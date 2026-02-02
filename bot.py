import os
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing. Add TOKEN in Railway Variables.")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"

FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "0.8"))

def is_cmd(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t == "/hack" or t.startswith("/hack@") or t.startswith("/hack ")

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

# Твои шаги (каждый элемент = текст, который будет стоять в сообщении)
STEPS = [
    "Encrypting 1%",
    "Encrypting 9%",
    "Encrypting 23%",
    "Encrypting 41%",
    "Encrypting 69%",
    "Encrypting 73%",
    "Encrypting 87%",
    "Encrypting 93%",
    "⚪️Encrypting completed",
    "Opening json codec..",
    "Opening json codec...",
    "⚪️Success",
    "Rematching data 29%",
    "Rematching data 45%",
    "Rematching data 78%",
    "Rematching data 96%",
    "⚪️Successful",
]

# Задержки между шагами (сек). Если хочешь быстрее/медленнее — меняй тут.
# Длина должна совпадать с количеством STEPS-1 (между шагами).
DELAYS = [
    0.08, 0.08, 0.10, 0.10, 0.10, 0.08, 0.08, 0.10,
    0.12, 0.10, 0.12, 0.10,
    0.10, 0.10, 0.10, 0.10
]

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return

    if not is_cmd(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    # удалить /hack
    await delete_business_messages(bcid, [msg.message_id])

    # отправить первое состояние
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=STEPS[0],
        business_connection_id=bcid,
    )

    # проиграть шаги
    for i in range(1, len(STEPS)):
        await asyncio.sleep(DELAYS[i - 1])
        try:
            await sent.edit_text(STEPS[i])
        except Exception:
            pass

    # удалить через 0.8 сек
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await delete_business_messages(bcid, [sent.message_id])

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
