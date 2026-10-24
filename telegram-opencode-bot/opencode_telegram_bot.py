#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت تيليغرام يربطك بـ OpenCode المثبت عندك في UserLAnd على هاتفك.
- ترسل مهمة من تيليغرام -> البوت يشغّل: opencode run --model <النموذج> "<المهمة>" داخل مجلد المشروع
- يرجع لك النتيجة في تيليغرام (العربية تظهر سليمة، بلا تقليب الحروف تاع التيرمينال)
- /models يعرض لك النماذج المجانية بأزرار كما في شاشة اختيار النموذج، واختيارك يتحفظ ويُستعمل في المهام
- يرد فقط على حسابك أنت (ALLOWED_USER_ID)

الإعداد: املأ ملف .env بجانب هذا السكربت:
    BOT_TOKEN=توكن البوت من BotFather
    ALLOWED_USER_ID=معرفك الرقمي في تيليغرام
    PROJECT_DIR=/home/retia44/projects/madrasati_ai

التشغيل:  python3 opencode_telegram_bot.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))

# النماذج المجانية كما تظهر في شاشة Select model عندك (OpenCode 1.19.4)
FREE_MODELS = [
    ("nemotron-3.5-super-vl-free", "Nemotron 3.5 Super VL Free"),
    ("beam-free", "Beam Free"),
    ("mimo-v2.6-flash-free", "MiMo-V2.6-Flash Free"),
    ("deepseek-v4.1-flash-free", "DeepSeek V4.1 Flash Free"),
    ("glm-5.3-flash-free", "GLM-5.3-Flash Free"),
    ("nemotron-3.5-lightning-free", "Nemotron 3.5 Lightning Free"),
    ("nemotron-3-ultra-free", "Nemotron 3 Ultra Free"),
    ("big-pickle", "Big Pickle"),
    ("flint-40b-free", "Flint 40B Free"),
]
MODEL_NAMES = dict(FREE_MODELS)
DEFAULT_MODEL = "big-pickle"
MODEL_STATE = os.path.join(HERE, "model.txt")


def load_model():
    try:
        with open(MODEL_STATE, encoding="utf-8") as f:
            m = f.read().strip()
        if m in MODEL_NAMES:
            return m
    except OSError:
        pass
    return DEFAULT_MODEL


def save_model(m):
    with open(MODEL_STATE, "w", encoding="utf-8") as f:
        f.write(m)


CURRENT_MODEL = load_model()


def load_env():
    env = {}
    path = os.path.join(HERE, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def first_run_setup():
    """إعداد تفاعلي عند أول تشغيل: يسأل عن التوكن والمعرف ويحفظهما في .env"""
    print("=== إعداد أول مرة ===")
    print("1) اخلق بوت عند @BotFather في تيليغرام (/newbot) وانسخ التوكن.")
    print("2) جيب معرفك الرقمي من @userinfobot.")
    token = input("الصق توكن البوت هنا: ").strip()
    allowed = input("الصق معرفك الرقمي هنا: ").strip()
    project = input(
        "مجلد المشروع الافتراضي [/home/retia44/projects/madrasati_ai]: "
    ).strip() or "/home/retia44/projects/madrasati_ai"
    with open(os.path.join(HERE, ".env"), "w", encoding="utf-8") as f:
        f.write(f"BOT_TOKEN={token}\nALLOWED_USER_ID={allowed}\nPROJECT_DIR={project}\n")
    print("تحفظ الإعداد في .env — البوت يبدا دروك.")
    return {"BOT_TOKEN": token, "ALLOWED_USER_ID": allowed, "PROJECT_DIR": project}


ENV = load_env()
if not ENV.get("BOT_TOKEN") or not ENV.get("ALLOWED_USER_ID"):
    ENV = first_run_setup()
TOKEN = ENV.get("BOT_TOKEN") or os.environ.get("BOT_TOKEN", "")
ALLOWED = ENV.get("ALLOWED_USER_ID") or os.environ.get("ALLOWED_USER_ID", "")
PROJECT_DIR = ENV.get("PROJECT_DIR") or os.environ.get(
    "PROJECT_DIR", os.path.expanduser("~/projects/madrasati_ai")
)
TIMEOUT = int(ENV.get("TASK_TIMEOUT", "1200"))  # أقصى مدة لمهمة واحدة (ثواني)
API = f"https://api.telegram.org/bot{TOKEN}"

if not TOKEN or not ALLOWED:
    sys.exit("خطأ: املأ BOT_TOKEN و ALLOWED_USER_ID في ملف .env بجانب السكربت")


def api(method, **params):
    data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/{method}", data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.loads(r.read().decode("utf-8"))


def send(chat_id, text, reply_markup=None):
    # تيليغرام يحد الرسالة بـ4096 حرف: نقسّم النص الطويل
    chunks = [text[i : i + 3900] for i in range(0, len(text), 3900)] or [""]
    for i, chunk in enumerate(chunks):
        try:
            params = {"chat_id": chat_id, "text": chunk}
            if reply_markup is not None and i == 0:
                params["reply_markup"] = reply_markup
            api("sendMessage", **params)
        except Exception as e:
            print("sendMessage error:", e, file=sys.stderr)
        time.sleep(0.4)


def models_keyboard():
    rows = []
    for mid, name in FREE_MODELS:
        label = ("✅ " if mid == CURRENT_MODEL else "") + name + " — Free"
        rows.append([{"text": label, "callback_data": f"model:{mid}"}])
    return {"inline_keyboard": rows}


def send_models(chat_id):
    send(
        chat_id,
        f"اختر النموذج (الحالي: {MODEL_NAMES[CURRENT_MODEL]}):",
        reply_markup=models_keyboard(),
    )


def handle_callback(cb):
    global CURRENT_MODEL
    user_id = str(cb.get("from", {}).get("id", ""))
    cb_id = cb.get("id")
    data = cb.get("data") or ""
    msg = cb.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")
    if user_id != str(ALLOWED):
        try:
            api("answerCallbackQuery", callback_query_id=cb_id, text="هذا البوت خاص بصاحبه فقط.")
        except Exception:
            pass
        return
    if data.startswith("model:"):
        mid = data.split(":", 1)[1]
        if mid in MODEL_NAMES:
            CURRENT_MODEL = mid
            save_model(mid)
            try:
                api("answerCallbackQuery", callback_query_id=cb_id,
                    text=f"تبدّل النموذج إلى {MODEL_NAMES[mid]}")
            except Exception:
                pass
            try:
                api("editMessageText", chat_id=chat_id, message_id=msg_id,
                    text=f"اختر النموذج (الحالي: {MODEL_NAMES[mid]}):",
                    reply_markup=models_keyboard())
            except Exception as e:
                print("editMessageText error:", e, file=sys.stderr)
            return
    try:
        api("answerCallbackQuery", callback_query_id=cb_id)
    except Exception:
        pass


def run_opencode(prompt, cwd):
    """يشغّل OpenCode بوضع غير تفاعلي بالنموذج المختار ويرجع المخرجات."""
    cmd = ["opencode", "run", "--model", f"opencode/{CURRENT_MODEL}", prompt]
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT
        )
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        if p.returncode != 0 and err:
            return f"خرج OpenCode بخطأ (code {p.returncode}):\n{err[-1500:]}"
        return out or "(بلا مخرجات)"
    except subprocess.TimeoutExpired:
        return f"المهمة فاقت {TIMEOUT} ثانية وتوقفت. قسّمها لأجزاء أصغر."
    except FileNotFoundError:
        return "ما لقيتش أمر opencode — تأكد أنه مثبت ويشتغل في التيرمينال: opencode --version"


