import os
import asyncio
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import google.generativeai as genai

# --- ВНУТРЕННИЙ СЕРВЕР ДЛЯ ОЖИВЛЕНИЯ ---
app = Flask('')
@app.route('/')
def home():
    return "I am alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# --- НАСТРОЙКИ БОТА ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
STRING_SESSION = os.environ.get("STRING_SESSION")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
muted_users = set()
ai_chats = set()

@client.on(events.NewMessage(outgoing=True))
async def cmd_handler(event):
    global muted_users, ai_chats
    text = event.text.lower()
    if ".mute" in text and event.is_reply:
        rep = await event.get_reply_message()
        muted_users.add(rep.from_id.user_id)
        await event.edit("🤐 Заткнул.")
    elif ".ai_on" in text:
        ai_chats.add(event.chat_id)
        await event.edit("🤖 AI ON.")

@client.on(events.NewMessage(incoming=True))
async def main_handler(event):
    if event.sender_id in muted_users:
        await event.delete(revoke=True)
    if event.chat_id in ai_chats and event.is_private:
        res = ai_model.generate_content(f"Ответь как я: {event.text}")
        await event.reply(res.text)

# --- ЗАПУСК ---
def start_bot():
    Thread(target=run_flask).start() # Запускаем веб-сервер в фоне
    client.start()
    client.run_until_disconnected()

if __name__ == "__main__":
    start_bot()