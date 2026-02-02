import os
import asyncio
import random
import aiohttp
from telegram import Update, MessageEntity
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "0.8"))

CUSTOM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID", "").strip()

PERCENT_BASE = float(os.getenv("PERCENT_BASE", "0.045"))
PERCENT_MIN = float(os.getenv("PERCENT_MIN", "0.028"))
PERCENT_JITTER_LOW = float(os.getenv("PERCENT_JITTER_LOW", "-0.012"))
PERCENT_JITTER_HIGH = float(os.getenv("PERCENT_JITTER_HIGH", "0.020"))

TEXT_BASE = float(os.getenv("TEXT_BASE", "0.07"))
TEXT_MIN = float(os.getenv("TEXT_MIN", "0.045"))
TEXT_JITTER_LOW = float(os.getenv("TEXT_JITTER_LOW", "-0.015"))
TEXT_JITTER_HIGH = float(os.getenv("TEXT_JITTER_HIGH", "0.030"))

def is_cmd(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t == ".protocol" or t.startswith(".protocol@") or t.startswith(".protocol ")

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
    if r < 0.32:
        return 2
    if r < 0.70:
        return 3
    if r < 0.92:
        return 4
    return 1

def emoji_prefix() -> tuple[str, list[MessageEntity] | None]:
    if CUSTOM_EMOJI_ID:
        return "▫", [MessageEntity(type="custom_emoji", offset=0, length=1, custom_emoji_id=CUSTOM_EMOJI_ID)]
    return "⚪️", None

def build_percent_values(start: int, end: int) -> list[int]:
    vals = [start]
    p = start
    while p < end:
        if random.random() < 0.04:
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

async def send_or_edit(sent, context, chat_id, bcid, text, entities):
    if sent is None:
        return await context.bot.send_message(chat_id=chat_id, text=text, business_connection_id=bcid, entities=entities)
    try:
        await sent.edit_text(text, entities=entities)
    except Exception:
        pass
    return sent

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return
    if not is_cmd(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    await delete_business_messages(bcid, [msg.message_id])

    circle, circle_entities = emoji_prefix()

    sent = None

    for p in build_percent_values(1, 93):
        sent = await send_or_edit(sent, context, chat_id, bcid, f"Encrypting {p}%", None)
        await sleep_percent()

    sent = await send_or_edit(sent, context, chat_id, bcid, f"{circle}Encrypting completed", circle_entities)
    await sleep_text()

    loops = random.randint(3, 4)
    for _ in range(loops):
        sent = await send_or_edit(sent, context, chat_id, bcid, "Opening json codec.", None)
        await sleep_text()
        sent = await send_or_edit(sent, context, chat_id, bcid, "Opening json codec..", None)
        await sleep_text()
        sent = await send_or_edit(sent, context, chat_id, bcid, "Opening json codec...", None)
        await sleep_text()

    sent = await send_or_edit(sent, context, chat_id, bcid, f"{circle}Success", circle_entities)
    await sleep_text()

    for p in build_percent_values(29, 96):
        sent = await send_or_edit(sent, context, chat_id, bcid, f"Rematching data {p}%", None)
        await sleep_percent()

    sent = await send_or_edit(sent, context, chat_id, bcid, f"{circle}Successful", circle_entities)

    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    if sent is not None:
        await delete_business_messages(bcid, [sent.message_id])

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
