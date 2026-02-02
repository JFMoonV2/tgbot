import os
import asyncio
import random
import re
import math
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"

CIRCLE = "⚪️"

FINAL_DELETE_PROTOCOL = 0.8
FINAL_DELETE_DOX = 1.5

PERCENT_BASE = 0.020
PERCENT_MIN = 0.012
TEXT_BASE = 0.028
TEXT_MIN = 0.020

muted_chats = set()
owner_id_by_chat = {}

clean_mode = set()
emoji_mode = set()
ai_answers = set()

EMOJIS = ["😈", "💀", "🔥", "😏", "🤡", "🗿", "⚠️", "🧠", "🫠", "✨"]

BAD_PATTERNS = [
    r"\bбля(?:д[ьи])?\b",
    r"\bсука(?:ми|м|х)?\b",
    r"\bсучк[аиоы]?\b",
    r"\bхуй(?:ня|ню|не|ням|ни|й|я|е|ю)?\b",
    r"\bпизд(?:ец|а|у|е|ой|ы|ишь|ит|ёж|еж)?\b",
    r"\bеб(?:ал|ало|али|ать|у|ет|ё|ешь|ан|ану|анут|аш|ался|алась|ались)?\b",
    r"\bёб(?:ал|ало|али|ать|у|ет|ё|ешь|ан|ану|анут|аш|ался|алась|ались)?\b",
    r"\bпид(?:ор|орас|оры|ар|ары)?\b",
    r"\bгандон(?:ы|)\b",
    r"\bдолбо(?:ёб|еб)\b",
]
BAD_RE = re.compile("|".join(BAD_PATTERNS), flags=re.IGNORECASE | re.UNICODE)

DOX_LINES = [
    "IP: 92.28.211.234",
    "N: 43.7462",
    "W: 12.489",
    "SS Number: 697919918",
    "IPv6: fe80::5dcd::ef69::fb22::d9888%12",
    "DMZ: 10.12.45.123",
    "MAC: 5A:78:3E:7E:00",
    "ISP: United Networks",
    "DNS: 8.8.8.8",
    "DNS: 8.8.4.4",
    "WAN: 92.28.211.234",
    "WAN Type: Private",
    "Gateway: 102.168.1.1",
    "Subnet Mask: 255.255.255.0",
    "UPNP: ENABLED",
    "TCP OPEN PORTS: 8080, 80",
    "UDP OPEN PORTS: 53",
]

def cmd(t: str) -> str:
    return (t or "").strip()

def is_cmd(t: str, base: str) -> bool:
    t = cmd(t)
    return t == base or t.startswith(base + " ")

async def tg_post(method: str, payload: dict):
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(f"{API_BASE}/{method}", json=payload, timeout=8)
    except:
        pass

async def del_msgs(bcid, ids):
    if bcid and ids:
        await tg_post("deleteBusinessMessages", {"business_connection_id": bcid, "message_ids": ids})

async def edit_msg(bcid, chat_id, mid, text):
    if bcid:
        await tg_post("editMessageText", {
            "business_connection_id": bcid,
            "chat_id": chat_id,
            "message_id": mid,
            "text": text
        })

def mask_bad(text: str) -> str:
    return BAD_RE.sub(lambda m: "*" * len(m.group(0)), text)

def calc(expr: str) -> str:
    e = (expr or "").strip()
    if not e:
        return "Error"
    if re.search(r"[A-Za-zА-Яа-яЁё]", e):
        parts = [p.strip() for p in e.split("+")]
        parts = [p for p in parts if p]
        return " ".join(parts) if parts else "Error"
    if not re.fullmatch(r"[0-9\.\s\+\-\*\/\(\)\%\^]+", e):
        return "Error"
    e = e.replace("^", "**")
    try:
        return str(eval(e, {"__builtins__": None}, {"sqrt": math.sqrt}))
    except:
        return "Error"

def ai_ru(text: str) -> str:
    t = (text or "").strip()
    l = t.lower()

    if any(x in l for x in ["привет", "здар", "здравствуйте", "хай", "ку", "hello", "hi"]):
        return random.choice([
            "Привет 🙂 Как ты?",
            "Привет-привет! Как настроение?",
            "Привет 😄 Что нового?"
        ])

    if any(x in l for x in ["как дела", "как ты", "как жизнь"]):
        return random.choice([
            "Нормально 🙂 А у тебя как?",
            "Все окей. Ты как?",
            "Живу, работаю 😄 А у тебя?"
        ])

    if any(x in l for x in ["что делаешь", "чем занят", "чо делаешь"]):
        return random.choice([
            "Да так, своими делами. А ты?",
            "Ничего особенного 🙂 Ты что хотел?",
            "Сижу тут. А ты чем занят?"
        ])

    if any(x in l for x in ["спасибо", "пасиб", "благодарю"]):
        return random.choice([
            "Пожалуйста 🙂",
            "Всегда пожалуйста.",
            "Не за что 😄"
        ])

    if "?" in l:
        return random.choice([
            "Сложно ответить без деталей. Уточни 🙂",
            "Зависит от ситуации. Расскажи подробнее.",
            "Можешь переформулировать? Тогда отвечу точнее."
        ])

    if len(l) <= 3:
        return random.choice(["Окей.", "Ясно.", "Понял 🙂"])

    if any(x in l for x in ["лол", "ахаха", "хаха", "ржу"]):
        return random.choice([
            "Ахаха 😄",
            "Понимаю 😅",
            "Ну ты выдал 😄"
        ])

    return random.choice([
        "Понял тебя 🙂",
        "Окей, принял.",
        "Интересно. И что дальше?",
        "Хм. Ладно.",
        "Ясно. Давай по сути 🙂"
    ])

