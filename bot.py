import os
import asyncio
import random
import re
import math
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"

CIRCLE = "⚪️"
CHECK = "✅"

muted_chats = set()
owner_id_by_chat = {}

clean_mode = set()
emoji_mode = set()
ai_answers = set()

EMOJIS = ["😈", "💀", "🔥", "😏", "🤡", "🗿", "⚠️"]

AI_PHRASES = [
    "Unclear intent.",
    "Statement noted.",
    "Response probability: low.",
    "Try again.",
    "Your logic is questionable.",
    "Interesting conclusion.",
    "That does not change the outcome.",
]

def is_cmd(t, c):
    t = (t or "").strip()
    return t == c or t.startswith(c + " ")

async def delete_business_messages(bcid, ids):
    if not bcid:
        return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"{API_BASE}/deleteBusinessMessages",
                json={"business_connection_id": bcid, "message_ids": ids},
                timeout=5
            )
    except:
        pass

def clean_text(text):
    return re.sub(r"\b(\w{4,})\b", "***", text)

def emoji_text(text):
    return text + " " + random.choice(EMOJIS)

def calc(expr):
    try:
        if re.search(r"[a-zA-Z]", expr):
            parts = re.split(r"\+", expr)
            return "".join(p.strip() for p in parts)
        return str(eval(expr, {"__builtins__": None, "sqrt": math.sqrt}))
    except:
        return "Error"

async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg:
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)
    from_id = getattr(getattr(msg, "from_user", None), "id", None)
    owner = owner_id_by_chat.get(chat_id)

    if chat_id in muted_chats and owner and from_id != owner:
        await delete_business_messages(bcid, [msg.message_id])
        return

    if not msg.text:
        return

    text = msg.text.strip()

    if is_cmd(text, ".mute"):
        owner_id_by_chat[chat_id] = from_id
        muted_chats.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, "Помолчи-ка, ты пока что в муте и не можешь писать", business_connection_id=bcid)
        return

    if is_cmd(text, ".unmute"):
        owner_id_by_chat[chat_id] = from_id
        muted_chats.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, "Все, можешь говорить <3", business_connection_id=bcid)
        return

    if is_cmd(text, ".clean on"):
        clean_mode.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if is_cmd(text, ".clean off"):
        clean_mode.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if is_cmd(text, ".emoji on"):
        emoji_mode.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if is_cmd(text, ".emoji off"):
        emoji_mode.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if is_cmd(text, ".aianswers on"):
        ai_answers.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if is_cmd(text, ".aianswers off"):
        ai_answers.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        return

    if text.startswith(".calc"):
        expr = text.replace(".calc", "", 1).strip()
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, calc(expr), business_connection_id=bcid)
        return

    if chat_id in ai_answers and owner and from_id != owner:
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(chat_id, random.choice(AI_PHRASES), business_connection_id=bcid)
        return

    if owner and from_id == owner:
        new_text = text
        if chat_id in clean_mode:
            new_text = clean_text(new_text)
        if chat_id in emoji_mode:
            new_text = emoji_text(new_text)
        if new_text != text:
            try:
                await ctx.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=new_text,
                    business_connection_id=bcid
                )
            except:
                pass

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
