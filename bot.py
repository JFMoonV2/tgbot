import os
import asyncio
import random
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
    # поддержка .protocol и .protocol@BotName (на всякий)
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

def build_encrypting_steps() -> list[str]:
    """
    Делает “живую” шкалу процентов: иногда +1, иногда +2/+3/+4,
    с паузами/скачками, чтобы выглядело как процесс.
    """
    steps = []
    p = 1
    steps.append(f"Encrypting {p}%")

    # пока не дойдём до 93-99 — генерируем плавно
    while p < 93:
        r = random.random()
        if r < 0.55:
            inc = 1
        elif r < 0.80:
            inc = 2
        elif r < 0.93:
            inc = 3
        else:
            inc = 4

        # иногда делаем “залипание” на том же % (редко)
        if random.random() < 0.06:
            steps.append(f"Encrypting {p}%")
            continue

        p = min(93, p + inc)
        steps.append(f"Encrypting {p}%")

    # фиксируем финальные строки как ты хотел
    steps.append("⚪️Encrypting completed")
    steps.append("Opening json codec..")
    steps.append("Opening json codec...")
    steps.append("⚪️Success")

    # рематч тоже “живой”
    rp = 1
    steps.append(f"Rematching data {rp}%")
    while rp < 96:
        r = random.random()
        if r < 0.60:
            inc = 1
        elif r < 0.83:
            inc = 3
        else:
            inc = 4

        if random.random() < 0.05:
            steps.append(f"Rematching data {rp}%")
            continue

        rp = min(96, rp + inc)
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

    # 1) удалить твою команду .protocol
    await delete_business_messages(bcid, [msg.message_id])

    # 2) генерируем шаги процесса
    steps = build_encrypting_steps()

    # 3) отправляем первое состояние
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=steps[0],
        business_connection_id=bcid,
    )

    # 4) проигрываем шаги не слишком быстро
    # базовая скорость + случайные вариации (чтобы выглядело "живее")
    for i in range(1, len(steps)):
        # пауза: иногда короче, иногда длиннее
        base = 0.22
        jitter = random.uniform(-0.06, 0.14)  # небольшая вариативность
        await asyncio.sleep(max(0.10, base + jitter))

        try:
            await sent.edit_text(steps[i])
        except Exception:
            pass

    # 5) удалить сообщение через 0.8 сек
    await asyncio.sleep(FINAL_DELETE_DELAY_SEC)
    await delete_business_messages(bcid, [sent.message_id])

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
