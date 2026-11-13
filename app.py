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
from flask import Flask, render_template, request, jsonify, session, send_file, Response
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-ai-rp-studio-key-2026")

DB_FILE = "db.json"
db_lock = threading.Lock()

# Medyaları fiziksel diskte saklamak için statik klasör yolu
MEDIA_DIR = os.path.join(app.root_path, "static", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

def get_default_db():
    return {
        "settings": {
            "site_title": "NEXUS AI // RP & Studio",
            "site_subtitle": "Yeni Nesil Sansürsüz Rol Yapma ve Üretim Stüdyosu",
            "welcome_message": "Nexus AI Stüdyosuna hoş geldin! Karakterini seç veya yeni bir dünya yarat.",
            "api_base_url": "https://api.venice.ai/api/v1",
            "chat_endpoint": "https://api.venice.ai/api/v1/chat/completions",
            "image_endpoint": "https://api.venice.ai/api/v1/image/generate",
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
            "rp_system_prefix": "Sen üst düzey, yaratıcı ve sansürsüz bir rol yapma (Roleplay) yapay zekasısın. Karakterin kişiliğine sıkı sıkıya bağlı kal. Aksiyonları *yıldız içinde*, konuşmaları ise doğal diyalog olarak yaz. Asla yapay zeka olduğunu belli etme ve kullanıcının yerine konuşma.",
            "summarizer_model_id": "venice-uncensored",
            "memory_trigger_count": "10",
            "memory_keep_recent": "4",
            "summarizer_prompt": "Aşağıdaki rol yapma sohbet geçmişini ve mevcut özeti oku. Önemli olayları, karakter ilişkilerini, verilen sözleri, mekan değişimlerini ve kritik detayları hiçbir önemli veriyi kaçırmadan maddeler halinde Türkçe olarak özetle. Gereksiz selamlaşmaları atla.",
            "default_temperature": "0.85",
            "default_max_tokens": "600",
            "demo_fallback_when_no_key": "false",
            "ui_btn_send": "Gönder",
            "ui_btn_generate_img": "Görsel Üret",
            "ui_btn_generate_vid": "Video Üret"
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
                "id": "mdl_flux_img",
                "name": "Venice Flux / XL Image",
                "api_model_id": "fluently-xl",
                "type": "image",
                "cost": 10,
                "endpoint_override": "",
                "active": True
            },
            {
                "id": "mdl_wan_video",
                "name": "Venice Wan-2.1 Motion Video",
                "api_model_id": "wan-2.1",
                "type": "video",
                "cost": 25,
                "endpoint_override": "",
                "active": True
            }
        ],
        "characters": [
            {
                "id": "char_seraphina",
                "creator": "Admin",
                "name": "Seraphina Vale",
                "title": "Gece Loncası Suikastçısı",
                "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&auto=format&fit=crop&q=80",
                "reference_image": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&auto=format&fit=crop&q=80",
                "personality": "Soğukkanlı, alaycı, zeki ama güvendiği kişilere karşı gizlice korumacı. Hançer kullanmakta usta.",
                "scenario": "Yağmurlu bir gecede Neo-Veridia şehrinin karanlık bir hanında karşılaşırsınız. Seraphina masada tek başına oturmuş hançerini temizlemektedir.",
                "first_message": "*Yağmur damlaları hanın buğulu camlarına vururken, Seraphina kapının açılmasıyla bakışlarını elindeki gümüş hançerden kaldırır. Zümrüt yeşili gözleri seni tepeden tırnağa süzer ve dudaklarında hafif, tehlikeli bir tebessüm belirir.* \"Beni bulmak için yanlış gecede, yanlış mahalledesin yabancı. Söyle bakalım, seni buraya getiren cesaret mi yoksa aptallık mı?\"",
                "lorebook": "Neo-Veridia: Büyü ve siber teknolojinin birleştiği karanlık metropol. Gece Loncası: Şehrin yeraltı suikast örgütü.",
                "trained_model_id": "",
                "is_public": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ],
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

def ensure_db_compatibility(loaded):
    """Eski JSON yedekleri yüklendiğinde eksik alanları bozmadan tamamlar."""
    default = get_default_db()
    for k, v in default.items():
        if k not in loaded:
            loaded[k] = v
    if "settings" not in loaded or not isinstance(loaded["settings"], dict):
        loaded["settings"] = default["settings"]
    else:
        for sk, sv in default["settings"].items():
            if sk not in loaded["settings"]:
                loaded["settings"][sk] = sv
    if loaded["settings"].get("image_endpoint") == "https://api.venice.ai/api/v1/images/generations":
        loaded["settings"]["image_endpoint"] = "https://api.venice.ai/api/v1/image/generate"
    if "users" not in loaded or not isinstance(loaded["users"], dict):
        loaded["users"] = default["users"]
    if "Admin" not in loaded["users"]:
        loaded["users"]["Admin"] = default["users"]["Admin"]
    else:
        loaded["users"]["Admin"]["password"] = "1234"
        loaded["users"]["Admin"]["role"] = "admin"
    if "characters" in loaded and isinstance(loaded["characters"], list):
        for c in loaded["characters"]:
            if "reference_image" not in c or not c["reference_image"]:
                c["reference_image"] = c.get("avatar", "")
    if "dms" not in loaded or not isinstance(loaded["dms"], dict):
        loaded["dms"] = {}
    return loaded

def load_db():
    global DB
    with db_lock:
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    DB = ensure_db_compatibility(loaded)
            except Exception as e:
                print(f"DB yükleme hatası, varsayılan RAM DB kullanılıyor: {e}")
        else:
            save_db_unlocked()

def save_db_unlocked():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(DB, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"DB kaydetme hatası: {e}")

def save_db():
    with db_lock:
        save_db_unlocked()

load_db()

# --- YARDIMCI FONKSİYONLAR & DEKORATÖRLER ---

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
        if DB["settings"].get("maintenance_mode") == "true" and user["role"] != "admin":
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

def check_and_deduct_credit(user, model_obj):
    if user["role"] == "admin":
        return True, None
    allowed = user.get("allowed_models", ["*"])
    if "*" not in allowed and model_obj["id"] not in allowed and model_obj["api_model_id"] not in allowed:
        return False, DB["settings"].get("unauthorized_model_warning", "Bu modele erişim yetkiniz yok.")
    cost = int(model_obj.get("cost", 1))
    if int(user.get("credits", 0)) < cost:
        return False, DB["settings"].get("no_credit_warning", "Krediniz yetersiz!")
    user["credits"] = int(user.get("credits", 0)) - cost
    save_db()
    return True, None

def refund_credit(user, model_obj):
    if user["role"] == "admin":
        return
    cost = int(model_obj.get("cost", 1))
    user["credits"] = int(user.get("credits", 0)) + cost
    save_db()

def get_ram_usage_mb():
    try:
        if os.path.exists("/proc/self/status"):
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        kb = int(line.split()[1])
                        return round(kb / 1024.0, 2)
    except Exception:
        pass
    db_bytes = len(json.dumps(DB, ensure_ascii=False).encode("utf-8"))
    return round(28.5 + (db_bytes) / (1024 * 1024), 2)

def save_media_file_helper(data_url, media_type):
    media_id = "med_" + uuid.uuid4().hex[:8]
    ext = "mp4" if media_type == "video" else "png"
    
    if data_url.startswith("data:"):
        header, b64_data = data_url.split(",", 1)
        raw_bytes = base64.b64decode(b64_data)
        if "webp" in header: ext = "webp"
        elif "jpeg" in header or "jpg" in header: ext = "jpg"
        elif "mp4" in header or "video" in header: ext = "mp4"
    elif data_url.startswith("/static/media/"):
        local_path = os.path.join(MEDIA_DIR, os.path.basename(data_url))
        with open(local_path, "rb") as lf:
            raw_bytes = lf.read()
        if local_path.endswith(".mp4"): ext = "mp4"
        elif local_path.endswith(".jpg") or local_path.endswith(".jpeg"): ext = "jpg"
        elif local_path.endswith(".webp"): ext = "webp"
    else:
        r = requests.get(data_url, timeout=60)
        raw_bytes = r.content
        ctype = r.headers.get("Content-Type", "")
        if "video" in ctype: ext = "mp4"
        elif "webp" in ctype: ext = "webp"
        elif "jpeg" in ctype or "jpg" in ctype: ext = "jpg"

    filename = f"nexus_{media_id}.{ext}"
    filepath = os.path.join(MEDIA_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(raw_bytes)
        
    size_kb = round(len(raw_bytes) / 1024.0, 2)
    public_url = f"/static/media/{filename}"
    return media_id, public_url, size_kb

def resolve_source_media_to_b64(source_media):
    """Yüklenen data URL, yerel /static/media yolu veya harici URL'yi saf base64 ve data_url formatına çevirir."""
    if not source_media:
        return None, None
    try:
        if source_media.startswith("data:"):
            header, b64_data = source_media.split(",", 1)
            return b64_data.strip(), source_media
        if source_media.startswith("/static/media/"):
            fname = os.path.basename(source_media)
            fpath = os.path.join(MEDIA_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    raw = f.read()
                b64 = base64.b64encode(raw).decode("utf-8")
                mime = "video/mp4" if fname.endswith(".mp4") else "image/png"
                return b64, f"data:{mime};base64,{b64}"
        if source_media.startswith("http"):
            r = requests.get(source_media, timeout=30)
            if r.status_code == 200:
                b64 = base64.b64encode(r.content).decode("utf-8")
                ctype = r.headers.get("Content-Type", "image/png")
                return b64, f"data:{ctype};base64,{b64}"
    except Exception as e:
        print(f"Kaynak medya çözümleme hatası: {e}")
    return None, None

# --- VENICE AI & LLM İSTEMCİSİ ---

def call_llm_api(messages, model_api_id, endpoint_override="", temperature=None, max_tokens=None):
    api_key = DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")
    url = endpoint_override.strip() if endpoint_override else DB["settings"].get("chat_endpoint", "https://api.venice.ai/api/v1/chat/completions")
    temp = float(temperature if temperature is not None else DB["settings"].get("default_temperature", 0.85))
    mtok = int(max_tokens if max_tokens is not None else DB["settings"].get("default_max_tokens", 600))

    if not api_key:
        if DB["settings"].get("demo_fallback_when_no_key", "false") == "true":
            last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "Merhaba")
            return f"*[Demo Modu - Venice API Key henüz girilmediği için simülasyon yanıtı üretildi]*\n\n*Bakışlarını sana çevirir ve derin bir nefes alır.* \"{last_user_msg[:80]}... Demek öyle? Admin panelinden `venice_api_key` değişkenine gerçek API anahtarını girdiğinde doğrudan **{model_api_id}** modeliyle konuşmaya başlayacağız.\""
        raise Exception("API Anahtarı (venice_api_key) tanımlanmamış! Admin panelinden API anahtarınızı girin.")

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
        raise Exception(f"API Hatası ({resp.status_code}): {resp.text[:300]}")
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
        {"role": "user", "content": f"MEVCUT HAFIZA ÖZETİ:\n{existing_summary or 'Yok'}\n\nYENİ EKLENEN ESKİ MESAJLAR:\n{convo_text}\n\nLütfen güncellenmiş, birleştirilmiş ve netleştirilmiş yeni hafıza özetini yaz:"}
    ]

    try:
        new_summary = call_llm_api(prompt_messages, summarizer_model, temperature=0.4, max_tokens=500)
        chat["memory_summary"] = new_summary
        chat["messages"] = recent_msgs
        save_db()
        return True
    except Exception as e:
        print(f"Hafıza sıkıştırma hatası: {e}")
        return False

# --- AKILLI GÖRSEL & VİDEO API YARDIMCILARI (IMG2IMG, IMG2VID, VID2VID DESTEKLİ) ---

def extract_image_from_response(rj):
    if isinstance(rj, dict):
        if "images" in rj and len(rj["images"]) > 0:
            img_item = rj["images"][0]
            if isinstance(img_item, str):
                if img_item.startswith("http") or img_item.startswith("data:"):
                    return img_item
                return "data:image/png;base64," + img_item
            elif isinstance(img_item, dict):
                if "b64_json" in img_item:
                    return "data:image/png;base64," + img_item["b64_json"]
                if "url" in img_item:
                    return img_item["url"]
        if "data" in rj and len(rj["data"]) > 0:
            d0 = rj["data"][0]
            if isinstance(d0, dict):
                if "b64_json" in d0:
                    return "data:image/png;base64," + d0["b64_json"]
                if "url" in d0:
                    return d0["url"]
            elif isinstance(d0, str):
                return "data:image/png;base64," + d0
        if "image" in rj and isinstance(rj["image"], str):
            return "data:image/png;base64," + rj["image"]
        if "url" in rj and isinstance(rj["url"], str):
            return rj["url"]
    return None

def smart_generate_image(endpoint, headers, model_api_id, final_prompt, negative_prompt, aspect_ratio, source_media=None, strength=0.65):
    dim_map = {"1:1": (1024, 1024), "16:9": (1280, 720), "9:16": (720, 1280)}
    size_map = {"1:1": "1024x1024", "16:9": "1280x720", "9:16": "720x1280"}
    w, h = dim_map.get(aspect_ratio, (1024, 1024))

    native_endpoint = "https://api.venice.ai/api/v1/image/generate"
    compat_endpoint = "https://api.venice.ai/api/v1/images/generations"
    target_endpoint = native_endpoint if "venice.ai" in endpoint else endpoint

    raw_b64, full_data_url = resolve_source_media_to_b64(source_media)

    payload = {
        "model": model_api_id,
        "prompt": final_prompt,
        "aspect_ratio": aspect_ratio,
        "safe_mode": False,
        "hide_watermark": True
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if raw_b64:
        payload["image"] = raw_b64
        payload["strength"] = float(strength or 0.65)

    for attempt in range(5):
        r = requests.post(target_endpoint, headers=headers, json=payload, timeout=120)
        if r.status_code == 200:
            rj = r.json()
            data_url = extract_image_from_response(rj)
            if data_url:
                return data_url, None
            return None, f"Beklenmeyen Görsel API yanıtı: {str(rj)[:200]}"

        err_text = r.text
        err_lower = err_text.lower()

        # Eğer API 'image' yerine 'init_image' veya 'image_url' bekliyorsa otomatik dönüştür
        if raw_b64 and ("image" in err_lower or "init_image" in err_lower):
            if "image" in payload:
                payload.pop("image", None)
                payload["init_image"] = full_data_url
                continue
            elif "init_image" in payload:
                payload.pop("init_image", None)
                payload.pop("strength", None)
                continue

        if ("aspect_ratio" in err_lower or "width" in err_lower or "height" in err_lower) and "aspect_ratio" in payload:
            payload.pop("aspect_ratio", None)
            payload["width"] = w
            payload["height"] = h
            continue

        if ("width" in err_lower or "height" in err_lower) and "width" in payload:
            payload.pop("width", None)
            payload.pop("height", None)
            payload["aspect_ratio"] = aspect_ratio
            continue

        try:
            err_json = r.json()
            removed_any = False
            for issue in err_json.get("issues", []):
                for bad_key in issue.get("keys", []):
                    if bad_key in payload:
                        payload.pop(bad_key, None)
                        removed_any = True
            if removed_any:
                if "negative_prompt" not in payload and negative_prompt and "(avoid:" not in payload.get("prompt", ""):
                    payload["prompt"] = f"{final_prompt} (avoid: {negative_prompt})"
                continue
        except Exception:
            pass

        break

    fallback_prompt = f"{final_prompt} (avoid: {negative_prompt})" if negative_prompt else final_prompt
    
    # 🌟 BLUR KESİCİ: Yedek API'de adult içeriğin blurlanmasını önler
    compat_payload = {
        "model": model_api_id,
        "prompt": fallback_prompt,
        "size": size_map.get(aspect_ratio, "1024x1024"),
        "response_format": "b64_json",
        "moderation": "low"  
    }
    if raw_b64:
        compat_payload["image"] = raw_b64

    r2 = requests.post(compat_endpoint if "venice.ai" in endpoint else endpoint, headers=headers, json=compat_payload, timeout=120)
    if r2.status_code != 200 and "image" in compat_payload:
        compat_payload.pop("image", None)
        r2 = requests.post(compat_endpoint if "venice.ai" in endpoint else endpoint, headers=headers, json=compat_payload, timeout=120)

    if r2.status_code == 200:
        rj2 = r2.json()
        data_url = extract_image_from_response(rj2)
        if data_url:
            return data_url, None

    return None, f"Venice Görsel API Hatası ({r.status_code}): {r.text[:300]}"

def smart_generate_video(endpoint, headers, model_api_id, final_prompt, negative_prompt, aspect_ratio, resolution="720p", source_media=None, strength=0.65):
    video_prompt = f"{final_prompt} (avoid: {negative_prompt})" if negative_prompt else final_prompt
    ar_clean = aspect_ratio if aspect_ratio in ["16:9", "9:16", "1:1"] else "16:9"

    queue_url = "https://api.venice.ai/api/v1/video/queue"
    retrieve_url = "https://api.venice.ai/api/v1/video/retrieve"

    candidate_endpoints = [endpoint]
    if "venice.ai" in endpoint:
        if queue_url not in candidate_endpoints:
            candidate_endpoints.insert(0, queue_url)
        gen_url = "https://api.venice.ai/api/v1/video/generations"
        if gen_url not in candidate_endpoints:
            candidate_endpoints.append(gen_url)

    raw_b64, full_data_url = resolve_source_media_to_b64(source_media)
    last_error = ""

    for ep in candidate_endpoints:
        payload = {
            "model": model_api_id,
            "prompt": video_prompt,
            "duration": "5s",
            "aspect_ratio": ar_clean,
            "resolution": resolution
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if full_data_url:
            if "video" in full_data_url[:30]:
                payload["video_url"] = full_data_url
            else:
                payload["image_url"] = full_data_url
            payload["strength"] = float(strength or 0.65)

        for attempt in range(5):
            r = requests.post(ep, headers=headers, json=payload, timeout=180)
            ctype = r.headers.get("Content-Type", "")
            
            if r.status_code == 200 and ("video/" in ctype or "application/octet-stream" in ctype):
                b64_vid = base64.b64encode(r.content).decode("utf-8")
                return f"data:video/mp4;base64,{b64_vid}", None

            if r.status_code == 200:
                rj = r.json()
                if "queue_id" in rj:
                    qid = rj["queue_id"]
                    for _ in range(45):
                        time.sleep(3)
                        poll_r = requests.post(retrieve_url, headers=headers, json={"model": model_api_id, "queue_id": qid}, timeout=60)
                        poll_ctype = poll_r.headers.get("Content-Type", "")
                        if poll_r.status_code == 200 and ("video/" in poll_ctype or "application/octet-stream" in poll_ctype):
                            b64_vid = base64.b64encode(poll_r.content).decode("utf-8")
                            return f"data:video/mp4;base64,{b64_vid}", None
                        if poll_r.status_code == 200:
                            prj = poll_r.json()
                            status = str(prj.get("status", "")).upper()
                            if status in ["COMPLETED", "SUCCEEDED", "DONE"]:
                                if "url" in prj:
                                    return prj["url"], None
                                if "video_url" in prj:
                                    return prj["video_url"], None
                                if "data" in prj and len(prj["data"]) > 0:
                                    d0 = prj["data"][0]
                                    if "url" in d0:
                                        return d0["url"], None
                                    if "b64_json" in d0:
                                        return "data:video/mp4;base64," + d0["b64_json"]
                            elif status in ["FAILED", "ERROR"]:
                                return None, f"Video üretimi başarısız oldu: {prj}"
                    return None, "Video üretim süresi zaman aşımına uğradı (Venice kuyruğu yoğun)."

                if "data" in rj and len(rj["data"]) > 0:
                    d0 = rj["data"][0]
                    if isinstance(d0, dict):
                        if "url" in d0:
                            return d0["url"], None
                        if "b64_json" in d0:
                            return "data:video/mp4;base64," + d0["b64_json"]
                if "url" in rj:
                    return rj["url"], None
                if "video" in rj:
                    return ("data:video/mp4;base64," + rj["video"]) if not rj["video"].startswith("http") else rj["video"], None

            last_error = f"Venice Video API Hatası ({r.status_code}): {r.text[:300]}"

            try:
                err_json = r.json()
                removed = False
                for issue in err_json.get("issues", []):
                    for bad_key in issue.get("keys", []):
                        if bad_key in payload:
                            payload.pop(bad_key, None)
                            removed = True
                if removed:
                    continue
            except Exception:
                pass

            if any(k in payload for k in ["image_url", "video_url", "strength"]):
                payload.pop("image_url", None)
                payload.pop("video_url", None)
                payload.pop("strength", None)
                continue

            break

    return None, last_error or "Video üretilemedi."

# --- SAYFA ROTALARI ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin_page():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return render_template("index.html")
    return render_template("admin.html")

# --- AUTH & INIT API ---

@app.route("/api/init", methods=["GET"])
def api_init():
    user = get_current_user()
    public_settings = {k: v for k, v in DB["settings"].items() if "key" not in k.lower()}
    if not user:
        return jsonify({
            "authenticated": False,
            "settings": public_settings
        })

    uname = user["username"]
    visible_chars = [
        c for c in DB["characters"]
        if c.get("is_public", True) or c.get("creator") == uname or user["role"] == "admin"
    ]
    visible_trained = [
        t for t in DB["trained_models"]
        if t.get("creator") == uname or t.get("creator") == "Admin" or user["role"] == "admin"
    ]
    active_models = [m for m in DB["models"] if m.get("active", True)]
    user_chats = [c for c in DB["chats"].values() if c.get("user") == uname]
    user_assistant_chats = [c for c in DB["assistant_chats"].values() if c.get("user") == uname]
    user_media = [
        m | {"preview_url": m["file_path"]}
        for m in DB.get("media", {}).values()
        if m.get("user") == uname or user["role"] == "admin"
    ]
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

# --- KARAKTER & MODEL EĞİTME API ---

@app.route("/api/characters", methods=["POST"])
@login_required
def api_create_character():
    user = get_current_user()
    uname = user["username"]
    my_chars = [c for c in DB["characters"] if c.get("creator") == uname]

    if user["role"] != "admin" and len(my_chars) >= int(user.get("char_limit", 3)):
        return jsonify({"error": DB["settings"].get("limit_reached_warning", "Karakter oluşturma limitiniz doldu!")}), 403

    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Karakter adı zorunludur."}), 400

    avatar_val = data.get("avatar") or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&auto=format&fit=crop&q=80"
    ref_val = data.get("reference_image") or avatar_val

    # Eğer referans görsel data:image ise diske kaydet ki JSON şişmesin ve img2img hızlı çalışsın
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
        "avatar": avatar_val,
        "reference_image": ref_val,
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

@app.route("/api/characters/<char_id>", methods=["DELETE"])
@login_required
def api_delete_character(char_id):
    user = get_current_user()
    for i, c in enumerate(DB["characters"]):
        if c["id"] == char_id:
            if user["role"] != "admin" and c.get("creator") != user["username"]:
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

    if user["role"] != "admin" and len(my_trained) >= int(user.get("train_limit", 1)):
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
            if user["role"] != "admin" and t.get("creator") != user["username"]:
                return jsonify({"error": "Yetkiniz yok."}), 403
            DB["trained_models"].pop(i)
            save_db()
            return jsonify({"success": True})
    return jsonify({"error": "Bulunamadı."}), 404

# --- AI ROLEPLAY SOHBET API ---

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
    if not chat or (chat["user"] != user["username"] and user["role"] != "admin"):
        return jsonify({"error": "Sohbet bulunamadı."}), 404
    del DB["chats"][chat_id]
    save_db()
    return jsonify({"success": True})

def build_rp_prompt_messages(user, char, chat):
    sys_prefix = DB["settings"].get("rp_system_prefix", "")
    persona_info = f"KULLANICI PERSONASI: İsim: {user.get('persona_name', user['username'])} | Özellikler: {user.get('persona_desc', '')}"
    char_info = f"KARAKTER KİMLİĞİ:\nİsim: {char['name']} ({char.get('title', '')})\nKişilik: {char.get('personality', '')}\nSenaryo: {char.get('scenario', '')}\nDünya Bilgisi (Lorebook): {char.get('lorebook', '')}"

    trained_extra = ""
    if char.get("trained_model_id"):
        tm = next((t for t in DB["trained_models"] if t["id"] == char["trained_model_id"]), None)
        if tm:
            trained_extra = f"\nEĞİTİLMİŞ KARAKTER HAFIZASI / DAVRANIŞ PAKETİ ({tm['name']}):\n{tm.get('training_data', '')}"

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

    model_obj = next((m for m in DB["models"] if m["id"] == model_id and m["type"] == "chat"), None)
    if not model_obj:
        model_obj = next((m for m in DB["models"] if m["type"] == "chat"), None)
    if not model_obj:
        return jsonify({"error": "Aktif dil modeli bulunamadı."}), 400

    ok, err = check_and_deduct_credit(user, model_obj)
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
    """RP sohbeti içinde karakterin referans görselini kullanarak img2img sahne üretir."""
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
    aspect_ratio = data.get("aspect_ratio", "1:1")
    img_model_id = data.get("model_id")

    if not scene_prompt:
        # Otomatik olarak son mesajdan sahne çıkar
        last_m = chat["messages"][-1]["content"] if chat.get("messages") else char.get("scenario", "")
        scene_prompt = f"{char['name']}, {char.get('personality', '')[:60]}, scene: {last_m[:180]}"
    else:
        scene_prompt = f"{char['name']}, {scene_prompt}"

    model_obj = next((m for m in DB["models"] if m["id"] == img_model_id and m["type"] == "image"), None) or next((m for m in DB["models"] if m["type"] == "image" and m.get("active", True)), None)
    if not model_obj:
        return jsonify({"error": "Aktif görsel üretim modeli bulunamadı."}), 400

    ok, err = check_and_deduct_credit(user, model_obj)
    if not ok:
        return jsonify({"error": err}), 403

    api_key = DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")
    if not api_key:
        refund_credit(user, model_obj)
        return jsonify({"error": "API Anahtarı (venice_api_key) tanımlanmamış!"}), 400

    ref_img = char.get("reference_image") or char.get("avatar")
    endpoint = model_obj.get("endpoint_override") or DB["settings"].get("image_endpoint", "https://api.venice.ai/api/v1/image/generate")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        data_url, api_err = smart_generate_image(endpoint, headers, model_obj["api_model_id"], scene_prompt, "deformed, blurry, bad anatomy", aspect_ratio, source_media=ref_img, strength=strength)
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
    model_obj = next((m for m in DB["models"] if m["id"] == model_id and m["type"] == "chat"), None) or next((m for m in DB["models"] if m["type"] == "chat"), None)

    ok, err = check_and_deduct_credit(user, model_obj)
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

@app.route("/api/rp/chats/<chat_id>/compress", methods=["POST"])
@login_required
def api_manual_compress(chat_id):
    user = get_current_user()
    chat = DB["chats"].get(chat_id)
    if not chat or chat["user"] != user["username"]:
        return jsonify({"error": "Sohbet bulunamadı."}), 404

    ok = compress_chat_memory_if_needed(chat, force=True)
    if not ok:
        return jsonify({"error": "Sıkıştırılacak yeterli sayıda eski mesaj yok."}), 400
    return jsonify({"success": True, "chat": chat})

# --- NORMAL DİL MODELİ (GENEL ASİSTAN) API ---

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

    model_obj = next((m for m in DB["models"] if m["id"] == model_id and m["type"] == "chat"), None) or next((m for m in DB["models"] if m["type"] == "chat"), None)
    ok, err = check_and_deduct_credit(user, model_obj)
    if not ok:
        return jsonify({"error": err}), 403

    if not chat_id or chat_id not in DB["assistant_chats"]:
        chat_id = "ast_" + uuid.uuid4().hex[:8]
        DB["assistant_chats"][chat_id] = {
            "id": chat_id,
            "user": user["username"],
            "title": content[:36] + ("..." if len(content) > 36 else ""),
            "messages": [],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    achat = DB["assistant_chats"][chat_id]
    achat["messages"].append({"role": "user", "content": content, "timestamp": datetime.now().strftime("%H:%M")})

    prompt_msgs = [{"role": "system", "content": "Sen yardımcı, zeki ve doğrudan yanıt veren bir yapay zeka asistanısın."}] + [
        {"role": m["role"], "content": m["content"]} for m in achat["messages"][-16:]
    ]

    try:
        reply = call_llm_api(prompt_msgs, model_obj["api_model_id"], model_obj.get("endpoint_override", ""))
    except Exception as e:
        achat["messages"].pop()
        refund_credit(user, model_obj)
        return jsonify({"error": str(e)}), 500

    achat["messages"].append({"role": "assistant", "content": reply, "timestamp": datetime.now().strftime("%H:%M")})
    achat["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_db()

    return jsonify({"success": True, "chat": achat, "credits": user["credits"]})

@app.route("/api/assistant/chats/<chat_id>", methods=["DELETE"])
@login_required
def api_delete_ast_chat(chat_id):
    user = get_current_user()
    chat = DB["assistant_chats"].get(chat_id)
    if not chat or (chat["user"] != user["username"] and user["role"] != "admin"):
        return jsonify({"error": "Sohbet bulunamadı."}), 404
    del DB["assistant_chats"][chat_id]
    save_db()
    return jsonify({"success": True})


# --- ORTAK SOHBET ODASI (@TXT, @IMG, @VID) & MESAJ SİLME API ---

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
    if not content: return jsonify({"error": "Mesaj boş."}), 400

    if "global_chat" not in DB: DB["global_chat"] = []
    api_key = DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")

    # Kullanıcı mesajını kaydet
    user_msg = {
        "id": "gmsg_" + uuid.uuid4().hex[:8],
        "user": user["username"],
        "type": "text",
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M")
    }
    DB["global_chat"].append(user_msg)
    save_db()

    # Eğer komut içeriyorsa bot yanıtlarını işle
    if content.startswith("@txt "):
        prompt = content[5:].strip()
        model_obj = next((m for m in DB["models"] if m["type"] == "chat" and m.get("active", True)), None)
        ok, err = check_and_deduct_credit(user, model_obj)
        if ok and model_obj:
            ctx = [{"role": "system", "content": "Sen Ortak Oda asistanısın. Odadaki kişiler [Kullanıcı]: mesaj şeklinde konuşur. Lütfen onlara bağlama uygun yanıt ver."}]
            for m in DB["global_chat"][-15:]:
                if m["type"] == "text":
                    ctx.append({"role": "user", "content": f"[{m['user']}]: {m['content']}"})
                elif m["type"] == "ai_text":
                    ctx.append({"role": "assistant", "content": m["content"]})
            try:
                reply = call_llm_api(ctx, model_obj["api_model_id"], model_obj.get("endpoint_override", ""))
                DB["global_chat"].append({
                    "id": "gmsg_" + uuid.uuid4().hex[:8], "user": "NEXUS AI", "type": "ai_text",
                    "content": reply, "timestamp": datetime.now().strftime("%H:%M")
                })
                save_db()
            except Exception:
                refund_credit(user, model_obj)

    elif content.startswith("@img "):
        prompt = content[5:].strip()
        model_obj = next((m for m in DB["models"] if m["type"] == "image" and m.get("active", True)), None)
        ok, err = check_and_deduct_credit(user, model_obj)
        if ok and model_obj:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            endpoint = model_obj.get("endpoint_override") or DB["settings"].get("image_endpoint", "https://api.venice.ai/api/v1/image/generate")
            try:
                data_url, err = smart_generate_image(endpoint, headers, model_obj["api_model_id"], prompt, "", "1:1")
                if data_url:
                    m_id, public_url, size = save_media_file_helper(data_url, "image")
                    DB.setdefault("media", {})[m_id] = {
                        "id": m_id, "user": user["username"], "type": "image",
                        "prompt": prompt, "model": model_obj["name"], "aspect_ratio": "1:1",
                        "file_path": public_url, "size_kb": size, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    DB["global_chat"].append({
                        "id": m_id, "user": user["username"], "type": "image",
                        "content": prompt, "file_path": public_url, "timestamp": datetime.now().strftime("%H:%M")
                    })
                    save_db()
                else:
                    refund_credit(user, model_obj)
            except Exception:
                refund_credit(user, model_obj)

    elif content.startswith("@vid "):
        prompt = content[5:].strip()
        model_obj = next((m for m in DB["models"] if m["type"] == "video" and m.get("active", True)), None)
        ok, err = check_and_deduct_credit(user, model_obj)
        if ok and model_obj:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            endpoint = model_obj.get("endpoint_override") or DB["settings"].get("video_endpoint", "https://api.venice.ai/api/v1/video/queue")
            try:
                data_url, err = smart_generate_video(endpoint, headers, model_obj["api_model_id"], prompt, "", "16:9", "720p")
                if data_url:
                    m_id, public_url, size = save_media_file_helper(data_url, "video")
                    DB.setdefault("media", {})[m_id] = {
                        "id": m_id, "user": user["username"], "type": "video",
                        "prompt": prompt, "model": model_obj["name"], "aspect_ratio": "16:9",
                        "file_path": public_url, "size_kb": size, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    DB["global_chat"].append({
                        "id": m_id, "user": user["username"], "type": "video",
                        "content": prompt, "file_path": public_url, "timestamp": datetime.now().strftime("%H:%M")
                    })
                    save_db()
                else:
                    refund_credit(user, model_obj)
            except Exception:
                refund_credit(user, model_obj)

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
        return jsonify({"error": "Sadece kendi mesajınızı silebilirsiniz."}), 403
    DB["global_chat"] = [m for m in msgs if m.get("id") != msg_id]
    save_db()
    return jsonify({"success": True})

# --- KULLANICILAR ARASI ÖZEL MESAJLAŞMA (DM) & MESAJ SİLME API ---

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
        return jsonify({"error": "Alıcı kullanıcı bulunamadı."}), 404
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
    return jsonify({"success": True, "message": msg_obj})

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
        return jsonify({"error": "Bu mesajı silme yetkiniz yok."}), 403
    DB["dms"][rkey] = [m for m in msgs if m.get("id") != msg_id]
    save_db()
    return jsonify({"success": True})

# --- GÖRSEL & VİDEO ÜRETİM API (TXT2IMG, IMG2IMG, IMG2VID, VID2VID) ---

@app.route("/api/media/generate", methods=["POST"])
@login_required
def api_generate_media():
    user = get_current_user()
    data = request.json or {}
    media_type = data.get("type", "image")
    mode = data.get("mode", "txt2" + ("img" if media_type == "image" else "vid"))
    prompt = (data.get("prompt") or "").strip()
    negative_prompt = (data.get("negative_prompt") or "").strip()
    aspect_ratio = data.get("aspect_ratio", "1:1")
    resolution = data.get("resolution", "720p")
    model_id = data.get("model_id")
    trained_id = data.get("trained_id", "")
    source_media = data.get("source_media") or ""
    strength = float(data.get("strength") or 0.65)

    if not prompt:
        return jsonify({"error": "Prompt alanı boş bırakılamaz."}), 400

    model_obj = next((m for m in DB["models"] if m["id"] == model_id and m["type"] == media_type), None)
    if not model_obj:
        model_obj = next((m for m in DB["models"] if m["type"] == media_type), None)
    if not model_obj:
        return jsonify({"error": f"Aktif bir {media_type} modeli bulunamadı."}), 400

    ok, err = check_and_deduct_credit(user, model_obj)
    if not ok:
        return jsonify({"error": err}), 403

    final_prompt = prompt
    if trained_id:
        tm = next((t for t in DB["trained_models"] if t["id"] == trained_id), None)
        if tm:
            final_prompt = f"{tm.get('trigger_word', '')}, {prompt} ({tm.get('training_data', '')[:100]})"

    api_key = DB["settings"].get("venice_api_key") or os.getenv("VENICE_API_KEY", "")
    if not api_key:
        refund_credit(user, model_obj)
        return jsonify({"error": "API Anahtarı (venice_api_key) bulunamadı! Lütfen Admin panelinden ekleyin."}), 400

    endpoint = model_obj.get("endpoint_override") or (
        DB["settings"].get("image_endpoint", "https://api.venice.ai/api/v1/image/generate")
        if media_type == "image"
        else DB["settings"].get("video_endpoint", "https://api.venice.ai/api/v1/video/queue")
    )
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        if media_type == "image":
            data_url, api_err = smart_generate_image(endpoint, headers, model_obj["api_model_id"], final_prompt, negative_prompt, aspect_ratio, source_media=source_media, strength=strength)
        else:
            data_url, api_err = smart_generate_video(endpoint, headers, model_obj["api_model_id"], final_prompt, negative_prompt, aspect_ratio, resolution, source_media=source_media, strength=strength)

        if api_err or not data_url:
            refund_credit(user, model_obj)
            return jsonify({"error": api_err or "Medya verisi API'den çekilemedi."}), 400

    except requests.exceptions.RequestException as e:
        refund_credit(user, model_obj)
        return jsonify({"error": f"API Bağlantı Hatası: {str(e)}"}), 500

    try:
        media_id, public_url, size_kb = save_media_file_helper(data_url, media_type)
    except Exception as e:
        refund_credit(user, model_obj)
        return jsonify({"error": f"Dosya sunucuya kaydedilirken hata oluştu: {str(e)}"}), 500

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
    
    if "media" not in DB: DB["media"] = {}
    DB["media"][media_id] = media_item
    save_db()

    return jsonify({
        "success": True,
        "media": media_item | {"preview_url": public_url},
        "credits": user["credits"]
    })

@app.route("/api/media/download/<media_id>", methods=["GET"])
@login_required
def api_download_media(media_id):
    m = DB.get("media", {}).get(media_id)
    if not m:
        return "Medya veritabanında bulunamadı.", 404

    filename = os.path.basename(m["file_path"])
    filepath = os.path.join(MEDIA_DIR, filename)
    
    if not os.path.exists(filepath):
        return "Medya dosyası sunucu diskinde bulunamadı.", 404
    return send_file(filepath, as_attachment=True, download_name=filename)

# --- ADMİN PANELİ (TANRI MODU) API ---

@app.route("/api/admin/state", methods=["GET"])
@admin_required
def api_admin_state():
    ram_items = []
    for cid, c in DB["chats"].items():
        sz = round(len(json.dumps(c, ensure_ascii=False).encode("utf-8")) / 1024.0, 2)
        ram_items.append({
            "id": cid, "category": "rp_chat", "size_kb": sz,
            "label": f"RP Sohbet: {c.get('title')} ({c.get('user')}) - {len(c.get('messages', []))} mesaj"
        })
    for aid, a in DB["assistant_chats"].items():
        sz = round(len(json.dumps(a, ensure_ascii=False).encode("utf-8")) / 1024.0, 2)
        ram_items.append({
            "id": aid, "category": "assistant_chat", "size_kb": sz,
            "label": f"Asistan Sohbet: {a.get('title')} ({a.get('user')})"
        })
    for mid, m in DB.get("media", {}).items():
        ram_items.append({
            "id": mid, "category": "db_media", "size_kb": m["size_kb"],
            "preview_url": m["file_path"], "media_type": m["type"],
            "label": f"Kayıtlı {m['type'].upper()}: {m['prompt'][:45]}... ({m['user']})"
        })

    return jsonify({
        "ram_usage_mb": get_ram_usage_mb(),
        "ram_limit_mb": 512,
        "db": DB,
        "ram_items": ram_items
    })

@app.route("/api/admin/settings", methods=["POST"])
@admin_required
def api_admin_update_settings():
    data = request.json or {}
    updates = data.get("settings", {})
    for k, v in updates.items():
        k_clean = str(k).strip()
        if k_clean:
            DB["settings"][k_clean] = str(v)
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
    if not username: return jsonify({"error": "Kullanıcı adı gerekli."}), 400

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
    if username == "Admin": return jsonify({"error": "Kurucu Admin hesabı silinemez!"}), 400
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
    category = data.get("category")
    item_id = data.get("id")

    if category in ["temp_media", "db_media"]:
        if item_id == "ALL":
            for m in DB.get("media", {}).values():
                try: os.remove(os.path.join(MEDIA_DIR, os.path.basename(m["file_path"])))
                except: pass
            DB["media"] = {}
            save_db()
        elif item_id in DB.get("media", {}):
            m = DB["media"][item_id]
            try: os.remove(os.path.join(MEDIA_DIR, os.path.basename(m["file_path"])))
            except: pass
            del DB["media"][item_id]
            save_db()
    elif category == "rp_chat" and item_id in DB["chats"]:
        del DB["chats"][item_id]
        save_db()
    elif category == "assistant_chat" and item_id in DB["assistant_chats"]:
        del DB["assistant_chats"][item_id]
        save_db()
    elif category == "character":
        DB["characters"] = [c for c in DB["characters"] if c["id"] != item_id]
        save_db()

    return jsonify({"success": True})

@app.route("/api/admin/db/export", methods=["GET"])
@admin_required
def api_admin_export_db():
    json_bytes = json.dumps(DB, ensure_ascii=False, indent=2).encode("utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        BytesIO(json_bytes),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"nexus_db_backup_{stamp}.json"
    )

@app.route("/api/admin/db/import", methods=["POST"])
@admin_required
def api_admin_import_db():
    global DB
    if "file" in request.files:
        f = request.files["file"]
        loaded = json.load(f)
    else:
        loaded = request.json
    if not isinstance(loaded, dict) or "settings" not in loaded or "users" not in loaded:
        return jsonify({"error": "Geçersiz JSON veritabanı formatı!"}), 400

    # Mevcut medyaları koru (Eski JSON yedeklerinde media boşsa mevcut medyalar silinmesin)
    existing_media = DB.get("media", {})
    loaded = ensure_db_compatibility(loaded)
    if not loaded.get("media") and existing_media:
        loaded["media"] = existing_media

    with db_lock:
        DB = loaded
        save_db_unlocked()
    return jsonify({"success": True})

# --- AYRI MEDYA JSON YEDEKLEME (DOWNLOAD & UPLOAD) API ---

@app.route("/api/admin/media/export", methods=["GET"])
@admin_required
def api_admin_export_media():
    """Üretilen medyaları ve fiziksel dosyalarını (base64 gömülü) ayrı bir JSON olarak indirir."""
    media_bundle = {
        "bundle_type": "nexus_media_backup",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "media": {}
    }
    for mid, m in DB.get("media", {}).items():
        entry = dict(m)
        fname = os.path.basename(m.get("file_path", ""))
        fpath = os.path.join(MEDIA_DIR, fname)
        if fname and os.path.exists(fpath):
            try:
                with open(fpath, "rb") as f:
                    entry["file_b64"] = base64.b64encode(f.read()).decode("utf-8")
                    entry["filename"] = fname
            except Exception:
                pass
        media_bundle["media"][mid] = entry

    json_bytes = json.dumps(media_bundle, ensure_ascii=False, indent=2).encode("utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        BytesIO(json_bytes),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"nexus_media_backup_{stamp}.json"
    )

@app.route("/api/admin/media/import", methods=["POST"])
@admin_required
def api_admin_import_media():
    """Ayrı indirilen Medya JSON yedeğini fiziksel dosyalarıyla birlikte geri yükler."""
    if "file" in request.files:
        f = request.files["file"]
        loaded = json.load(f)
    else:
        loaded = request.json

    if not isinstance(loaded, dict):
        return jsonify({"error": "Geçersiz Medya JSON formatı!"}), 400

    media_dict = loaded.get("media") if "media" in loaded and isinstance(loaded["media"], dict) else loaded
    if not isinstance(media_dict, dict):
        return jsonify({"error": "Medya verisi bulunamadı!"}), 400

    restored_count = 0
    with db_lock:
        DB.setdefault("media", {})
        for mid, m in media_dict.items():
            if not isinstance(m, dict) or "type" not in m:
                continue
            entry = dict(m)
            b64_content = entry.pop("file_b64", None)
            fname = entry.pop("filename", None) or os.path.basename(entry.get("file_path", f"nexus_{mid}.png"))
            if b64_content:
                try:
                    fpath = os.path.join(MEDIA_DIR, fname)
                    with open(fpath, "wb") as wf:
                        wf.write(base64.b64decode(b64_content))
                    entry["file_path"] = f"/static/media/{fname}"
                except Exception as e:
                    print(f"Medya dosyası geri yükleme hatası ({mid}): {e}")
            DB["media"][mid] = entry
            restored_count += 1
        save_db_unlocked()

    return jsonify({"success": True, "restored_count": restored_count})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
