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

AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "llama-3.1-8b-instant").strip()

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

BAD_PATTERNS = [
    r"(?:^|(?<=\W))(?:бля|бляд|блять|блят)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:сука|сучк)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:хуй|хуё|хуе|хуя|хуи|хую)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:пизд|пезд)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:ебан|ёбан|ебал|ёбал|ебу|ёбу|ебёт|ёбёт|ебешь|ёбешь|ебанн|ёбанн)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:пидор|пидр|пидарас|пидарасина|педик)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:гандон)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:долбо(?:ёб|еб))(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:мраз)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:шлюх)(?:[а-яё]*)",
    r"(?:^|(?<=\W))(?:еблан)(?:[а-яё]*)",
]
BAD_RE = re.compile("|".join(BAD_PATTERNS), flags=re.IGNORECASE | re.UNICODE)

def cmd(t: str) -> str:
    return (t or "").strip()

def is_cmd(t: str, base: str) -> bool:
    t = cmd(t)
    return t == base or t.startswith(base + " ")

async def tg_post(method: str, payload: dict):
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(f"{API_BASE}/{method}", json=payload, timeout=12)
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

def mask_bad_regex(text: str) -> str:
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

async def llm_chat(messages, max_tokens=220, temperature=0.9):
    if not AI_API_KEY:
        return None
    url = AI_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    if "openrouter.ai" in AI_BASE_URL:
        headers["HTTP-Referer"] = "https://telegram.me/"
        headers["X-Title"] = "tg-business-bot"
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers, timeout=18) as r:
                j = await r.json()
                c = j.get("choices", [{}])[0].get("message", {}).get("content", "")
                c = (c or "").strip()
                return c or None
    except:
        return None

async def ai_answer_any(text: str):
    m = await llm_chat([
        {"role": "system", "content": "Ты дружелюбный собеседник. Отвечай на русском, естественно, коротко/средне. Без упоминаний, что ты бот. Отвечай на ЛЮБОЙ вопрос по смыслу. Если не хватает деталей — предположи и ответь, потом уточни одним вопросом."},
        {"role": "user", "content": text},
    ], max_tokens=260, temperature=0.95)
    return m or "Понял 🙂"

async def ai_pick_emoji(text: str):
    m = await llm_chat([
        {"role": "system", "content": "Выбери ОДИН эмодзи, который лучше всего подходит к сообщению по смыслу/настроению. Ответь только эмодзи, без текста."},
        {"role": "user", "content": text},
    ], max_tokens=8, temperature=0.7)
    if m:
        m = (m.strip().split() or [""])[0]
        if len(m) <= 6:
            return m
    return random.choice(["🙂", "😄", "✨"])

async def ai_clean_text(text: str):
    m = await llm_chat([
        {"role": "system", "content": "Замени ВСЕ русские матерные/оскорбительные слова на звёздочки той же длины. Не меняй остальные слова, пробелы и пунктуацию. Ответь только итоговым текстом."},
        {"role": "user", "content": text},
    ], max_tokens=320, temperature=0.0)
    return m or mask_bad_regex(text)

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
        await asyncio.sleep(0.16)
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
        a = await ai_answer_any(text)
        await ctx.bot.send_message(chat_id, a, business_connection_id=bcid)
        return

    if uid == owner:
        new = text
        if chat_id in clean_mode:
            new = await ai_clean_text(new) if AI_API_KEY else mask_bad_regex(new)
        if chat_id in emoji_mode:
            e = await ai_pick_emoji(new) if AI_API_KEY else random.choice(["🙂", "😄", "✨"])
            new = new + " " + e
        if new != text:
            await edit_msg(bcid, chat_id, msg.message_id, new)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
