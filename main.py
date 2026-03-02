import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from google.generativeai import GenerativeModel
import google.generativeai as genai

# Загрузка настроек из Render
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка Gemini
genai.configure(api_key=GEMINI_KEY)
model = GenerativeModel('gemini-pro')

# Список замученных (хранится в памяти, пока бот запущен)
muted_users = set()

# Проверка, что пишет именно владелец
def is_owner(message: types.Message):
    return message.from_user.id == OWNER_ID

# КОМАНДА .MUTE
@dp.message(F.text.startswith(".mute"), is_owner)
async def mute_user(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Ответь этой командой на сообщение того, кого хочешь замутить.")
    
    user_id = message.reply_to_message.from_user.id
    muted_users.add(user_id)
    await message.answer(f"🚫 Пользователь {user_id} теперь в муте. Его сообщения будут удаляться.")

# КОМАНДА .UNMUTE
@dp.message(F.text.startswith(".unmute"), is_owner)
async def unmute_user(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Ответь этой командой на сообщение.")
    
    user_id = message.reply_to_message.from_user.id
    muted_users.discard(user_id)
    await message.answer(f"✅ Пользователь {user_id} размучен.")

# КОМАНДА .DOX
@dp.message(F.text.startswith(".dox"), is_owner)
async def dox_user(message: types.Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    
    info = (
        f"🔍 **DOSSIER: {target.full_name}**\n"
        f"🆔 **ID:** `{target.id}`\n"
        f"👤 **Username:** @{target.username if target.username else 'нет'}\n"
        f"🤖 **Bot:** {'Да' if target.is_bot else 'Нет'}\n"
        f"🔗 **History:** [Check Names](https://t.me/SangMataInfo_bot?start={target.id})"
    )
    await message.answer(info, parse_mode="Markdown")

# КОМАНДА .AI
@dp.message(F.text.startswith(".ai "), is_owner)
async def ai_chat(message: types.Message):
    prompt = message.text[4:]
    response = model.generate_content(prompt)
    await message.answer(f"🤖 **Gemini:**\n{response.text}")

# УДАЛЕНИЕ СООБЩЕНИЙ ЗАМУЧЕННЫХ
@dp.message()
async def auto_delete(message: types.Message):
    if message.from_user.id in muted_users:
        try:
            await message.delete()
        except:
            pass

async def main():
    print("Бот запущен через Telegram Business!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())