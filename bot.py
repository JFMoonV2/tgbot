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
    if r < 0.45:
        return 1
    if r < 0.79:
        return 2
    if r < 0.93:
        return 3
    return 4

def build_steps() -> list[str]:
    steps = []
    p = 1
    steps.append(f"Encrypting {p}%")
    while p < 93:
        if random.random() < 0.05:
            steps.append(f"Encrypting {p}%")
            continue
        p = min(93, p + rand_inc())
        steps.append(f"Encrypting {p}%")

    steps.append("⚪️Encrypting completed")

    loops = random.randint(3, 4)
    for _ in range(loops):
        steps.append("Opening json codec.")
        steps.append("Opening json codec..")
        steps.append("Opening json codec...")

    steps.append("⚪️Success")

    rp = 1
    steps.append(f"Rematching data {rp}%")
    while rp < 96:
        if random.random() < 0.05:
            steps.append(f"Rematching data {rp}%")
            continue
        rp = min(96, rp + rand_inc())
        steps.append(f"Rematching data {rp}%")

    steps.append("⚪️Successful")
    return steps

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return
    if not is_cmd(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    await delete_business_messages(bcid, [msg.message_id])

    steps = build_steps()

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=steps[0],
        business_connection_id=bcid,
    )

    base = 0.085
    for i in range(1, len(steps)):
        jitter = random.uniform(-0.02, 0.045)
        await asyncio.sleep(max(0.05, base + jitter))
        try:
            await sent.edit_text(steps[i])
        except Exception:
            pass

    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await delete_business_messages(bcid, [sent.message_id])

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
