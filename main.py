import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from google.generativeai import GenerativeModel
import google.generativeai as genai
from aiohttp import web

# Настройки
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()
genai.configure(api_key=GEMINI_KEY)
model = GenerativeModel('gemini-pro')
muted_users = set()

# --- ФЕЙКОВЫЙ СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    await site.start()
# ----------------------------------

@dp.message(F.text.startswith(".dox"))
async def dox_user(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    info = f"🔍 **DOSSIER:** {target.full_name}\n🆔 **ID:** `{target.id}`\n👤 @{target.username}\n🔗 [History](https://t.me/SangMataInfo_bot?start={target.id})"
    await message.answer(info, parse_mode="Markdown")

@dp.message(F.text.startswith(".ai "))
async def ai_chat(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    response = model.generate_content(message.text[4:])
    await message.answer(f"🤖 **Gemini:**\n{response.text}")

async def main():
    # Запускаем и сервер, и бота одновременно
    await start_web_server()
    print("Бот и Фейк-сервер запущены!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())