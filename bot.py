import os
import asyncio
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

# Railway: добавь переменную окружения TOKEN
TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing. Add TOKEN in Railway Variables.")

# скорость смены процентов (рекомендую 0.25; быстрее может упираться в лимиты edit)
STEP_DELAY_SEC = float(os.getenv("STEP_DELAY_SEC", "0.25"))
# сколько ждать перед удалением финального сообщения
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "2"))

def is_hack_command(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    # /hack, /hack@BotName, /hack что-то
    return t == "/hack" or t.startswith("/hack@") or t.startswith("/hack ")

async def safe_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, bcid: str | None):
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
            business_connection_id=bcid,
        )
    except Exception:
        # если Telegram не разрешил — просто игнорируем
        pass

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # бизнес-сообщения приходят в update.business_message
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return

    if not is_hack_command(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    # 1) пытаемся удалить твоё сообщение /hack
    await safe_delete(context, chat_id, msg.message_id, bcid)

    # 2) отправляем одно сообщение и редактируем его: hack 1% ... hack 100%
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text="hack 1%",
        business_connection_id=bcid,
    )

    # 3) прогресс 2..100
    for p in range(2, 101):
        await asyncio.sleep(STEP_DELAY_SEC)
        try:
            await sent.edit_text(f"hack {p}%")
        except Exception:
            # лимиты редактирования/гонки — не валим бота
            pass

    # 4) финал
    await asyncio.sleep(STEP_DELAY_SEC)
    try:
        await sent.edit_text("successful!")
    except Exception:
        pass

    # 5) удалить финальное сообщение через 2 секунды
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await safe_delete(context, chat_id, sent.message_id, bcid)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