def projects_root():
    return os.path.expanduser("~/projects")


def list_projects():
    root = projects_root()
    if not os.path.isdir(root):
        return []
    return sorted(
        d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))
    )


def handle(msg):
    global PROJECT_DIR
    chat_id = msg["chat"]["id"]
    user_id = str(msg.get("from", {}).get("id", ""))
    text = (msg.get("text") or "").strip()
    if user_id != str(ALLOWED):
        send(chat_id, "هذا البوت خاص بصاحبه فقط.")
        return
    if not text:
        return
    if text == "/start":
        send(
            chat_id,
            "أهلاً! أنا جسرك إلى OpenCode في هاتفك.\n"
            f"المشروع الحالي: {PROJECT_DIR}\n"
            f"النموذج الحالي: {MODEL_NAMES[CURRENT_MODEL]}\n\n"
            "ابعت أي مهمة كنص وسأشغّلها في OpenCode وأرجع لك النتيجة.\n"
            "أوامر:\n"
            "/models — اختيار النموذج بالأزرار\n"
            "/projects — قائمة المشاريع\n"
            "/project اسم_المشروع — تبديل المشروع\n"
            "/status — الحالة",
        )
        return
    if text == "/models":
        send_models(chat_id)
        return
    if text == "/projects":
        names = list_projects()
        send(chat_id, "المشاريع:\n" + ("\n".join("- " + n for n in names) or "لا يوجد"))
        return
    if text.startswith("/project"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            cand = os.path.join(projects_root(), parts[1].strip())
            if os.path.isdir(cand):
                PROJECT_DIR = cand
                send(chat_id, f"تبدّل المشروع إلى: {PROJECT_DIR}")
            else:
                send(chat_id, "ما لقيتش هذا المجلد تحت ~/projects")
        else:
            send(chat_id, f"المشروع الحالي: {PROJECT_DIR}")
        return
    if text == "/status":
        send(chat_id, f"خدام. المشروع: {PROJECT_DIR}\nالنموذج: {MODEL_NAMES[CURRENT_MODEL]}")
        return
    # أي نص آخر = مهمة لـ OpenCode
    send(chat_id, "استلمت المهمة، خدام عليها...")
    result = run_opencode(text, PROJECT_DIR)
    send(chat_id, result[-15000:])


def main():
    print("البوت خدام... المشروع:", PROJECT_DIR, "| النموذج:", CURRENT_MODEL)
    offset = None
    while True:
        try:
            params = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                params["offset"] = offset
            res = api("getUpdates", **params)
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                if upd.get("callback_query"):
                    handle_callback(upd["callback_query"])
                elif upd.get("message"):
                    handle(upd["message"])
        except urllib.error.URLError as e:
            print("network:", e, file=sys.stderr)
            time.sleep(5)
        except Exception as e:
            print("error:", e, file=sys.stderr)
            time.sleep(3)


if __name__ == "__main__":
    main()
