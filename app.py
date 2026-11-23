import os
import sys
import json
import uuid
import time
import base64
import threading
import requests
from datetime import datetime
from functools import wraps
from io import BytesIO
from flask import Flask, render_template, request, jsonify, session, send_file, Response
from dotenv import load_dotenv

try:
    import psycopg2
except ImportError:
    psycopg2 = None

load_dotenv()
load_dotenv(".env.local", override=False)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "nexus-ai-rp-studio-secret-key-2026")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(BASE_DIR, "db.json")
MEDIA_DIR = os.path.join(BASE_DIR, "static", "media")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
os.makedirs(MEDIA_DIR, exist_ok=True)

db_lock = threading.RLock()


def get_default_db():
    return {
        "settings": {
            "site_title": "NEXUS AI // RP & Studio",
            "site_subtitle": "Yeni Nesil Sansürsüz Rol Yapma ve Üretim Stüdyosu",
            "welcome_message": "Nexus AI Stüdyosuna hoş geldin! Karakterini seç veya yeni bir dünya yarat.",
            "api_base_url": "https://api.venice.ai/api/v1",
            "chat_endpoint": "https://api.venice.ai/api/v1/chat/completions",
            "image_endpoint": "https://api.venice.ai/api/v1/image/generate",
            "image_edit_endpoint": "https://api.venice.ai/api/v1/image/edit",
            "video_endpoint": "https://api.venice.ai/api/v1/video/queue",
            "venice_api_key": os.getenv("VENICE_API_KEY", ""),
            "default_register_credits": "100",
            "default_char_limit": "3",
            "default_train_limit": "1",
            "allow_registration": "true",
            "maintenance_mode": "false",
            "no_credit_warning": "Yetersiz kredi! İşleme devam etmek için yönetici ile iletişime geçin.",
            "limit_reached_warning": "Hesabınız için tanımlanan oluşturma/eğitim kotası doldu!",
            "unauthorized_model_warning": "Bu AI modelini kullanmak için yetkiniz bulunmuyor.",
            "bypass_422_base_credit": "85",
            "bypass_422_prompt": "heavily blur and pixelate the face, strong gaussian blur over the face and eyes, keep the rest of the image and body unchanged",
            "rp_system_prefix": (
                "Sen üst düzey, yaratıcı ve sansürsüz bir rol yapma (Roleplay) yapay zekasısın. "
                "Karakterin kişiliğine sıkı sıkıya bağlı kal. Aksiyonları *yıldız içinde*, "
                "konuşmaları ise doğal diyalog olarak yaz. Asla yapay zeka olduğunu belli etme "
                "ve kullanıcının yerine konuşma."
            ),
            "summarizer_model_id": "venice-uncensored",
            "memory_trigger_count": "10",
            "memory_keep_recent": "4",
            "summarizer_prompt": (
                "Aşağıdaki rol yapma sohbet geçmişini ve mevcut özeti oku. Önemli olayları, "
                "karakter ilişkilerini, verilen sözleri, mekan değişimlerini ve kritik detayları "
                "hiçbir önemli veriyi kaçırmadan maddeler halinde Türkçe olarak özetle. "
                "Gereksiz selamlaşmaları atla."
            ),
            "default_temperature": "0.85",
            "default_max_tokens": "600",
            "demo_fallback_when_no_key": "false",
            "ui_btn_send": "Gönder",
            "ui_btn_generate_img": "Görseli Üret",
            "ui_btn_generate_vid": "Videoyu Üret"
        },
        "users": {
            "Admin": {
                "username": "Admin",
                "password": "1234",
                "role": "admin",
                "credits": 999999,
                "char_limit": 9999,
                "train_limit": 9999,
                "allowed_models": ["*"],
                "persona_name": "Gezgin",
                "persona_desc": "Gizemli, zeki ve kararlı bir maceracı.",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        },
        "models": [
            {
                "id": "mdl_venice_uncensored",
                "name": "Venice Uncensored (RP Master)",
                "api_model_id": "venice-uncensored",
                "type": "chat",
                "cost": 2,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_llama_70b",
                "name": "Llama 3.3 70B Instruct",
                "api_model_id": "llama-3.3-70b",
                "type": "chat",
                "cost": 3,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_firered_edit",
                "name": "FireRed Image Edit (Ucuz img2img)",
                "api_model_id": "firered-image-edit",
                "type": "image",
                "cost": 12,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_qwen_edit",
                "name": "Qwen Image 2.1 Turbo Edit (img2img)",
                "api_model_id": "qwen-image-2-1-turbo-edit",
                "type": "image",
                "cost": 15,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_qwen_edit_uncensored",
                "name": "Qwen Edit Uncensored (img2img)",
                "api_model_id": "qwen-edit-uncensored",
                "type": "image",
                "cost": 15,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_lustify_uncensored",
                "name": "Lustify SDXL (Tam Sansürsüz txt2img)",
                "api_model_id": "lustify-sdxl",
                "type": "image",
                "cost": 10,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_lustify_v8",
                "name": "Lustify v8 (Sansürsüz Yeni txt2img)",
                "api_model_id": "lustify-v8",
                "type": "image",
                "cost": 10,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_flux_img",
                "name": "Venice Fluently XL Image",
                "api_model_id": "fluently-xl",
                "type": "image",
                "cost": 10,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_seedream",
                "name": "Seedream V4.5",
                "api_model_id": "seedream-v4.5",
                "type": "image",
                "cost": 12,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_wan_video",
                "name": "Venice Wan-2.5 Motion Video",
                "api_model_id": "wan-2.5-preview-text-to-video",
                "type": "video",
                "cost": 25,
                "endpoint_override": "",
                "active": True
            }
        ],
        "characters": [],
        "trained_models": [
            {
                "id": "trn_default_cyber",
                "creator": "Admin",
                "name": "Gotik & Siberpunk Karakter Paketi",
                "type": "image_lora",
                "trigger_word": "nvr_style, dark cinematic lighting, detailed face",
                "training_data": "Karanlık neon atmosfer, keskin hatlar, sinematik ışıklandırma ve karakter tutarlılığı.",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ],
        "chats": {},
        "assistant_chats": {},
        "media": {},
        "global_chat": [],
        "dms": {}
    }


DB = get_default_db()


def clean_media_path(url_or_path):
    if not url_or_path or not isinstance(url_or_path, str):
        return ""
    if url_or_path.startswith("data:"):
        return url_or_path
    return url_or_path.split("?")[0].split("#")[0].strip()


def ensure_db_compatibility(loaded):
    default = get_default_db()
    if not isinstance(loaded, dict):
        return default

    for k, v in default.items():
        if k not in loaded or not isinstance(loaded[k], type(v)):
            loaded[k] = v

    for sk, sv in default["settings"].items():
        if sk not in loaded["settings"]:
            loaded["settings"][sk] = sv

    if loaded["settings"].get("image_endpoint") == "https://api.venice.ai/api/v1/images/generations":
        loaded["settings"]["image_endpoint"] = "https://api.venice.ai/api/v1/image/generate"

    if "Admin" not in loaded["users"]:
        loaded["users"]["Admin"] = default["users"]["Admin"]
    else:
        loaded["users"]["Admin"]["role"] = "admin"

    loaded["characters"] = [
        c for c in loaded.get("characters", [])
        if isinstance(c, dict) and c.get("id") != "char_seraphina"
    ]
    for c in loaded["characters"]:
        if not c.get("reference_image"):
            c["reference_image"] = c.get("avatar", "")

    existing_ids = {m.get("api_model_id") for m in loaded.get("models", []) if isinstance(m, dict)}
    for def_m in default["models"]:
        if def_m["api_model_id"] not in existing_ids:
            loaded["models"].append(def_m)

    fixed_media = {}
    for mid, m in loaded.get("media", {}).items():
        if isinstance(m, dict) and m.get("file_path"):
            m["file_path"] = clean_media_path(m["file_path"])
            fixed_media[mid] = m
    loaded["media"] = fixed_media

    return loaded


def sync_disk_media_to_db():
    if not os.path.exists(MEDIA_DIR):
        return False

    changed = False
    existing_files = {
        os.path.basename(clean_media_path(m.get("file_path", "")))
        for m in DB.get("media", {}).values()
        if isinstance(m, dict)
    }

    for fname in os.listdir(MEDIA_DIR):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".webp", ".mp4"]:
            continue
        if fname in existing_files:
            continue

        fpath = os.path.join(MEDIA_DIR, fname)
        if not os.path.isfile(fpath):
            continue

        try:
            stat = os.stat(fpath)
            if stat.st_size < 100:
                continue
            size_kb = round(stat.st_size / 1024.0, 2)
            created_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            size_kb = 0.0
            created_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        mtype = "video" if ext == ".mp4" else "image"
        stem = os.path.splitext(fname)[0]
        mid = stem.replace("nexus_", "") if stem.startswith("nexus_med_") else ("med_" + uuid.uuid4().hex[:8])
        if mid in DB["media"]:
            mid = "med_" + uuid.uuid4().hex[:8]

        DB["media"][mid] = {
            "id": mid,
            "user": "Admin",
            "type": mtype,
            "mode": "txt2vid" if mtype == "video" else "txt2img",
            "prompt": f"Kurtarılan Medya ({fname})",
            "model": "Venice AI",
            "aspect_ratio": "16:9" if mtype == "video" else "1:1",
            "file_path": f"/static/media/{fname}",
            "size_kb": size_kb,
            "created_at": created_str
        }
        changed = True

    return changed


_pg_initialized = False


def get_pg_conn():
    global _pg_initialized
    if not DATABASE_URL or psycopg2 is None:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        if not _pg_initialized:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS app_state (
                        id TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS media_blobs (
                        filename TEXT PRIMARY KEY,
                        mime_type TEXT NOT NULL,
                        data BYTEA NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.commit()
            _pg_initialized = True
        return conn
    except Exception as e:
        print(f"[PG BAĞLANTI HATASI]: {e}")
        return None


def save_media_blob_to_pg(filename, mime_type, raw_bytes):
    conn = get_pg_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO media_blobs (filename, mime_type, data)
                VALUES (%s, %s, %s)
                ON CONFLICT (filename) DO UPDATE SET
                    mime_type = EXCLUDED.mime_type,
                    data = EXCLUDED.data;
                """,
                (filename, mime_type, psycopg2.Binary(raw_bytes))
            )
        conn.commit()
    except Exception as e:
        print(f"[PG MEDIA KAYIT HATASI]: {e}")
    finally:
        conn.close()


def get_media_blob_from_pg(filename):
    conn = get_pg_conn()
    if not conn:
        return None, None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT mime_type, data FROM media_blobs WHERE filename = %s;", (filename,))
            row = cur.fetchone()
            if row:
                return row[0], bytes(row[1])
    except Exception as e:
        print(f"[PG MEDIA OKUMA HATASI]: {e}")
    finally:
        conn.close()
    return None, None


def save_db_unlocked():
    payload_str = json.dumps(DB, ensure_ascii=False, indent=2)
    try:
        tmp_file = DB_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(payload_str)
        os.replace(tmp_file, DB_FILE)
    except Exception as e:
        print(f"[DB KAYIT HATASI]: {e}")

    conn = get_pg_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_state (id, data, updated_at)
                    VALUES ('main', %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        data = EXCLUDED.data,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (payload_str,)
                )
            conn.commit()
        except Exception as e:
            print(f"[PG DB KAYIT HATASI]: {e}")
        finally:
            conn.close()


def save_db():
    with db_lock:
        save_db_unlocked()


def load_db():
    global DB
    with db_lock:
        loaded_from_pg = False
        conn = get_pg_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT data FROM app_state WHERE id = 'main';")
                    row = cur.fetchone()
                    if row and row[0]:
                        loaded = json.loads(row[0])
                        DB = ensure_db_compatibility(loaded)
                        loaded_from_pg = True
            except Exception as e:
                print(f"[PG DB YÜKLEME HATASI]: {e}")
            finally:
                conn.close()

        if not loaded_from_pg and os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    DB = ensure_db_compatibility(loaded)
            except Exception as e:
                print(f"[DB YÜKLEME HATASI]: {e}")

        recovered = sync_disk_media_to_db()
        if recovered or not loaded_from_pg or not os.path.exists(DB_FILE):
            save_db_unlocked()


load_db()


def get_current_user():
    uname = session.get("username")
    if uname and uname in DB["users"]:
        return DB["users"][uname]
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Oturum açmanız gerekiyor."}), 401
        if DB["settings"].get("maintenance_mode") == "true" and user.get("role") != "admin":
            return jsonify({"error": "Sistem şu anda bakım modundadır."}), 503
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user.get("role") != "admin":
            return jsonify({"error": "Bu işlem için Admin yetkisi gereklidir."}), 403
        return f(*args, **kwargs)
    return decorated


def check_and_deduct_credit(user, model_obj, extra_cost=0):
    total_cost = int(model_obj.get("cost", 1)) + int(extra_cost)
    if user.get("role") == "admin":
        return True, None, total_cost
    allowed = user.get("allowed_models", ["*"])
    if "*" not in allowed and model_obj["id"] not in allowed and model_obj["api_model_id"] not in allowed:
        return False, DB["settings"].get("unauthorized_model_warning", "Bu modele erişim yetkiniz yok."), 0
    current_credits = int(user.get("credits", 0))
    if current_credits < total_cost:
        return False, DB["settings"].get("no_credit_warning", f"Yetersiz kredi! Gereken: {total_cost}⚡"), 0
    user["credits"] = current_credits - total_cost
    save_db()
    return True, None, total_cost


def refund_credit(user, model_obj, extra_cost=0):
    if user.get("role") == "admin":
        return
    total_cost = int(model_obj.get("cost", 1)) + int(extra_cost)
    user["credits"] = int(user.get("credits", 0)) + total_cost
    save_db()


def get_ram_usage_mb():
    try:
        if os.path.exists("/proc/self/status"):
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return round(int(line.split()[1]) / 1024.0, 2)
    except Exception:
        pass
    db_bytes = len(json.dumps(DB, ensure_ascii=False).encode("utf-8"))
    return round(28.5 + (db_bytes / (1024 * 1024)), 2)


def save_media_file_helper(data_url, media_type):
    media_id = "med_" + uuid.uuid4().hex[:8]
    ext = "mp4" if media_type == "video" else "png"

    if data_url.startswith("data:"):
        header, b64_data = data_url.split(",", 1)
        raw_bytes = base64.b64decode(b64_data)
        if "webp" in header:
            ext = "webp"
        elif "jpeg" in header or "jpg" in header:
            ext = "jpg"
        elif "mp4" in header or "video" in header:
            ext = "mp4"
    elif clean_media_path(data_url).startswith("/static/media/"):
        clean_path = clean_media_path(data_url)
        fname_only = os.path.basename(clean_path)
        local_path = os.path.join(MEDIA_DIR, fname_only)
        if os.path.exists(local_path):
            with open(local_path, "rb") as lf:
                raw_bytes = lf.read()
        else:
            _, pg_bytes = get_media_blob_from_pg(fname_only)
            if not pg_bytes:
                raise FileNotFoundError(f"Medya bulunamadı: {fname_only}")
            raw_bytes = pg_bytes
        if local_path.endswith(".mp4"):
            ext = "mp4"
        elif local_path.endswith((".jpg", ".jpeg")):
            ext = "jpg"
        elif local_path.endswith(".webp"):
            ext = "webp"
    else:
        r = requests.get(data_url, timeout=60)
        r.raise_for_status()
        raw_bytes = r.content
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "video" in ctype:
            ext = "mp4"
        elif "webp" in ctype:
            ext = "webp"
        elif "jpeg" in ctype or "jpg" in ctype:
            ext = "jpg"

    filename = f"nexus_{media_id}.{ext}"
    filepath = os.path.join(MEDIA_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(raw_bytes)

    mime_map = {"mp4": "video/mp4", "jpg": "image/jpeg", "webp": "image/webp", "png": "image/png"}
    save_media_blob_to_pg(filename, mime_map.get(ext, "application/octet-stream"), raw_bytes)

    size_kb = round(len(raw_bytes) / 1024.0, 2)
    public_url = f"/static/media/{filename}"
    return media_id, public_url, size_kb


def resolve_source_media_to_b64(source_media):
    if not source_media or not isinstance(source_media, str):
        return None, None
    try:
        if source_media.startswith("data:"):
            header, b64_data = source_media.split(",", 1)
            return b64_data.strip(), source_media

        cleaned = clean_media_path(source_media)
        if cleaned.startswith("/static/media/"):
            fname = os.path.basename(cleaned)
            fpath = os.path.join(MEDIA_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    raw = f.read()
                b64 = base64.b64encode(raw).decode("utf-8")
                mime = "video/mp4" if fname.endswith(".mp4") else "image/png"
                return b64, f"data:{mime};base64,{b64}"

        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            r = requests.get(cleaned, timeout=30)
            if r.status_code == 200:
                b64 = base64.b64encode(r.content).decode("utf-8")
                ctype = r.headers.get("Content-Type", "image/png").split(";")[0]
                return b64, f"data:{ctype};base64,{b64}"
    except Exception as e:
        print(f"[KAYNAK MEDYA ÇÖZÜMLEME HATASI]: {e}")
    return None, None


def call_llm_api(messages, model_api_id, endpoint_override="", temperature=None, max_tokens=None):
    api_key = (DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")).strip()
    url = endpoint_override.strip() if endpoint_override else DB["settings"].get("chat_endpoint", "https://api.venice.ai/api/v1/chat/completions")
    temp = float(temperature if temperature is not None else DB["settings"].get("default_temperature", 0.85))
    mtok = int(max_tokens if max_tokens is not None else DB["settings"].get("default_max_tokens", 600))

    if not api_key:
        if DB["settings"].get("demo_fallback_when_no_key", "false") == "true":
            last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "Merhaba")
            return f"*[Demo Modu]*\n\n*Bakışlarını sana çevirir.* \"{last_user_msg[:80]}... Admin panelinden `venice_api_key` girdiğinde gerçek **{model_api_id}** modeliyle konuşacağız.\""
        raise Exception("Venice API Anahtarı tanımlanmamış!")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_api_id,
        "messages": messages,
        "temperature": temp,
        "max_tokens": mtok
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise Exception(f"Venice Chat API Hatası ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def compress_chat_memory_if_needed(chat, force=False):
    trigger_count = int(DB["settings"].get("memory_trigger_count", 10))
    keep_recent = int(DB["settings"].get("memory_keep_recent", 4))
    msgs = chat.get("messages", [])

    if not force and len(msgs) < trigger_count:
        return False
    if len(msgs) <= keep_recent:
        return False

    to_summarize = msgs[:-keep_recent]
    recent_msgs = msgs[-keep_recent:]

    convo_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in to_summarize])
    existing_summary = chat.get("memory_summary", "")

    summarizer_prompt = DB["settings"].get("summarizer_prompt", "Önemli olayları Türkçe maddeler halinde özetle.")
    summarizer_model = DB["settings"].get("summarizer_model_id", "venice-uncensored")

    prompt_messages = [
        {"role": "system", "content": summarizer_prompt},
        {
            "role": "user",
            "content": (
                f"MEVCUT HAFIZA ÖZETİ:\n{existing_summary or 'Yok'}\n\n"
                f"YENİ EKLENEN ESKİ MESAJLAR:\n{convo_text}\n\n"
                "Lütfen güncellenmiş, birleştirilmiş yeni hafıza özetini yaz:"
            )
        }
    ]

    try:
        new_summary = call_llm_api(prompt_messages, summarizer_model, temperature=0.4, max_tokens=500)
        chat["memory_summary"] = new_summary
        chat["messages"] = recent_msgs
        save_db()
        return True
    except Exception as e:
        print(f"[HAFIZA ÖZETLEME HATASI]: {e}")
        return False


def extract_image_from_response(resp):
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "image/" in ctype or "application/octet-stream" in ctype:
        mime = "image/webp" if "webp" in ctype else ("image/jpeg" if ("jpeg" in ctype or "jpg" in ctype) else "image/png")
        b64_img = base64.b64encode(resp.content).decode("utf-8")
        return f"data:{mime};base64,{b64_img}"

    try:
        rj = resp.json()
    except Exception:
        return None

    if isinstance(rj, dict):
        if "images" in rj and isinstance(rj["images"], list) and len(rj["images"]) > 0:
            item = rj["images"][0]
            if isinstance(item, str):
                return item if item.startswith(("http", "data:")) else f"data:image/png;base64,{item}"
            if isinstance(item, dict):
                if "b64_json" in item:
                    return f"data:image/png;base64,{item['b64_json']}"
                if "url" in item:
                    return item["url"]
        if "data" in rj and isinstance(rj["data"], list) and len(rj["data"]) > 0:
            d0 = rj["data"][0]
            if isinstance(d0, dict):
                if "b64_json" in d0:
                    return f"data:image/png;base64,{d0['b64_json']}"
                if "url" in d0:
                    return d0["url"]
            elif isinstance(d0, str):
                return d0 if d0.startswith(("http", "data:")) else f"data:image/png;base64,{d0}"
        if "image" in rj and isinstance(rj["image"], str):
            return rj["image"] if rj["image"].startswith(("http", "data:")) else f"data:image/png;base64,{rj['image']}"
        if "url" in rj and isinstance(rj["url"], str):
            return rj["url"]
    return None


def execute_venice_edit_multipart(auth_header_val, model_api_id, prompt_text, raw_b64):
    """
    Venice /api/v1/image/edit uç noktasına resmi Multipart Form-Data isteği gönderir.
    """
    edit_ep = "https://api.venice.ai/api/v1/image/edit"
    auth_headers = {"Authorization": auth_header_val}
    img_bytes = base64.b64decode(raw_b64)
    files_dict = {"image": ("input.png", img_bytes, "image/png")}
    form_data = {
        "model": model_api_id or "qwen-image-2-1-turbo-edit",
        "prompt": prompt_text,
        "safe_mode": "false"
    }

    try:
        r = requests.post(edit_ep, headers=auth_headers, data=form_data, files=files_dict, timeout=120)
        if r.status_code == 400 and "safe_mode" in r.text.lower():
            form_data.pop("safe_mode", None)
            files_retry = {"image": ("input.png", img_bytes, "image/png")}
            r = requests.post(edit_ep, headers=auth_headers, data=form_data, files=files_retry, timeout=120)

        if r.status_code == 200:
            data_url = extract_image_from_response(r)
            if data_url:
                return data_url, None
            return None, "Venice Edit API yanıtından görsel verisi okunamadı."
        return None, f"Venice Edit API Hatası ({r.status_code}): {r.text[:300]}"
    except Exception as e:
        return None, f"Venice Edit Bağlantı Hatası: {str(e)}"


def execute_venice_multi_edit_multipart(auth_header_val, model_api_id, prompt_text, b64_list):
    """
    Venice /api/v1/image/multi-edit uç noktasına birden fazla görseli Multipart Form-Data olarak gönderir.
    Venice dokümantasyonuna göre:
      - Alan adı: 'images' (birden fazla part aynı isimle)
      - Model alanı: 'modelId' (multi-edit sadece modelId kabul eder)
    """
    multi_ep = "https://api.venice.ai/api/v1/image/multi-edit"
    auth_headers = {"Authorization": auth_header_val}
    files_list = [
        ("images", (f"input_{idx}.png", base64.b64decode(b64), "image/png"))
        for idx, b64 in enumerate(b64_list)
    ]
    form_data = {
        "modelId": model_api_id or "firered-image-edit",
        "prompt": prompt_text,
        "safe_mode": "false"
    }
    try:
        r = requests.post(multi_ep, headers=auth_headers, data=form_data, files=files_list, timeout=120)
        if r.status_code == 400 and "safe_mode" in r.text.lower():
            form_data.pop("safe_mode", None)
            files_retry = [
                ("images", (f"input_{idx}.png", base64.b64decode(b64), "image/png"))
                for idx, b64 in enumerate(b64_list)
            ]
            r = requests.post(multi_ep, headers=auth_headers, data=form_data, files=files_retry, timeout=120)

        if r.status_code == 200:
            data_url = extract_image_from_response(r)
            if data_url:
                return data_url, None
            return None, "Venice Multi-Edit API yanıtından görsel verisi okunamadı."
        return None, f"Venice Multi-Edit API Hatası ({r.status_code}): {r.text[:300]}"
    except Exception as e:
        return None, f"Venice Multi-Edit Bağlantı Hatası: {str(e)}"


def smart_generate_image(
    endpoint,
    headers,
    model_api_id,
    final_prompt,
    negative_prompt,
    aspect_ratio,
    source_media=None,
    strength=0.65,
    bypass_422=False,
    bypass_model_api_id="firered-image-edit",
    source_images=None
):
    """
    Venice.ai Resmi API Uyumlu Görsel Üretim Fonksiyonu.
    bypass_422 aktifse:
      Adım 1 -> Seçilen bypass modeliyle yüzü blurlar.
      Adım 2 -> Blurlanmış görseli asıl model ve asıl prompt ile işler.
    """
    dim_map = {"1:1": (1024, 1024), "16:9": (1280, 720), "9:16": (720, 1280)}
    w, h = dim_map.get(aspect_ratio, (1024, 1024))

    b64_list = []
    if source_images and isinstance(source_images, list):
        for sm in source_images:
            b64_item, _ = resolve_source_media_to_b64(sm)
            if b64_item:
                b64_list.append(b64_item)

    raw_b64, full_data_url = resolve_source_media_to_b64(source_media)
    if raw_b64 and not b64_list:
        b64_list.append(raw_b64)

    is_img2img = len(b64_list) > 0
    selected_model = (model_api_id or "").strip()
    auth_val = headers.get("Authorization", "")

    # 1. IMG2IMG / EDIT MODU
    if is_img2img:
        working_b64 = b64_list[0]

        # 422 ENGELLEYİCİ (ÖNCE YÜZÜ BLURLAMA ADIMI)
        if bypass_422:
            blur_prompt = DB["settings"].get(
                "bypass_422_prompt",
                "heavily blur and pixelate the face, strong gaussian blur over the face and eyes, keep the rest of the image and body unchanged"
            )
            step1_model = (bypass_model_api_id or "firered-image-edit").strip()
            blurred_data_url, blur_err = execute_venice_edit_multipart(
                auth_val, step1_model, blur_prompt, working_b64
            )
            if blur_err or not blurred_data_url:
                return None, f"[422 Engelleyici 1. Adım (Yüz Blurlama) Hatası]: {blur_err}"

            step1_b64, _ = resolve_source_media_to_b64(blurred_data_url)
            if not step1_b64:
                return None, "[422 Engelleyici Hatası]: Blurlanan ara görsel okunamadı."
            working_b64 = step1_b64
            b64_list[0] = working_b64

        if len(b64_list) > 1:
            return execute_venice_multi_edit_multipart(
                auth_val,
                selected_model or "firered-image-edit",
                final_prompt,
                b64_list
            )

        # ASIL PROMPT VE ASIL MODEL ADIMI (Tek görsel)
        return execute_venice_edit_multipart(
            auth_val,
            selected_model or "qwen-image-2-1-turbo-edit",
            final_prompt,
            working_b64
        )

    # 2. TXT2IMG MODU (Resmi /api/v1/image/generate Endpoint'i)
    txt_model_map = {
        "qwen-edit-uncensored": "lustify-sdxl",
        "firered-image-edit": "fluently-xl",
        "qwen-image-2-1-turbo-edit": "fluently-xl",
    }
    target_txt_model = txt_model_map.get(selected_model, selected_model or "lustify-sdxl")
    if target_txt_model.endswith("-edit"):
        target_txt_model = target_txt_model[:-5]

    gen_ep = "https://api.venice.ai/api/v1/image/generate" if (not endpoint or "venice.ai" in endpoint) else endpoint
    json_headers = {
        "Authorization": auth_val,
        "Content-Type": "application/json"
    }

    pixel_based_models = {"lustify-sdxl", "lustify-v7", "lustify-v8", "fluently-xl", "venice-sd35", "z-image-turbo"}
    uses_pixels = target_txt_model in pixel_based_models

    payload = {
        "model": target_txt_model,
        "prompt": final_prompt,
        "safe_mode": False,
        "hide_watermark": True
    }
    if uses_pixels:
        payload["width"] = w
        payload["height"] = h
    else:
        payload["aspect_ratio"] = aspect_ratio

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    try:
        r = requests.post(gen_ep, headers=json_headers, json=payload, timeout=120)
        if r.status_code == 400:
            err_lower = r.text.lower()
            retry_needed = False
            if "aspect_ratio" in err_lower and "aspect_ratio" in payload:
                payload.pop("aspect_ratio", None)
                payload["width"] = w
                payload["height"] = h
                retry_needed = True
            elif ("width" in err_lower or "height" in err_lower) and "width" in payload:
                payload.pop("width", None)
                payload.pop("height", None)
                payload["aspect_ratio"] = aspect_ratio
                retry_needed = True
            if "negative_prompt" in err_lower and "negative_prompt" in payload:
                payload.pop("negative_prompt", None)
                retry_needed = True
            if "hide_watermark" in err_lower and "hide_watermark" in payload:
                payload.pop("hide_watermark", None)
                retry_needed = True

            if retry_needed:
                r = requests.post(gen_ep, headers=json_headers, json=payload, timeout=120)

        if r.status_code == 200:
            data_url = extract_image_from_response(r)
            if data_url:
                return data_url, None
            return None, f"Görsel verisi ayrıştırılamadı: {r.text[:200]}"

        return None, f"Venice Görsel API Hatası ({r.status_code}): {r.text[:300]}"
    except Exception as e:
        return None, f"Venice Görsel Bağlantı Hatası: {str(e)}"


def smart_generate_video(endpoint, headers, model_api_id, final_prompt, negative_prompt, aspect_ratio, resolution="720p", source_media=None, strength=0.65):
    ar_clean = aspect_ratio if aspect_ratio in ["16:9", "9:16", "1:1"] else "16:9"
    queue_url = "https://api.venice.ai/api/v1/video/queue"
    retrieve_url = "https://api.venice.ai/api/v1/video/retrieve"

    raw_b64, full_data_url = resolve_source_media_to_b64(source_media)
    has_media_input = bool(full_data_url)

    mid = (model_api_id or "wan-2.5-preview-text-to-video").strip()
    if has_media_input and mid.endswith("-text-to-video"):
        target_model = mid.replace("-text-to-video", "-image-to-video")
    elif not has_media_input and mid.endswith("-image-to-video"):
        target_model = mid.replace("-image-to-video", "-text-to-video")
    else:
        target_model = mid

    json_headers = {
        "Authorization": headers.get("Authorization", ""),
        "Content-Type": "application/json"
    }
    ep = queue_url if (not endpoint or "venice.ai" in endpoint) else endpoint

    payload = {
        "model": target_model,
        "prompt": final_prompt,
        "duration": "5s",
        "resolution": resolution
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if has_media_input:
        if "video" in full_data_url[:30]:
            payload["video_url"] = full_data_url
        else:
            payload["image_url"] = full_data_url
    else:
        payload["aspect_ratio"] = ar_clean

    try:
        r = requests.post(ep, headers=json_headers, json=payload, timeout=180)
        ctype = (r.headers.get("Content-Type") or "").lower()

        if r.status_code == 200 and ("video/" in ctype or "application/octet-stream" in ctype):
            b64_vid = base64.b64encode(r.content).decode("utf-8")
            return f"data:video/mp4;base64,{b64_vid}", None

        if r.status_code == 200:
            rj = r.json()
            if "queue_id" in rj:
                qid = rj["queue_id"]
                for _ in range(45):
                    time.sleep(3)
                    poll_r = requests.post(
                        retrieve_url,
                        headers=json_headers,
                        json={"model": target_model, "queue_id": qid},
                        timeout=60
                    )
                    poll_ctype = (poll_r.headers.get("Content-Type") or "").lower()
                    if poll_r.status_code == 200 and ("video/" in poll_ctype or "application/octet-stream" in poll_ctype):
                        b64_vid = base64.b64encode(poll_r.content).decode("utf-8")
                        return f"data:video/mp4;base64,{b64_vid}", None
                    if poll_r.status_code == 200:
                        prj = poll_r.json()
                        status = str(prj.get("status", "")).upper()
                        if status in ["COMPLETED", "SUCCEEDED", "DONE"]:
                            for k in ["url", "video_url", "output"]:
                                if isinstance(prj.get(k), str) and prj[k]:
                                    return prj[k], None
                            if "data" in prj and isinstance(prj["data"], list) and len(prj["data"]) > 0:
                                d0 = prj["data"][0]
                                if isinstance(d0, dict):
                                    if "url" in d0:
                                        return d0["url"], None
                                    if "b64_json" in d0:
                                        return f"data:video/mp4;base64,{d0['b64_json']}", None
                        elif status in ["FAILED", "ERROR"]:
                            return None, f"Video üretimi başarısız oldu: {prj}"
                return None, "Video üretim süresi zaman aşımına uğradı."

            if "url" in rj:
                return rj["url"], None
            if "video" in rj:
                v = rj["video"]
                return v if v.startswith("http") else f"data:video/mp4;base64,{v}", None

        return None, f"Venice Video API Hatası ({r.status_code}): {r.text[:300]}"
    except Exception as e:
        return None, f"Venice Video Bağlantı Hatası: {str(e)}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin_page():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return render_template("index.html")
    return render_template("admin.html")


@app.route("/api/init", methods=["GET"])
def api_init():
    with db_lock:
        if sync_disk_media_to_db():
            save_db_unlocked()

    user = get_current_user()
    public_settings = {k: v for k, v in DB["settings"].items() if "key" not in k.lower()}
    if not user:
        return jsonify({
            "authenticated": False,
            "settings": public_settings
        })

    uname = user["username"]
    is_admin = user.get("role") == "admin"

    visible_chars = [
        c for c in DB["characters"]
        if c.get("is_public", True) or c.get("creator") == uname or is_admin
    ]
    visible_trained = [
        t for t in DB["trained_models"]
        if t.get("creator") == uname or t.get("creator") == "Admin" or is_admin
    ]
    active_models = [m for m in DB["models"] if m.get("active", True)]
    user_chats = [c for c in DB["chats"].values() if c.get("user") == uname]
    user_assistant_chats = [c for c in DB["assistant_chats"].values() if c.get("user") == uname]

    user_media = []
    for m in DB.get("media", {}).values():
        if not isinstance(m, dict):
            continue
        if m.get("user") == uname or is_admin:
            clean_fp = clean_media_path(m.get("file_path", ""))
            item_copy = dict(m)
            item_copy["file_path"] = clean_fp
            item_copy["preview_url"] = clean_fp
            user_media.append(item_copy)

    user_directory = [
        {
            "username": u["username"],
            "persona_name": u.get("persona_name", u["username"]),
            "role": u.get("role", "user")
        }
        for u in DB["users"].values()
        if not u.get("banned", False)
    ]

    return jsonify({
        "authenticated": True,
        "user": {k: v for k, v in user.items() if k != "password"},
        "users_directory": user_directory,
        "settings": public_settings,
        "models": active_models,
        "characters": visible_chars,
        "trained_models": visible_trained,
        "chats": sorted(user_chats, key=lambda x: x.get("updated_at", ""), reverse=True),
        "assistant_chats": sorted(user_assistant_chats, key=lambda x: x.get("updated_at", ""), reverse=True),
        "media": sorted(user_media, key=lambda x: x.get("created_at", ""), reverse=True)
    })


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    user = DB["users"].get(username)
    if not user or user.get("password") != password:
        return jsonify({"error": "Kullanıcı adı veya şifre hatalı!"}), 401
    if user.get("banned"):
        return jsonify({"error": "Hesabınız yönetici tarafından askıya alınmıştır."}), 403

    session["username"] = username
    return jsonify({"success": True, "role": user.get("role", "user")})


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    if DB["settings"].get("allow_registration", "true").lower() != "true":
        return jsonify({"error": "Yeni üye alımı şu anda kapalıdır."}), 403

    data = request.json or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password or len(username) < 3:
        return jsonify({"error": "Kullanıcı adı en az 3 karakter olmalıdır."}), 400
    if username in DB["users"] or username.lower() == "admin":
        return jsonify({"error": "Bu kullanıcı adı zaten alınmış."}), 400

    DB["users"][username] = {
        "username": username,
        "password": password,
        "role": "user",
        "credits": int(DB["settings"].get("default_register_credits", 100)),
        "char_limit": int(DB["settings"].get("default_char_limit", 3)),
        "train_limit": int(DB["settings"].get("default_train_limit", 1)),
        "allowed_models": ["*"],
        "persona_name": username,
        "persona_desc": "Standart maceracı.",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_db()
    session["username"] = username
    return jsonify({"success": True})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/user/persona", methods=["POST"])
@login_required
def api_update_persona():
    user = get_current_user()
    data = request.json or {}
    user["persona_name"] = (data.get("persona_name") or user["username"]).strip()
    user["persona_desc"] = (data.get("persona_desc") or "").strip()
    save_db()
    return jsonify({"success": True})


@app.route("/api/characters", methods=["POST"])
@login_required
def api_create_character():
    user = get_current_user()
    uname = user["username"]
    my_chars = [c for c in DB["characters"] if c.get("creator") == uname]

    if user.get("role") != "admin" and len(my_chars) >= int(user.get("char_limit", 3)):
        return jsonify({"error": DB["settings"].get("limit_reached_warning", "Karakter oluşturma limitiniz doldu!")}), 403

    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Karakter adı zorunludur."}), 400

    avatar_val = data.get("avatar") or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&auto=format&fit=crop&q=80"
    ref_val = data.get("reference_image") or avatar_val

    if isinstance(avatar_val, str) and avatar_val.startswith("data:"):
        try:
            _, pub_av, _ = save_media_file_helper(avatar_val, "image")
            avatar_val = pub_av
        except Exception:
            pass

    if isinstance(ref_val, str) and ref_val.startswith("data:"):
        try:
            _, pub_url, _ = save_media_file_helper(ref_val, "image")
            ref_val = pub_url
        except Exception:
            pass

    new_char = {
        "id": "char_" + uuid.uuid4().hex[:8],
        "creator": uname,
        "name": name,
        "title": (data.get("title") or "Özel Karakter").strip(),
        "avatar": clean_media_path(avatar_val),
        "reference_image": clean_media_path(ref_val),
        "personality": (data.get("personality") or "").strip(),
        "scenario": (data.get("scenario") or "").strip(),
        "first_message": (data.get("first_message") or f"*Sana gülümseyerek bakar.* \"Merhaba, ben {name}.\"").strip(),
        "lorebook": (data.get("lorebook") or "").strip(),
        "trained_model_id": data.get("trained_model_id") or "",
        "is_public": bool(data.get("is_public", True)),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    DB["characters"].append(new_char)
    save_db()
    return jsonify({"success": True, "character": new_char})


@app.route("/api/characters/<char_id>", methods=["PUT"])
@login_required
def api_update_character(char_id):
    user = get_current_user()
    data = request.json or {}
    for c in DB["characters"]:
        if c["id"] == char_id:
            if user.get("role") != "admin" and c.get("creator") != user["username"]:
                return jsonify({"error": "Bu karakteri düzenleme yetkiniz yok."}), 403
            if "name" in data and (data.get("name") or "").strip():
                c["name"] = data["name"].strip()
            if "title" in data:
                c["title"] = (data.get("title") or "Özel Karakter").strip()
            if "personality" in data:
                c["personality"] = (data.get("personality") or "").strip()
            if "scenario" in data:
                c["scenario"] = (data.get("scenario") or "").strip()
            if "first_message" in data:
                c["first_message"] = (data.get("first_message") or "").strip()
            if "lorebook" in data:
                c["lorebook"] = (data.get("lorebook") or "").strip()
            if "trained_model_id" in data:
                c["trained_model_id"] = data.get("trained_model_id") or ""
            if "is_public" in data:
                c["is_public"] = bool(data.get("is_public"))
            if "avatar" in data and data["avatar"]:
                av = data["avatar"]
                if isinstance(av, str) and av.startswith("data:"):
                    try:
                        _, pub_av, _ = save_media_file_helper(av, "image")
                        av = pub_av
                    except Exception:
                        pass
                c["avatar"] = clean_media_path(av)
            if "reference_image" in data and data["reference_image"]:
                rv = data["reference_image"]
                if isinstance(rv, str) and rv.startswith("data:"):
                    try:
                        _, pub_rv, _ = save_media_file_helper(rv, "image")
                        rv = pub_rv
                    except Exception:
                        pass
                c["reference_image"] = clean_media_path(rv)
            save_db()
            return jsonify({"success": True, "character": c})
    return jsonify({"error": "Karakter bulunamadı."}), 404


@app.route("/api/characters/<char_id>", methods=["DELETE"])
@login_required
def api_delete_character(char_id):
    user = get_current_user()
    for i, c in enumerate(DB["characters"]):
        if c["id"] == char_id:
            if user.get("role") != "admin" and c.get("creator") != user["username"]:
                return jsonify({"error": "Bu karakteri silme yetkiniz yok."}), 403
            DB["characters"].pop(i)
            save_db()
            return jsonify({"success": True})
    return jsonify({"error": "Karakter bulunamadı."}), 404


@app.route("/api/trained-models", methods=["POST"])
@login_required
def api_train_model():
    user = get_current_user()
    uname = user["username"]
    my_trained = [t for t in DB["trained_models"] if t.get("creator") == uname]

    if user.get("role") != "admin" and len(my_trained) >= int(user.get("train_limit", 1)):
        return jsonify({"error": DB["settings"].get("limit_reached_warning", "Model eğitme kotanız doldu!")}), 403

    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Model adı zorunludur."}), 400

    new_trained = {
        "id": "trn_" + uuid.uuid4().hex[:8],
        "creator": uname,
        "name": name,
        "type": data.get("type", "memory_pack"),
        "trigger_word": (data.get("trigger_word") or "").strip(),
        "training_data": (data.get("training_data") or "").strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    DB["trained_models"].append(new_trained)
    save_db()
    return jsonify({"success": True, "trained_model": new_trained})


@app.route("/api/trained-models/<trn_id>", methods=["DELETE"])
@login_required
def api_delete_trained_model(trn_id):
    user = get_current_user()
    for i, t in enumerate(DB["trained_models"]):
        if t["id"] == trn_id:
            if user.get("role") != "admin" and t.get("creator") != user["username"]:
                return jsonify({"error": "Yetkiniz yok."}), 403
            DB["trained_models"].pop(i)
            save_db()
            return jsonify({"success": True})
    return jsonify({"error": "Bulunamadı."}), 404


@app.route("/api/rp/chats", methods=["POST"])
@login_required
def api_start_rp_chat():
    user = get_current_user()
    data = request.json or {}
    char_id = data.get("character_id")
    char = next((c for c in DB["characters"] if c["id"] == char_id), None)
    if not char:
        return jsonify({"error": "Karakter bulunamadı."}), 404

    chat_id = "rp_" + uuid.uuid4().hex[:8]
    first_msg = {
        "id": "msg_" + uuid.uuid4().hex[:8],
        "role": "assistant",
        "content": char["first_message"],
        "swipes": [char["first_message"]],
        "active_swipe": 0,
        "timestamp": datetime.now().strftime("%H:%M")
    }
    chat_obj = {
        "id": chat_id,
        "user": user["username"],
        "character_id": char["id"],
        "character_name": char["name"],
        "character_avatar": char["avatar"],
        "title": f"{char['name']} ile Sohbet",
        "memory_summary": "",
        "messages": [first_msg],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    DB["chats"][chat_id] = chat_obj
    save_db()
    return jsonify({"success": True, "chat": chat_obj})


@app.route("/api/rp/chats/<chat_id>", methods=["DELETE"])
@login_required
def api_delete_rp_chat(chat_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or (chat["user"] != user["username"] and user.get("role") != "admin"):
        return jsonify({"error": "Sohbet bulunamadı."}), 404
    del DB["chats"][chat_id]
    save_db()
    return jsonify({"success": True})


def build_rp_prompt_messages(user, char, chat):
    sys_prefix = DB["settings"].get("rp_system_prefix", "")
    persona_info = f"KULLANICI PERSONASI: İsim: {user.get('persona_name', user['username'])} | Özellikler: {user.get('persona_desc', '')}"
    char_info = (
        f"KARAKTER KİMLİĞİ:\nİsim: {char['name']} ({char.get('title', '')})\n"
        f"Kişilik: {char.get('personality', '')}\n"
        f"Senaryo: {char.get('scenario', '')}\n"
        f"Dünya Bilgisi (Lorebook): {char.get('lorebook', '')}"
    )

    trained_extra = ""
    if char.get("trained_model_id"):
        tm = next((t for t in DB["trained_models"] if t["id"] == char["trained_model_id"]), None)
        if tm:
            trained_extra = f"\nEĞİTİLMİŞ KARAKTER HAFIZASI ({tm['name']}):\n{tm.get('training_data', '')}"

    memory_block = ""
    if chat.get("memory_summary"):
        memory_block = f"\nÖNCEKİ OLAYLARIN ÖZETİ (UZUN SÜRELİ HAFIZA):\n{chat['memory_summary']}"

    system_content = f"{sys_prefix}\n\n{char_info}{trained_extra}\n\n{persona_info}{memory_block}"
    messages = [{"role": "system", "content": system_content}]
    for m in chat.get("messages", []):
        messages.append({"role": m["role"], "content": m["content"]})
    return messages


@app.route("/api/rp/chats/<chat_id>/message", methods=["POST"])
@login_required
def api_send_rp_message(chat_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or chat["user"] != user["username"]:
        return jsonify({"error": "Sohbet bulunamadı."}), 404

    data = request.json or {}
    content = (data.get("content") or "").strip()
    model_id = data.get("model_id")
    temperature = data.get("temperature")

    if not content:
        return jsonify({"error": "Mesaj boş olamaz."}), 400

    model_obj = (
        next((m for m in DB["models"] if m["id"] == model_id and m["type"] == "chat"), None)
        or next((m for m in DB["models"] if m["type"] == "chat" and m.get("active", True)), None)
    )
    if not model_obj:
        return jsonify({"error": "Aktif dil modeli bulunamadı."}), 400

    ok, err, _ = check_and_deduct_credit(user, model_obj)
    if not ok:
        return jsonify({"error": err}), 403

    char = next((c for c in DB["characters"] if c["id"] == chat["character_id"]), None)
    if not char:
        refund_credit(user, model_obj)
        return jsonify({"error": "Karakter silinmiş."}), 404

    user_msg = {
        "id": "msg_" + uuid.uuid4().hex[:8],
        "role": "user",
        "content": content,
        "swipes": [content],
        "active_swipe": 0,
        "timestamp": datetime.now().strftime("%H:%M")
    }
    chat["messages"].append(user_msg)

    try:
        prompt_msgs = build_rp_prompt_messages(user, char, chat)
        ai_reply = call_llm_api(
            prompt_msgs,
            model_obj["api_model_id"],
            model_obj.get("endpoint_override", ""),
            temperature=temperature
        )
    except Exception as e:
        chat["messages"].pop()
        refund_credit(user, model_obj)
        return jsonify({"error": str(e)}), 500

    ai_msg = {
        "id": "msg_" + uuid.uuid4().hex[:8],
        "role": "assistant",
        "content": ai_reply,
        "swipes": [ai_reply],
        "active_swipe": 0,
        "timestamp": datetime.now().strftime("%H:%M")
    }
    chat["messages"].append(ai_msg)
    chat["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    compressed = compress_chat_memory_if_needed(chat, force=False)
    save_db()

    return jsonify({
        "success": True,
        "chat": chat,
        "credits": user["credits"],
        "memory_compressed": compressed
    })


@app.route("/api/rp/chats/<chat_id>/scene-image", methods=["POST"])
@login_required
def api_rp_generate_scene_image(chat_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or chat["user"] != user["username"]:
        return jsonify({"error": "Sohbet bulunamadı."}), 404

    char = next((c for c in DB["characters"] if c["id"] == chat["character_id"]), None)
    if not char:
        return jsonify({"error": "Karakter bulunamadı."}), 404

    data = request.json or {}
    scene_prompt = (data.get("prompt") or "").strip()
    strength = float(data.get("strength") or 0.60)
    aspect_ratio = data.get("aspect_ratio", "16:9")
    img_model_id = data.get("model_id")

    if not scene_prompt:
        last_m = chat["messages"][-1]["content"] if chat.get("messages") else char.get("scenario", "")
        scene_prompt = f"{char['name']}, {char.get('personality', '')[:60]}, scene: {last_m[:180]}"
    else:
        scene_prompt = f"{char['name']}, {scene_prompt}"

    model_obj = (
        next((m for m in DB["models"] if m["id"] == img_model_id and m["type"] == "image"), None)
        or next((m for m in DB["models"] if m["type"] == "image" and m.get("active", True)), None)
    )
    if not model_obj:
        return jsonify({"error": "Aktif görsel üretim modeli bulunamadı."}), 400

    ok, err, _ = check_and_deduct_credit(user, model_obj)
    if not ok:
        return jsonify({"error": err}), 403

    api_key = (DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")).strip()
    if not api_key:
        refund_credit(user, model_obj)
        return jsonify({"error": "API Anahtarı tanımlanmamış!"}), 400

    ref_img = char.get("reference_image") or char.get("avatar")
    endpoint = model_obj.get("endpoint_override") or DB["settings"].get("image_endpoint", "https://api.venice.ai/api/v1/image/generate")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        data_url, api_err = smart_generate_image(
            endpoint, headers, model_obj["api_model_id"],
            scene_prompt, "deformed, blurry, bad anatomy", aspect_ratio,
            source_media=ref_img, strength=strength
        )
        if api_err or not data_url:
            refund_credit(user, model_obj)
            return jsonify({"error": api_err or "Sahne görseli üretilemedi."}), 400
        media_id, public_url, size_kb = save_media_file_helper(data_url, "image")
    except Exception as e:
        refund_credit(user, model_obj)
        return jsonify({"error": str(e)}), 500

    media_item = {
        "id": media_id,
        "user": user["username"],
        "type": "image",
        "mode": "rp_img2img",
        "prompt": scene_prompt,
        "model": model_obj["name"],
        "aspect_ratio": aspect_ratio,
        "file_path": public_url,
        "size_kb": size_kb,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    DB.setdefault("media", {})[media_id] = media_item

    scene_msg = {
        "id": "msg_" + uuid.uuid4().hex[:8],
        "role": "assistant",
        "content": f"*📸 Sahne Görseli ({scene_prompt[:70]})*",
        "media_url": public_url,
        "media_id": media_id,
        "swipes": [f"*📸 Sahne Görseli ({scene_prompt[:70]})*"],
        "active_swipe": 0,
        "timestamp": datetime.now().strftime("%H:%M")
    }
    chat["messages"].append(scene_msg)
    chat["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_db()

    return jsonify({
        "success": True,
        "chat": chat,
        "media": media_item | {"preview_url": public_url},
        "credits": user["credits"]
    })


@app.route("/api/rp/chats/<chat_id>/compress", methods=["POST"])
@login_required
def api_compress_rp_memory(chat_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or chat["user"] != user["username"]:
        return jsonify({"error": "Sohbet bulunamadı."}), 404
    ok = compress_chat_memory_if_needed(chat, force=True)
    if not ok:
        return jsonify({"error": "Özetlenecek yeterli mesaj yok."}), 400
    return jsonify({"success": True, "chat": chat})


@app.route("/api/rp/chats/<chat_id>/regenerate", methods=["POST"])
@login_required
def api_regenerate_rp_message(chat_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or chat["user"] != user["username"]:
        return jsonify({"error": "Sohbet bulunamadı."}), 404
    if not chat["messages"] or chat["messages"][-1]["role"] != "assistant":
        return jsonify({"error": "Yeniden üretilecek AI yanıtı bulunamadı."}), 400

    data = request.json or {}
    model_id = data.get("model_id")
    model_obj = (
        next((m for m in DB["models"] if m["id"] == model_id and m["type"] == "chat"), None)
        or next((m for m in DB["models"] if m["type"] == "chat" and m.get("active", True)), None)
    )

    ok, err, _ = check_and_deduct_credit(user, model_obj)
    if not ok:
        return jsonify({"error": err}), 403

    char = next((c for c in DB["characters"] if c["id"] == chat["character_id"]), None)
    last_msg = chat["messages"][-1]

    temp_chat_copy = dict(chat)
    temp_chat_copy["messages"] = chat["messages"][:-1]

    try:
        prompt_msgs = build_rp_prompt_messages(user, char, temp_chat_copy)
        ai_reply = call_llm_api(prompt_msgs, model_obj["api_model_id"], model_obj.get("endpoint_override", ""))
    except Exception as e:
        refund_credit(user, model_obj)
        return jsonify({"error": str(e)}), 500

    if "swipes" not in last_msg:
        last_msg["swipes"] = [last_msg["content"]]
    last_msg["swipes"].append(ai_reply)
    last_msg["active_swipe"] = len(last_msg["swipes"]) - 1
    last_msg["content"] = ai_reply
    save_db()
    return jsonify({"success": True, "chat": chat, "credits": user["credits"]})


@app.route("/api/rp/chats/<chat_id>/swipe", methods=["POST"])
@login_required
def api_swipe_rp_message(chat_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or chat["user"] != user["username"]:
        return jsonify({"error": "Sohbet bulunamadı."}), 404

    data = request.json or {}
    msg_id = data.get("msg_id")
    direction = int(data.get("direction", 1))

    for m in chat["messages"]:
        if m["id"] == msg_id and "swipes" in m and len(m["swipes"]) > 1:
            idx = (m.get("active_swipe", 0) + direction) % len(m["swipes"])
            m["active_swipe"] = idx
            m["content"] = m["swipes"][idx]
            save_db()
            return jsonify({"success": True, "chat": chat})

    return jsonify({"error": "Alternatif yanıt bulunamadı."}), 400


@app.route("/api/rp/chats/<chat_id>/message/<msg_id>", methods=["PUT", "DELETE"])
@login_required
def api_edit_or_delete_rp_message(chat_id, msg_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or chat["user"] != user["username"]:
        return jsonify({"error": "Sohbet bulunamadı."}), 404

    if request.method == "DELETE":
        chat["messages"] = [m for m in chat["messages"] if m["id"] != msg_id]
        save_db()
        return jsonify({"success": True, "chat": chat})

    data = request.json or {}
    new_content = (data.get("content") or "").strip()
    for m in chat["messages"]:
        if m["id"] == msg_id:
            m["content"] = new_content
            m["swipes"] = [new_content]
            m["active_swipe"] = 0
            save_db()
            return jsonify({"success": True, "chat": chat})

    return jsonify({"error": "Mesaj bulunamadı."}), 404


@app.route("/api/assistant/send", methods=["POST"])
@login_required
def api_assistant_send():
    user = get_current_user()
    data = request.json or {}
    chat_id = data.get("chat_id")
    content = (data.get("content") or "").strip()
    model_id = data.get("model_id")

    if not content:
        return jsonify({"error": "Mesaj boş olamaz."}), 400

    model_obj = (
        next((m for m in DB["models"] if m["id"] == model_id and m["type"] == "chat"), None)
        or next((m for m in DB["models"] if m["type"] == "chat" and m.get("active", True)), None)
    )
    if not model_obj:
        return jsonify({"error": "Aktif dil modeli bulunamadı."}), 400

    ok, err, _ = check_and_deduct_credit(user, model_obj)
    if not ok:
        return jsonify({"error": err}), 403

    chat = DB["assistant_chats"].get(chat_id) if chat_id else None
    if not chat:
        chat_id = "ast_" + uuid.uuid4().hex[:8]
        chat = {
            "id": chat_id,
            "user": user["username"],
            "title": content[:32],
            "messages": [],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        DB["assistant_chats"][chat_id] = chat

    chat["messages"].append({"role": "user", "content": content})
    prompt_msgs = [{"role": "system", "content": "Sen yardımcı, zeki ve net yanıtlar veren bir AI asistansın."}] + chat["messages"][-20:]

    try:
        reply = call_llm_api(prompt_msgs, model_obj["api_model_id"], model_obj.get("endpoint_override", ""))
    except Exception as e:
        chat["messages"].pop()
        refund_credit(user, model_obj)
        return jsonify({"error": str(e)}), 500

    chat["messages"].append({"role": "assistant", "content": reply})
    chat["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_db()
    return jsonify({"success": True, "chat": chat, "credits": user["credits"]})


@app.route("/api/assistant/chats/<chat_id>", methods=["DELETE"])
@login_required
def api_delete_assistant_chat(chat_id):
    user = get_current_user()
    chat = DB["assistant_chats"].get(chat_id)
    if not chat or (chat["user"] != user["username"] and user.get("role") != "admin"):
        return jsonify({"error": "Sohbet bulunamadı."}), 404
    del DB["assistant_chats"][chat_id]
    save_db()
    return jsonify({"success": True})


def process_ai_commands_for_chat(content, room_list, user, room_type="global", target_user=None):
    if not (content.startswith("@txt ") or content.startswith("@img ") or content.startswith("@vid ")):
        return False

    api_key = (DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")).strip()
    prompt = content[5:].strip()
    if not prompt:
        return False

    if content.startswith("@txt "):
        model_obj = next((m for m in DB["models"] if m["type"] == "chat" and m.get("active", True)), None)
        ok, _, _ = check_and_deduct_credit(user, model_obj) if model_obj else (False, None, 0)
        if ok and model_obj:
            ctx = [{"role": "system", "content": "Sen sohbetteki bir AI asistansın. Odadaki kişiler [İsim]: mesaj şeklinde konuşur."}]
            for m in room_list[-15:]:
                if m.get("type") == "text" or "content" in m:
                    u_name = m.get("user") or m.get("sender")
                    ctx.append({"role": "user", "content": f"[{u_name}]: {m['content']}"})
                elif m.get("type") == "ai_text":
                    ctx.append({"role": "assistant", "content": m["content"]})
            try:
                reply = call_llm_api(ctx, model_obj["api_model_id"], model_obj.get("endpoint_override", ""))
                msg_obj = {
                    "id": ("gmsg_" if room_type == "global" else "dm_") + uuid.uuid4().hex[:8],
                    "user" if room_type == "global" else "sender": "NEXUS AI",
                    "type": "ai_text",
                    "content": reply,
                    "timestamp": datetime.now().strftime("%H:%M")
                }
                if room_type == "dm":
                    msg_obj["receiver"] = target_user
                room_list.append(msg_obj)
                save_db()
            except Exception:
                refund_credit(user, model_obj)
        return True

    elif content.startswith("@img "):
        model_obj = next((m for m in DB["models"] if m["type"] == "image" and m.get("active", True)), None)
        ok, _, _ = check_and_deduct_credit(user, model_obj) if model_obj else (False, None, 0)
        if ok and model_obj:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            endpoint = model_obj.get("endpoint_override") or DB["settings"].get("image_endpoint", "https://api.venice.ai/api/v1/image/generate")
            try:
                data_url, _ = smart_generate_image(endpoint, headers, model_obj["api_model_id"], prompt, "", "1:1")
                if data_url:
                    m_id, public_url, size = save_media_file_helper(data_url, "image")
                    DB.setdefault("media", {})[m_id] = {
                        "id": m_id, "user": user["username"], "type": "image", "mode": "chat_ai",
                        "prompt": prompt, "model": model_obj["name"], "aspect_ratio": "1:1",
                        "file_path": public_url, "size_kb": size, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    msg_obj = {
                        "id": ("gmsg_" if room_type == "global" else "dm_") + uuid.uuid4().hex[:8],
                        "user" if room_type == "global" else "sender": "NEXUS AI",
                        "type": "image", "content": prompt, "file_path": public_url,
                        "timestamp": datetime.now().strftime("%H:%M")
                    }
                    if room_type == "dm":
                        msg_obj["receiver"] = target_user
                        msg_obj["media_url"] = public_url
                    room_list.append(msg_obj)
                    save_db()
                else:
                    refund_credit(user, model_obj)
            except Exception:
                refund_credit(user, model_obj)
        return True

    elif content.startswith("@vid "):
        model_obj = next((m for m in DB["models"] if m["type"] == "video" and m.get("active", True)), None)
        ok, _, _ = check_and_deduct_credit(user, model_obj) if model_obj else (False, None, 0)
        if ok and model_obj:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            endpoint = model_obj.get("endpoint_override") or DB["settings"].get("video_endpoint", "https://api.venice.ai/api/v1/video/queue")
            try:
                data_url, _ = smart_generate_video(endpoint, headers, model_obj["api_model_id"], prompt, "", "16:9", "720p")
                if data_url:
                    m_id, public_url, size = save_media_file_helper(data_url, "video")
                    DB.setdefault("media", {})[m_id] = {
                        "id": m_id, "user": user["username"], "type": "video", "mode": "chat_ai",
                        "prompt": prompt, "model": model_obj["name"], "aspect_ratio": "16:9",
                        "file_path": public_url, "size_kb": size, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    msg_obj = {
                        "id": ("gmsg_" if room_type == "global" else "dm_") + uuid.uuid4().hex[:8],
                        "user" if room_type == "global" else "sender": "NEXUS AI",
                        "type": "video", "content": prompt, "file_path": public_url,
                        "timestamp": datetime.now().strftime("%H:%M")
                    }
                    if room_type == "dm":
                        msg_obj["receiver"] = target_user
                        msg_obj["media_url"] = public_url
                    room_list.append(msg_obj)
                    save_db()
                else:
                    refund_credit(user, model_obj)
            except Exception:
                refund_credit(user, model_obj)
        return True

    return False


@app.route("/api/global/sync", methods=["GET"])
@login_required
def api_global_sync():
    return jsonify({"success": True, "messages": DB.get("global_chat", [])[-50:]})


@app.route("/api/global/send", methods=["POST"])
@login_required
def api_global_send():
    user = get_current_user()
    data = request.json or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Mesaj boş."}), 400

    DB.setdefault("global_chat", [])
    user_msg = {
        "id": "gmsg_" + uuid.uuid4().hex[:8],
        "user": user["username"],
        "type": "text",
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M")
    }
    DB["global_chat"].append(user_msg)
    save_db()

    threading.Thread(target=process_ai_commands_for_chat, args=(content, DB["global_chat"], user, "global"), daemon=True).start()
    return jsonify({"success": True, "credits": user["credits"]})


@app.route("/api/global/message/<msg_id>", methods=["DELETE"])
@login_required
def api_global_delete_message(msg_id):
    user = get_current_user()
    msgs = DB.get("global_chat", [])
    target = next((m for m in msgs if m.get("id") == msg_id), None)
    if not target:
        return jsonify({"error": "Mesaj bulunamadı."}), 404
    if target.get("user") != user["username"] and user.get("role") != "admin":
        return jsonify({"error": "Yetkiniz yok."}), 403
    DB["global_chat"] = [m for m in msgs if m.get("id") != msg_id]
    save_db()
    return jsonify({"success": True})


def get_dm_room_key(u1, u2):
    return "::".join(sorted([u1, u2]))


@app.route("/api/dm/list", methods=["GET"])
@login_required
def api_dm_list():
    user = get_current_user()
    uname = user["username"]
    DB.setdefault("dms", {})
    users_info = []
    for u_key, u_obj in DB["users"].items():
        if u_key == uname or u_obj.get("banned"):
            continue
        rkey = get_dm_room_key(uname, u_key)
        room_msgs = DB["dms"].get(rkey, [])
        last_msg = room_msgs[-1] if room_msgs else None
        users_info.append({
            "username": u_key,
            "persona_name": u_obj.get("persona_name", u_key),
            "role": u_obj.get("role", "user"),
            "last_message": last_msg["content"][:40] if last_msg else "",
            "last_time": last_msg["timestamp"] if last_msg else ""
        })
    return jsonify({"success": True, "contacts": users_info})


@app.route("/api/dm/<target_user>", methods=["GET"])
@login_required
def api_dm_get_messages(target_user):
    user = get_current_user()
    if target_user not in DB["users"]:
        return jsonify({"error": "Kullanıcı bulunamadı."}), 404
    rkey = get_dm_room_key(user["username"], target_user)
    msgs = DB.setdefault("dms", {}).get(rkey, [])
    return jsonify({"success": True, "messages": msgs[-100:]})


@app.route("/api/dm/<target_user>/send", methods=["POST"])
@login_required
def api_dm_send_message(target_user):
    user = get_current_user()
    if target_user not in DB["users"]:
        return jsonify({"error": "Alıcı bulunamadı."}), 404
    data = request.json or {}
    content = (data.get("content") or "").strip()
    media_data = data.get("media_data")
    if not content and not media_data:
        return jsonify({"error": "Mesaj boş olamaz."}), 400

    media_url = ""
    if media_data:
        try:
            mtype = "video" if "video" in media_data[:30] else "image"
            _, media_url, _ = save_media_file_helper(media_data, mtype)
        except Exception:
            pass

    rkey = get_dm_room_key(user["username"], target_user)
    DB.setdefault("dms", {}).setdefault(rkey, [])

    msg_obj = {
        "id": "dm_" + uuid.uuid4().hex[:8],
        "sender": user["username"],
        "receiver": target_user,
        "content": content,
        "media_url": media_url,
        "timestamp": datetime.now().strftime("%H:%M")
    }
    DB["dms"][rkey].append(msg_obj)
    save_db()

    threading.Thread(
        target=process_ai_commands_for_chat,
        args=(content, DB["dms"][rkey], user, "dm", target_user),
        daemon=True
    ).start()
    return jsonify({"success": True, "message": msg_obj, "credits": user["credits"]})


@app.route("/api/dm/<target_user>/message/<msg_id>", methods=["DELETE"])
@login_required
def api_dm_delete_message(target_user, msg_id):
    user = get_current_user()
    rkey = get_dm_room_key(user["username"], target_user)
    msgs = DB.setdefault("dms", {}).get(rkey, [])
    target = next((m for m in msgs if m.get("id") == msg_id), None)
    if not target:
        return jsonify({"error": "Mesaj bulunamadı."}), 404
    if target.get("sender") != user["username"] and user.get("role") != "admin":
        return jsonify({"error": "Silme yetkiniz yok."}), 403
    DB["dms"][rkey] = [m for m in msgs if m.get("id") != msg_id]
    save_db()
    return jsonify({"success": True})


@app.route("/api/media/generate", methods=["POST"])
@login_required
def api_generate_media():
    user = get_current_user()
    data = request.json or {}
    media_type = data.get("type", "image")
    prompt = (data.get("prompt") or "").strip()
    negative_prompt = (data.get("negative_prompt") or "").strip()
    aspect_ratio = data.get("aspect_ratio", "1:1")
    resolution = data.get("resolution", "720p")
    model_id = data.get("model_id")
    trained_id = data.get("trained_id", "")
    raw_source = data.get("source_media") or ""
    source_media = clean_media_path(raw_source) if not str(raw_source).startswith("data:") else str(raw_source).strip()
    raw_sources = data.get("source_images") or []
    source_images = [
        clean_media_path(s) if not str(s).startswith("data:") else str(s).strip()
        for s in raw_sources if s
    ]
    if source_media and not source_images:
        source_images = [source_media]
    elif source_images and not source_media:
        source_media = source_images[0]
    strength = float(data.get("strength") or 0.65)

    # 422 Engelleyici parametreleri
    bypass_422 = bool(data.get("bypass_422", False)) and bool(source_media) and (media_type == "image")
    bypass_model_id = (data.get("bypass_model_id") or "").strip()

    if media_type == "image":
        if data.get("mode") == "char_ref":
            mode = "char_ref"
        elif source_media:
            mode = "img2img_422_bypass" if bypass_422 else "img2img"
        else:
            mode = "txt2img"
    else:
        if source_media:
            mode = "vid2vid" if ("mp4" in source_media[:40].lower() or source_media.startswith("data:video")) else "img2vid"
        else:
            mode = "txt2vid"

    if not prompt:
        return jsonify({"error": "Prompt alanı boş bırakılamaz."}), 400

    model_obj = (
        next((m for m in DB["models"] if m["id"] == model_id and m["type"] == media_type), None)
        or next((m for m in DB["models"] if m["type"] == media_type and m.get("active", True)), None)
    )
    if not model_obj:
        return jsonify({"error": f"Aktif bir {media_type} modeli bulunamadı."}), 400

    # 422 Engelleyici seçiliyse engelleyici modeli ve ekstra kredi maliyetini belirle
    extra_bypass_cost = 0
    bypass_api_model_id = "firered-image-edit"
    if bypass_422:
        bypass_model_obj = (
            next((m for m in DB["models"] if m["id"] == bypass_model_id and m["type"] == "image"), None)
            or next((m for m in DB["models"] if m.get("api_model_id") == "firered-image-edit"), None)
            or model_obj
        )
        bypass_api_model_id = bypass_model_obj.get("api_model_id", "firered-image-edit")
        base_bypass_fee = int(DB["settings"].get("bypass_422_base_credit", 85))
        extra_bypass_cost = base_bypass_fee + int(bypass_model_obj.get("cost", 15))

    ok, err, _ = check_and_deduct_credit(user, model_obj, extra_cost=extra_bypass_cost)
    if not ok:
        return jsonify({"error": err}), 403

    final_prompt = prompt
    if trained_id:
        tm = next((t for t in DB["trained_models"] if t["id"] == trained_id), None)
        if tm:
            final_prompt = f"{tm.get('trigger_word', '')}, {prompt} ({tm.get('training_data', '')[:100]})"

    api_key = (DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")).strip()
    if not api_key:
        refund_credit(user, model_obj, extra_cost=extra_bypass_cost)
        return jsonify({"error": "Venice API Anahtarı bulunamadı!"}), 400

    endpoint = model_obj.get("endpoint_override") or (
        DB["settings"].get("image_endpoint", "https://api.venice.ai/api/v1/image/generate")
        if media_type == "image"
        else DB["settings"].get("video_endpoint", "https://api.venice.ai/api/v1/video/queue")
    )
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        if media_type == "image":
            data_url, api_err = smart_generate_image(
                endpoint,
                headers,
                model_obj["api_model_id"],
                final_prompt,
                negative_prompt,
                aspect_ratio,
                source_media=source_media,
                strength=strength,
                bypass_422=bypass_422,
                bypass_model_api_id=bypass_api_model_id,
                source_images=source_images
            )
        else:
            data_url, api_err = smart_generate_video(
                endpoint,
                headers,
                model_obj["api_model_id"],
                final_prompt,
                negative_prompt,
                aspect_ratio,
                resolution=resolution,
                source_media=source_media,
                strength=strength
            )

        if api_err or not data_url:
            refund_credit(user, model_obj, extra_cost=extra_bypass_cost)
            return jsonify({"error": api_err or "Medya üretilemedi, krediniz iade edildi."}), 400
    except Exception as e:
        refund_credit(user, model_obj, extra_cost=extra_bypass_cost)
        return jsonify({"error": f"API Bağlantı Hatası: {str(e)}"}), 500

    try:
        media_id, public_url, size_kb = save_media_file_helper(data_url, media_type)
    except Exception as e:
        refund_credit(user, model_obj, extra_cost=extra_bypass_cost)
        return jsonify({"error": f"Dosya kayıt hatası: {str(e)}"}), 500

    media_item = {
        "id": media_id,
        "user": user["username"],
        "type": media_type,
        "mode": mode,
        "prompt": final_prompt,
        "model": model_obj["name"],
        "aspect_ratio": aspect_ratio,
        "file_path": public_url,
        "size_kb": size_kb,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    DB.setdefault("media", {})[media_id] = media_item
    save_db()

    return jsonify({
        "success": True,
        "media": media_item | {"preview_url": public_url},
        "credits": user["credits"]
    })


@app.route("/static/media/<path:filename>", methods=["GET"])
def serve_media_fallback(filename):
    safe_name = os.path.basename(filename)
    filepath = os.path.join(MEDIA_DIR, safe_name)
    if os.path.exists(filepath):
        return send_file(filepath)
    mime_type, raw_bytes = get_media_blob_from_pg(safe_name)
    if raw_bytes:
        try:
            with open(filepath, "wb") as f:
                f.write(raw_bytes)
        except Exception:
            pass
        return Response(raw_bytes, mimetype=mime_type or "application/octet-stream")
    return "Medya bulunamadı.", 404


@app.route("/api/media/download/<media_id>", methods=["GET"])
@login_required
def api_download_media(media_id):
    m = DB.get("media", {}).get(media_id)
    if not m:
        return "Medya veritabanında bulunamadı.", 404
    filename = os.path.basename(clean_media_path(m["file_path"]))
    filepath = os.path.join(MEDIA_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    mime_type, raw_bytes = get_media_blob_from_pg(filename)
    if raw_bytes:
        return send_file(BytesIO(raw_bytes), mimetype=mime_type or "application/octet-stream", as_attachment=True, download_name=filename)
    return "Dosya bulunamadı.", 404


@app.route("/api/admin/state", methods=["GET"])
@admin_required
def api_admin_state():
    ram_items = []
    for cid, c in DB["chats"].items():
        sz = round(len(json.dumps(c, ensure_ascii=False).encode("utf-8")) / 1024.0, 2)
        ram_items.append({"id": cid, "category": "rp_chat", "size_kb": sz, "label": f"RP: {c.get('title')} ({c.get('user')})"})
    for aid, a in DB["assistant_chats"].items():
        sz = round(len(json.dumps(a, ensure_ascii=False).encode("utf-8")) / 1024.0, 2)
        ram_items.append({"id": aid, "category": "assistant_chat", "size_kb": sz, "label": f"Ast: {a.get('title')} ({a.get('user')})"})
    for mid, m in DB.get("media", {}).items():
        fp = clean_media_path(m.get("file_path", ""))
        ram_items.append({"id": mid, "category": "db_media", "size_kb": m.get("size_kb", 0), "preview_url": fp, "media_type": m.get("type", "image"), "label": f"Medya: {m.get('prompt', '')[:45]}... ({m.get('user')})"})

    return jsonify({"ram_usage_mb": get_ram_usage_mb(), "ram_limit_mb": 512, "db": DB, "ram_items": ram_items})


@app.route("/api/admin/settings", methods=["POST"])
@admin_required
def api_admin_update_settings():
    for k, v in (request.json or {}).get("settings", {}).items():
        if str(k).strip():
            DB["settings"][str(k).strip()] = str(v)
    save_db()
    return jsonify({"success": True, "settings": DB["settings"]})


@app.route("/api/admin/settings/<key>", methods=["DELETE"])
@admin_required
def api_admin_delete_setting(key):
    if key in DB["settings"]:
        del DB["settings"][key]
        save_db()
    return jsonify({"success": True})


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def api_admin_save_user():
    data = request.json or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "Kullanıcı adı gerekli."}), 400

    existing = DB["users"].get(username, {})
    allowed = data.get("allowed_models", ["*"])
    if isinstance(allowed, str):
        allowed = [x.strip() for x in allowed.split(",") if x.strip()] or ["*"]

    DB["users"][username] = {
        "username": username,
        "password": "1234" if username == "Admin" else (data.get("password") or existing.get("password") or "1234"),
        "role": "admin" if username == "Admin" else data.get("role", existing.get("role", "user")),
        "credits": int(data.get("credits", existing.get("credits", 100))),
        "char_limit": int(data.get("char_limit", existing.get("char_limit", 3))),
        "train_limit": int(data.get("train_limit", existing.get("train_limit", 1))),
        "allowed_models": allowed,
        "banned": False if username == "Admin" else bool(data.get("banned", existing.get("banned", False))),
        "persona_name": existing.get("persona_name", username),
        "persona_desc": existing.get("persona_desc", "Maceracı"),
        "created_at": existing.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    }
    save_db()
    return jsonify({"success": True})


@app.route("/api/admin/users/<username>", methods=["DELETE"])
@admin_required
def api_admin_delete_user(username):
    if username == "Admin":
        return jsonify({"error": "Kurucu hesap silinemez!"}), 400
    if username in DB["users"]:
        del DB["users"][username]
        save_db()
    return jsonify({"success": True})


@app.route("/api/admin/models", methods=["POST"])
@admin_required
def api_admin_save_model():
    data = request.json or {}
    mid = data.get("id") or ("mdl_" + uuid.uuid4().hex[:6])
    model_obj = {
        "id": mid,
        "name": (data.get("name") or "Yeni Model").strip(),
        "api_model_id": (data.get("api_model_id") or "venice-uncensored").strip(),
        "type": data.get("type", "chat"),
        "cost": int(data.get("cost", 1)),
        "endpoint_override": (data.get("endpoint_override") or "").strip(),
        "active": bool(data.get("active", True))
    }
    replaced = False
    for i, m in enumerate(DB["models"]):
        if m["id"] == mid:
            DB["models"][i] = model_obj
            replaced = True
            break
    if not replaced:
        DB["models"].append(model_obj)
    save_db()
    return jsonify({"success": True})


@app.route("/api/admin/models/<mid>", methods=["DELETE"])
@admin_required
def api_admin_delete_model(mid):
    DB["models"] = [m for m in DB["models"] if m["id"] != mid]
    save_db()
    return jsonify({"success": True})


@app.route("/api/admin/ram/delete", methods=["POST"])
@admin_required
def api_admin_ram_delete():
    data = request.json or {}
    cat, iid = data.get("category"), data.get("id")
    if cat in ["temp_media", "db_media"]:
        if iid == "ALL":
            for m in DB.get("media", {}).values():
                try:
                    os.remove(os.path.join(MEDIA_DIR, os.path.basename(clean_media_path(m["file_path"]))))
                except Exception:
                    pass
            DB["media"] = {}
        elif iid in DB.get("media", {}):
            try:
                os.remove(os.path.join(MEDIA_DIR, os.path.basename(clean_media_path(DB["media"][iid]["file_path"]))))
            except Exception:
                pass
            del DB["media"][iid]
    elif cat == "rp_chat" and iid in DB["chats"]:
        del DB["chats"][iid]
    elif cat == "assistant_chat" and iid in DB["assistant_chats"]:
        del DB["assistant_chats"][iid]
    save_db()
    return jsonify({"success": True})


@app.route("/api/admin/db/export", methods=["GET"])
@admin_required
def api_admin_export_db():
    json_bytes = json.dumps(DB, ensure_ascii=False, indent=2).encode("utf-8")
    return send_file(
        BytesIO(json_bytes),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"nexus_db_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    )


@app.route("/api/admin/db/import", methods=["POST"])
@admin_required
def api_admin_import_db():
    global DB
    loaded = json.load(request.files["file"]) if "file" in request.files else request.json
    if not isinstance(loaded, dict) or "settings" not in loaded:
        return jsonify({"error": "Geçersiz JSON formatı!"}), 400

    existing_media = DB.get("media", {})
    loaded = ensure_db_compatibility(loaded)
    if existing_media:
        for mid, m in existing_media.items():
            loaded.setdefault("media", {}).setdefault(mid, m)

    with db_lock:
        DB = loaded
        sync_disk_media_to_db()
        save_db_unlocked()
    return jsonify({"success": True})


@app.route("/api/admin/media/export", methods=["GET"])
@admin_required
def api_admin_export_media():
    bundle = {
        "bundle_type": "nexus_media_backup",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "media": {}
    }
    for mid, m in DB.get("media", {}).items():
        entry = dict(m)
        fname = os.path.basename(clean_media_path(m.get("file_path", "")))
        fpath = os.path.join(MEDIA_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "rb") as f:
                    entry["file_b64"] = base64.b64encode(f.read()).decode("utf-8")
                    entry["filename"] = fname
            except Exception:
                pass
        bundle["media"][mid] = entry
    return send_file(
        BytesIO(json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"nexus_media_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    )


@app.route("/api/admin/media/import", methods=["POST"])
@admin_required
def api_admin_import_media():
    loaded = json.load(request.files["file"]) if "file" in request.files else request.json
    m_dict = loaded.get("media") if isinstance(loaded, dict) and "media" in loaded else loaded
    if not isinstance(m_dict, dict):
        return jsonify({"error": "Medya verisi bulunamadı!"}), 400
    c = 0
    with db_lock:
        DB.setdefault("media", {})
        for mid, m in m_dict.items():
            if not isinstance(m, dict) or "type" not in m:
                continue
            entry = dict(m)
            b64_str = entry.pop("file_b64", None)
            fname = clean_media_path(entry.pop("filename", None) or os.path.basename(entry.get("file_path", f"nexus_{mid}.png")))
            if b64_str:
                try:
                    with open(os.path.join(MEDIA_DIR, fname), "wb") as wf:
                        wf.write(base64.b64decode(b64_str))
                except Exception as e:
                    print(f"[MEDYA YAZMA HATASI]: {e}")
            entry["file_path"] = f"/static/media/{fname}"
            DB["media"][mid] = entry
            c += 1
        save_db_unlocked()
    return jsonify({"success": True, "restored_count": c})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
