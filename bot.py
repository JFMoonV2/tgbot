import os
import asyncio
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing. Add TOKEN in Railway Variables.")

# Быстро и обычно стабильно:
STEP_DELAY_SEC = float(os.getenv("STEP_DELAY_SEC", "0.06"))
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "2"))

def is_hack_command(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t == "/hack" or t.startswith("/hack@") or t.startswith("/hack ")

async def safe_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, bcid: str | None) -> bool:
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
            business_connection_id=bcid,
        )
        return True
    except Exception:
        return False

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return

    if not is_hack_command(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    # 1) Пытаемся удалить твой /hack
    deleted = await safe_delete(context, chat_id, msg.message_id, bcid)

    # 2) Если не удалилось — "маскировка" (НЕ удаляет /hack, просто визуально перебивает)
    # Отправим невидимый символ, и сразу удалим его (чтобы не мусорить)
    if not deleted:
        try:
            ghost = await context.bot.send_message(
                chat_id=chat_id,
                text="\u2063",  # INVISIBLE SEPARATOR
                business_connection_id=bcid,
            )
            await asyncio.sleep(0.2)
            await safe_delete(context, chat_id, ghost.message_id, bcid)
        except Exception:
            pass

    # 3) Сообщение прогресса (одно, редактируемое)
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text="hack 0%",
        business_connection_id=bcid,
    )

    # 4) Быстрый прогресс: шаг 2% (0,2,4...100)
    for p in range(2, 101, 2):
        await asyncio.sleep(STEP_DELAY_SEC)
        try:
            await sent.edit_text(f"hack {p}%")
        except Exception:
            pass

    # 5) Финал
    await asyncio.sleep(STEP_DELAY_SEC)
    try:
        await sent.edit_text("successful!")
    except Exception:
        pass

    # 6) Удалить финал через 2 секунды
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await safe_delete(context, chat_id, sent.message_id, bcid)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
