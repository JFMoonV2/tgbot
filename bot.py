import os
import asyncio
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing. Add TOKEN in Railway Variables.")

# Быстрее (если слишком быстро — поставь 0.06 или 0.08)
STEP_DELAY_SEC = float(os.getenv("STEP_DELAY_SEC", "0.04"))
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "2"))

PREFIX = "sdox"  # вместо hack

def is_cmd(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t == "/hack" or t.startswith("/hack@") or t.startswith("/hack ")

async def try_delete_user_cmd(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, bcid: str | None):
    # Пытаемся удалить /hack. В личке Telegram часто не разрешает — тогда просто молча продолжаем.
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
            business_connection_id=bcid,
        )
    except Exception:
        pass

async def try_delete_own(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, bcid: str | None):
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
            business_connection_id=bcid,
        )
    except Exception:
        pass

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return

    if not is_cmd(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    # 1) попытка удалить твою команду
    await try_delete_user_cmd(context, chat_id, msg.message_id, bcid)

    # 2) одно сообщение, которое редактируем (быстрее и без спама)
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"{PREFIX} 0%",
        business_connection_id=bcid,
    )

    # 3) прогресс шагом 4% (25 правок вместо 100 — быстрее и стабильнее)
    for p in range(4, 101, 4):
        await asyncio.sleep(STEP_DELAY_SEC)
        try:
            await sent.edit_text(f"{PREFIX} {p}%")
        except Exception:
            pass

    # 4) финал
    await asyncio.sleep(STEP_DELAY_SEC)
    try:
        await sent.edit_text("successful!")
    except Exception:
        pass

    # 5) удалить через 2 сек (это сообщение бота — удалится почти всегда)
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await try_delete_own(context, chat_id, sent.message_id, bcid)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
