import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tgbot")

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing. Add TOKEN in Railway Variables.")

STEP_DELAY_SEC = float(os.getenv("STEP_DELAY_SEC", "0.05"))
FINAL_DELETE_DELAY_SEC = float(os.getenv("FINAL_DELETE_DELAY_SEC", "2"))

PREFIX = "sdox"

def is_cmd(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    return t == "/hack" or t.startswith("/hack@") or t.startswith("/hack ")

async def try_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, bcid: str | None) -> tuple[bool, str]:
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
            business_connection_id=bcid,
        )
        return True, "ok"
    except Exception as e:
        return False, repr(e)

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg or not msg.text:
        return

    if not is_cmd(msg.text):
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)

    log.info(f"Got /hack in chat_id={chat_id}, bcid={bcid}, from_update={'business_message' if update.business_message else 'message'}")

    # 1) Пытаемся удалить твою команду
    ok, err = await try_delete(context, chat_id, msg.message_id, bcid)
    if ok:
        log.info("Deleted user /hack message: OK")
    else:
        log.warning(f"Failed to delete user /hack message: {err}")

    # 2) Отправляем прогресс-сообщение (это сообщение бота)
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"{PREFIX} 0%",
        business_connection_id=bcid,
    )

    # 3) Ускоренный прогресс: 0,5,10...100 (21 правка)
    for p in range(5, 101, 5):
        await asyncio.sleep(STEP_DELAY_SEC)
        try:
            await sent.edit_text(f"{PREFIX} {p}%")
        except Exception as e:
            log.warning(f"edit_text failed at {p}%: {repr(e)}")

    # 4) Финал
    await asyncio.sleep(STEP_DELAY_SEC)
    try:
        await sent.edit_text("successful!")
    except Exception as e:
        log.warning(f"final edit_text failed: {repr(e)}")

    # 5) Удаляем сообщение бота через 2 сек
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    ok2, err2 = await try_delete(context, chat_id, sent.message_id, bcid)
    if ok2:
        log.info("Deleted bot message: OK")
    else:
        log.warning(f"Failed to delete bot message: {err2}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