def rnd_inc():
    r = random.random()
    if r < 0.35: return 1
    if r < 0.70: return 2
    if r < 0.90: return 3
    return 4

async def sp():
    await asyncio.sleep(max(PERCENT_MIN, PERCENT_BASE + random.uniform(-0.006, 0.010)))

async def st():
    await asyncio.sleep(max(TEXT_MIN, TEXT_BASE + random.uniform(-0.008, 0.012)))

async def run_protocol(ctx, chat_id, bcid):
    m = await ctx.bot.send_message(chat_id, "Encrypting 1%", business_connection_id=bcid)

    p = 1
    while p < 100:
        await sp()
        p = min(100, p + rnd_inc())
        try:
            await m.edit_text(f"Encrypting {p}%")
        except:
            pass

    await st()
    try:
        await m.edit_text(f"{CIRCLE}Encrypting completed")
    except:
        pass

    loops = random.randint(3, 4)
    for _ in range(loops):
        for d in [".", "..", "..."]:
            await st()
            try:
                await m.edit_text(f"Opening json codec{d}")
            except:
                pass

    await st()
    try:
        await m.edit_text(f"{CIRCLE}Success")
    except:
        pass

    p = 29
    while p < 100:
        await sp()
        p = min(100, p + rnd_inc())
        try:
            await m.edit_text(f"Rematching data {p}%")
        except:
            pass

    await st()
    try:
        await m.edit_text(f"{CIRCLE}Successful")
    except:
        pass

    await asyncio.sleep(FINAL_DELETE_PROTOCOL)
    await del_msgs(bcid, [m.message_id])

async def run_dox(ctx, chat_id, bcid):
    text = DOX_LINES[0]
    m = await ctx.bot.send_message(chat_id, text, business_connection_id=bcid)
    for line in DOX_LINES[1:]:
        await asyncio.sleep(0.20)
        text += "\n" + line
        try:
            await m.edit_text(text)
        except:
            pass
    await asyncio.sleep(FINAL_DELETE_DOX)
    await del_msgs(bcid, [m.message_id])

async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not getattr(msg, "text", None):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)
    uid = msg.from_user.id
    text = cmd(msg.text)

    owner_id_by_chat.setdefault(chat_id, uid)
    owner = owner_id_by_chat[chat_id]

    if chat_id in muted_chats and uid != owner:
        await del_msgs(bcid, [msg.message_id])
        return

    if text.startswith("."):
        owner_id_by_chat[chat_id] = uid
        owner = uid

    if is_cmd(text, ".protocol"):
        await del_msgs(bcid, [msg.message_id])
        await run_protocol(ctx, chat_id, bcid)
        return

    if is_cmd(text, ".dox"):
        await del_msgs(bcid, [msg.message_id])
        await run_dox(ctx, chat_id, bcid)
        return

    if is_cmd(text, ".mute"):
        muted_chats.add(chat_id)
        await del_msgs(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, "Помолчи-ка, ты пока что в муте и не можешь писать", business_connection_id=bcid)
        return

    if is_cmd(text, ".unmute"):
        muted_chats.discard(chat_id)
        await del_msgs(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, "Все, можешь говорить <3", business_connection_id=bcid)
        return

    if text == ".clean on":
        clean_mode.add(chat_id)
        await del_msgs(bcid, [msg.message_id])
        return

    if text == ".clean off":
        clean_mode.discard(chat_id)
        await del_msgs(bcid, [msg.message_id])
        return

    if text == ".emoji on":
        emoji_mode.add(chat_id)
        await del_msgs(bcid, [msg.message_id])
        return

    if text == ".emoji off":
        emoji_mode.discard(chat_id)
        await del_msgs(bcid, [msg.message_id])
        return

    if text == ".aianswers on":
        ai_answers.add(chat_id)
        await del_msgs(bcid, [msg.message_id])
        return

    if text == ".aianswers off":
        ai_answers.discard(chat_id)
        await del_msgs(bcid, [msg.message_id])
        return

    if text.startswith(".calc"):
        expr = text[5:].strip()
        await ctx.bot.send_message(chat_id, f"Calc = {calc(expr)}", business_connection_id=bcid)
        return

    if chat_id in ai_answers and uid != owner:
        await ctx.bot.send_message(chat_id, ai_ru(text), business_connection_id=bcid)
        return

    if uid == owner:
        new = text
        if chat_id in clean_mode:
            new = mask_bad(new)
        if chat_id in emoji_mode:
            new = new + " " + random.choice(EMOJIS)
        if new != text:
            await edit_msg(bcid, chat_id, msg.message_id, new)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
