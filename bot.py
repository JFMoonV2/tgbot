import os
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing. Add TOKEN in Railway Variables.")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"

# быстрее/медленнее:
STEP_DELAY_SEC = float(os.getenv("STEP_DELAY_SEC", "0.04"))
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "2"))

PREFIX = "sdox"

def is_cmd(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t == "/hack" or t.startswith("/hack@") or t.startswith("/hack ")

async def delete_business_messages(business_connection_id: str | None, message_ids: list[int]) -> bool:
    """
    Правильный способ удаления в Telegram Business: deleteBusinessMessages.
    Требует включённых прав в Business (can_delete_sent_messages/can_delete_all_messages).
    """
    if not business_connection_id:
        return False

    url = f"{API_BASE}/deleteBusinessMessages"
    payload = {
        "business_connection_id": business_connection_id,
        "message_ids": message_ids,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                data = await resp.json()
                return bool(data.get("ok")) and bool(data.get("result"))
    except Exception:
        return False

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return

    if not is_cmd(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    # 1) Пытаемся удалить твоё /hack (как у “мут” ботов)
    # Это сработает только если Telegram реально разрешил через business rights.
    await delete_business_messages(bcid, [msg.message_id])

    # 2) Отправляем одно сообщение и редактируем его (на behalf владельца бизнес-аккаунта)
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"{PREFIX} 0%",
        business_connection_id=bcid,
    )

    # 3) Быстрый прогресс (шаг 4% = меньше edit'ов и меньше шанс лимитов)
    for p in range(4, 101, 4):
        await asyncio.sleep(STEP_DELAY_SEC)
        try:
            await sent.edit_text(f"{PREFIX} {p}%")
        except Exception:
            pass

    # 4) Финал
    await asyncio.sleep(STEP_DELAY_SEC)
    try:
        await sent.edit_text("successful!")
    except Exception:
        pass

    # 5) Удаляем сообщение бота/“от имени юзера” через 2 сек именно бизнес-методом
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await delete_business_messages(bcid, [sent.message_id])

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
