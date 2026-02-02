import os
import asyncio
import random
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "0.8"))

PERCENT_BASE = float(os.getenv("PERCENT_BASE", "0.032"))
PERCENT_MIN = float(os.getenv("PERCENT_MIN", "0.020"))
PERCENT_JITTER_LOW = float(os.getenv("PERCENT_JITTER_LOW", "-0.009"))
PERCENT_JITTER_HIGH = float(os.getenv("PERCENT_JITTER_HIGH", "0.014"))

TEXT_BASE = float(os.getenv("TEXT_BASE", "0.050"))
TEXT_MIN = float(os.getenv("TEXT_MIN", "0.035"))
TEXT_JITTER_LOW = float(os.getenv("TEXT_JITTER_LOW", "-0.010"))
TEXT_JITTER_HIGH = float(os.getenv("TEXT_JITTER_HIGH", "0.020"))

CIRCLE = "⚪️"

muted_chats = set()
owner_id_by_chat = {}

def is_cmd(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t.startswith(".")

def is_protocol(text: str) -> bool:
    t = (text or "").strip()
    return t == ".protocol" or t.startswith(".protocol@") or t.startswith(".protocol ")

def is_mute(text: str) -> bool:
    t = (text or "").strip()
    return t == ".mute" or t.startswith(".mute@") or t.startswith(".mute ")

def is_unmute(text: str) -> bool:
    t = (text or "").strip()
    return t == ".unmute" or t.startswith(".unmute@") or t.startswith(".unmute ")

async def delete_business_messages(business_connection_id: str | None, message_ids: list[int]) -> bool:
    if not business_connection_id:
        return False
    url = f"{API_BASE}/deleteBusinessMessages"
    payload = {"business_connection_id": business_connection_id, "message_ids": message_ids}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                data = await resp.json()
                return bool(data.get("ok")) and bool(data.get("result"))
    except Exception:
        return False

def rand_inc() -> int:
    r = random.random()
    if r < 0.44:
        return 2
    if r < 0.80:
        return 3
    if r < 0.94:
        return 4
    return 1

def build_percent_values(start: int, end: int) -> list[int]:
    vals = [start]
    p = start
    while p < end:
        if random.random() < 0.03:
            vals.append(p)
            continue
        p = min(end, p + rand_inc())
        vals.append(p)
    return vals

async def sleep_percent():
    jitter = random.uniform(PERCENT_JITTER_LOW, PERCENT_JITTER_HIGH)
    await asyncio.sleep(max(PERCENT_MIN, PERCENT_BASE + jitter))

async def sleep_text():
    jitter = random.uniform(TEXT_JITTER_LOW, TEXT_JITTER_HIGH)
    await asyncio.sleep(max(TEXT_MIN, TEXT_BASE + jitter))

async def run_protocol(context: ContextTypes.DEFAULT_TYPE, chat_id: int, bcid: str | None):
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text="Encrypting 1%",
        business_connection_id=bcid,
    )

    for p in build_percent_values(1, 93)[1:]:
        await sleep_percent()
        try:
            await sent.edit_text(f"Encrypting {p}%")
        except Exception:
            pass

    await sleep_text()
    try:
        await sent.edit_text(f"{CIRCLE}Encrypting completed")
    except Exception:
        pass

    loops = random.randint(3, 4)
    for _ in range(loops):
        await sleep_text()
        try:
            await sent.edit_text("Opening json codec.")
        except Exception:
            pass
        await sleep_text()
        try:
            await sent.edit_text("Opening json codec..")
        except Exception:
            pass
        await sleep_text()
        try:
            await sent.edit_text("Opening json codec...")
        except Exception:
            pass

    await sleep_text()
    try:
        await sent.edit_text(f"{CIRCLE}Success")
    except Exception:
        pass

    for p in build_percent_values(29, 96):
        await sleep_percent()
        try:
            await sent.edit_text(f"Rematching data {p}%")
        except Exception:
            pass

    await sleep_text()
    try:
        await sent.edit_text(f"{CIRCLE}Successful")
    except Exception:
        pass

    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await delete_business_messages(bcid, [sent.message_id])

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg:
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)
    from_id = getattr(getattr(msg, "from_user", None), "id", None)

    if chat_id in muted_chats:
        owner_id = owner_id_by_chat.get(chat_id)
        if owner_id and from_id and from_id != owner_id:
            await delete_business_messages(bcid, [msg.message_id])
            return

    if not msg.text:
        return

    if is_protocol(msg.text):
        if from_id:
            owner_id_by_chat[chat_id] = from_id
        await delete_business_messages(bcid, [msg.message_id])
        await run_protocol(context, chat_id, bcid)
        return

    if is_mute(msg.text):
        if from_id:
            owner_id_by_chat[chat_id] = from_id
        muted_chats.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await context.bot.send_message(
            chat_id=chat_id,
            text="Помолчи-ка, ты пока что в муте и не можешь писать",
            business_connection_id=bcid,
        )
        return

    if is_unmute(msg.text):
        if from_id:
            owner_id_by_chat[chat_id] = from_id
        muted_chats.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await context.bot.send_message(
            chat_id=chat_id,
            text="Все, можешь говорить <3",
            business_connection_id=bcid,
        )
        return

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
