import os
import asyncio
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

# Railway Variables -> TOKEN
TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing. Add TOKEN in Railway Variables.")

# Скорость (меньше = быстрее). Если начнёт лагать/пропускать — поставь 0.05-0.08
STEP_DELAY_SEC = float(os.getenv("STEP_DELAY_SEC", "0.04"))
# Через сколько секунд удалить сообщение бота после successful!
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "2"))

PREFIX = "sdox"  # вместо hack

def is_hack_command(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t == "/hack" or t.startswith("/hack@") or t.startswith("/hack ")

async def delete_message_safe(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """
    ВАЖНО: В python-telegram-bot delete_message НЕ принимает business_connection_id.
    Поэтому удаляем без него. Это удаляет сообщения бота стабильно.
    """
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return

    if not is_hack_command(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    # 1) Пытаемся удалить твою /hack (в личке часто запрещено — поэтому может не удалиться)
    await delete_message_safe(context, chat_id, msg.message_id)

    # 2) Отправляем одно сообщение и редактируем его (это сообщение бота)
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"{PREFIX} 0%",
        business_connection_id=bcid,  # для business-чатов
    )

    # 3) Быстрый прогресс: шаг 4% (25 редактирований — быстро и без лимитов)
    for p in range(4, 101, 4):
        await asyncio.sleep(STEP_DELAY_SEC)
        try:
            await sent.edit_text(f"{PREFIX} {p}%")
        except Exception:
            # если Telegram ограничил частоту редактирования — просто пропустим шаг
            pass

    # 4) Финал
    await asyncio.sleep(STEP_DELAY_SEC)
    try:
        await sent.edit_text("successful!")
    except Exception:
        pass

    # 5) Удаляем сообщение бота через 2 секунды
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await delete_message_safe(context, chat_id, sent.message_id)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
