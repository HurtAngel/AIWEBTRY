import dotenv from "dotenv";
import pg from "pg";
import { createRealtime, rawSql } from "@neon/realtime/server";
import { createRealtimeClient } from "@neon/realtime/client";

dotenv.config({ path: ".env.local" });

const dbUrl = process.env.DATABASE_URL;
const realtimeUrl = process.env.NEON_REALTIME_URL;
const realtimeSecret = process.env.NEON_REALTIME_SECRET;

if (!dbUrl || !realtimeUrl || !realtimeSecret) {
  console.error("Missing required env vars in .env.local");
  process.exit(1);
}

const dbName = new URL(dbUrl).pathname.replace(/^\//, "") || "neondb";

const pool = new pg.Pool({ connectionString: dbUrl });
await pool.query(`
  CREATE TABLE IF NOT EXISTS live_activity (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
  );
`);

const realtime = createRealtime({
  secret: realtimeSecret,
  db: dbName,
});

const query = rawSql(
  "SELECT id, message, created_at FROM live_activity ORDER BY id DESC LIMIT 10"
);

const sealed = await realtime.seal({ query });
console.log("Sealed live query created (token length:", sealed.token?.length ?? "ok", ")");

const client = createRealtimeClient({ url: realtimeUrl });
const sub = client.subscribe(sealed);

let initialReceived = false;
const testMsg = `Realtime test event @ ${new Date().toISOString()}`;

const done = new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error("Timed out waiting for live update")), 15000);

  sub.onChange(async () => {
    const snap = sub.getSnapshot();
    const rows = snap?.data ?? [];
    if (!initialReceived) {
      initialReceived = true;
      console.log("Initial snapshot rows:", rows.length);
      const res = await pool.query(
        "INSERT INTO live_activity (message) VALUES ($1) RETURNING id, message, pg_current_xact_id()::text AS txid",
        [testMsg]
      );
      console.log("Inserted row:", res.rows[0]);
    } else {
      const found = rows.find((r) => r.message === testMsg);
      if (found) {
        console.log("Subscriber received live row:", found);
        clearTimeout(timeout);
        resolve();
      }
    }
  });

  sub.onStateChange((state) => {
    if (state.status === "error") {
      clearTimeout(timeout);
      reject(new Error(`Subscription error: ${state.error?.message || "unknown"}`));
    }
  });
});

await done;
sub.unsubscribe?.();
await pool.end();
console.log("Neon Realtime end-to-end test PASSED!");
process.exit(0);
