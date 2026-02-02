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

FINAL_DELETE_PROTOCOL = 0.1
FINAL_DELETE_DOX = 1.5

PERCENT_BASE = 0.026
PERCENT_MIN = 0.016
TEXT_BASE = 0.038
TEXT_MIN = 0.028

CIRCLE = "⚪️"
CHECK = "✅"

muted_chats = set()
owner_id_by_chat = {}

clean_mode = set()
emoji_mode = set()
ai_answers = set()

EMOJIS = ["😈", "💀", "🔥", "😏", "🤡", "🗿", "⚠️"]
AI_PHRASES = [
    "Unclear intent.",
    "Statement noted.",
    "Response probability: low.",
    "Try again.",
    "Your logic is questionable.",
    "Interesting conclusion.",
    "That does not change the outcome.",
]

def cmd(text: str) -> str:
    return (text or "").strip()

def is_exact_or_prefix(text: str, base: str) -> bool:
    t = cmd(text)
    return t == base or t.startswith(base + " ") or t.startswith(base + "@")

async def tg_post(method: str, payload: dict) -> dict | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{API_BASE}/{method}", json=payload, timeout=8) as r:
                return await r.json()
    except Exception:
        return None

async def delete_business_messages(bcid: str | None, ids: list[int]):
    if not bcid or not ids:
        return
    await tg_post("deleteBusinessMessages", {"business_connection_id": bcid, "message_ids": ids})

async def edit_business_message_text(bcid: str | None, chat_id: int, message_id: int, text: str):
    if not bcid:
        return
    await tg_post("editMessageText", {
        "business_connection_id": bcid,
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    })

def clean_text(text: str) -> str:
    return re.sub(r"\b[^\W\d_]{4,}\b", "***", text, flags=re.UNICODE)

def emoji_text(text: str) -> str:
    return text + " " + random.choice(EMOJIS)

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
    except Exception:
        return "Error"

def rand_inc():
    r = random.random()
    if r < 0.45: return 2
    if r < 0.80: return 3
    if r < 0.94: return 4
    return 1

def build_vals(a, b):
    v = [a]; p = a
    while p < b:
        if random.random() < 0.03:
            v.append(p); continue
        p = min(b, p + rand_inc()); v.append(p)
    return v

async def sp():
    await asyncio.sleep(max(PERCENT_MIN, PERCENT_BASE + random.uniform(-0.008, 0.012)))

async def st():
    await asyncio.sleep(max(TEXT_MIN, TEXT_BASE + random.uniform(-0.010, 0.016)))

async def run_protocol(ctx, chat_id, bcid):
    m = await ctx.bot.send_message(chat_id, "Encrypting 1%", business_connection_id=bcid)
    for p in build_vals(1, 93)[1:]:
        await sp()
        try: await m.edit_text(f"Encrypting {p}%")
        except: pass
    await st()
    try: await m.edit_text(f"{CIRCLE}Encrypting completed")
    except: pass
    for _ in range(random.randint(3, 4)):
        await st()
        try: await m.edit_text("Opening json codec.")
        except: pass
        await st()
        try: await m.edit_text("Opening json codec..")
        except: pass
        await st()
        try: await m.edit_text("Opening json codec...")
        except: pass
    await st()
    try: await m.edit_text(f"{CIRCLE}Success")
    except: pass
    for p in build_vals(29, 96):
        await sp()
        try: await m.edit_text(f"Rematching data {p}%")
        except: pass
    await st()
    try: await m.edit_text(f"{CIRCLE}Successful")
    except: pass
    await asyncio.sleep(FINAL_DELETE_PROTOCOL)
    await delete_business_messages(bcid, [m.message_id])

async def run_dox(ctx, chat_id, bcid):
    lines = [
        "Target: masked",
        "Resolving identifiers...",
        "Sync: active",
        "Hash map: loaded",
        "Vectors: aligned",
        "Packet stream: locked",
        "Session key: generated",
        "Proxy chain: verified",
        "Firewall state: unknown",
        "Ruleset: applied",
        "Trace flags: cleared",
        "Payload: prepared",
        "Routing: stable",
        "Integrity: ok",
        "Finalizing...",
    ]
    text = lines[0]
    m = await ctx.bot.send_message(chat_id, text, business_connection_id=bcid)
    for line in lines[1:]:
        await asyncio.sleep(0.28)
        text += "\n" + line
        try: await m.edit_text(text)
        except: pass
    await asyncio.sleep(0.28)
    text += "\n\n" + f"{CHECK}Freefly Systems enabled"
    try: await m.edit_text(text)
    except: pass
    await asyncio.sleep(0.28)
    text += "\n" + f"{CHECK}Successful sent to IP base"
    try: await m.edit_text(text)
    except: pass
    await asyncio.sleep(FINAL_DELETE_DOX)
    await delete_business_messages(bcid, [m.message_id])

async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg:
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)
    from_id = getattr(getattr(msg, "from_user", None), "id", None)
    text = getattr(msg, "text", None)

    if from_id and chat_id not in owner_id_by_chat:
        owner_id_by_chat[chat_id] = from_id

    owner = owner_id_by_chat.get(chat_id)

    if chat_id in muted_chats and owner and from_id and from_id != owner:
        await delete_business_messages(bcid, [msg.message_id])
        return

    if not text:
        return

    t = cmd(text)

    if t.startswith(".") and from_id:
        owner_id_by_chat[chat_id] = from_id
        owner = from_id

    if is_exact_or_prefix(t, ".protocol"):
        await delete_business_messages(bcid, [msg.message_id])
        await run_protocol(ctx, chat_id, bcid)
        return

    if is_exact_or_prefix(t, ".dox"):
        await delete_business_messages(bcid, [msg.message_id])
        await run_dox(ctx, chat_id, bcid)
        return

    if is_exact_or_prefix(t, ".mute"):
        muted_chats.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, "Помолчи-ка, ты пока что в муте и не можешь писать", business_connection_id=bcid)
        return

    if is_exact_or_prefix(t, ".unmute"):
        muted_chats.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, "Все, можешь говорить <3", business_connection_id=bcid)
        return

    if t == ".clean on":
        clean_mode.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if t == ".clean off":
        clean_mode.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if t == ".emoji on":
        emoji_mode.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if t == ".emoji off":
        emoji_mode.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if t == ".aianswers on":
        ai_answers.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if t == ".aianswers off":
        ai_answers.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if t.startswith(".calc"):
        expr = t[5:].strip()
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, calc(expr), business_connection_id=bcid)
        return

    if chat_id in ai_answers and owner and from_id and from_id != owner:
        await ctx.bot.send_message(chat_id, random.choice(AI_PHRASES), business_connection_id=bcid)
        return

    if owner and from_id and from_id == owner:
        new_text = t
        if chat_id in clean_mode:
            new_text = clean_text(new_text)
        if chat_id in emoji_mode:
            new_text = emoji_text(new_text)
        if new_text != t:
            await edit_business_message_text(bcid, chat_id, msg.message_id, new_text)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
