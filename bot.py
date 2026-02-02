import os
import asyncio
import random
import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

TOKEN = os.getenv("TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

API_BASE = f"https://api.telegram.org/bot{TOKEN}"

FINAL_DELETE_PROTOCOL = 0.1
FINAL_DELETE_DOX = 1.5

PERCENT_BASE = 0.026
PERCENT_MIN = 0.016
TEXT_BASE = 0.038
TEXT_MIN = 0.028

CIRCLE = "⚪️"
CHECK = "✅"

muted_chats = set()
owner_id_by_chat = {}

def is_protocol(t):
    t = (t or "").strip()
    return t == ".protocol" or t.startswith(".protocol ")

def is_mute(t):
    t = (t or "").strip()
    return t == ".mute" or t.startswith(".mute ")

def is_unmute(t):
    t = (t or "").strip()
    return t == ".unmute" or t.startswith(".unmute ")

def is_dox(t):
    t = (t or "").strip()
    return t == ".dox" or t.startswith(".dox ")

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

def rand_inc():
    r = random.random()
    if r < 0.45: return 2
    if r < 0.80: return 3
    if r < 0.94: return 4
    return 1

def build_vals(a, b):
    v = [a]; p = a
    while p < b:
        if random.random() < 0.03:
            v.append(p); continue
        p = min(b, p + rand_inc()); v.append(p)
    return v

async def sp():
    await asyncio.sleep(max(PERCENT_MIN, PERCENT_BASE + random.uniform(-0.008, 0.012)))

async def st():
    await asyncio.sleep(max(TEXT_MIN, TEXT_BASE + random.uniform(-0.010, 0.016)))

async def run_protocol(ctx, chat_id, bcid):
    m = await ctx.bot.send_message(chat_id, "Encrypting 1%", business_connection_id=bcid)
    for p in build_vals(1, 93)[1:]:
        await sp()
        try: await m.edit_text(f"Encrypting {p}%")
        except: pass
    await st()
    try: await m.edit_text(f"{CIRCLE}Encrypting completed")
    except: pass
    for _ in range(random.randint(3, 4)):
        await st()
        try: await m.edit_text("Opening json codec.")
        except: pass
        await st()
        try: await m.edit_text("Opening json codec..")
        except: pass
        await st()
        try: await m.edit_text("Opening json codec...")
        except: pass
    await st()
    try: await m.edit_text(f"{CIRCLE}Success")
    except: pass
    for p in build_vals(29, 96):
        await sp()
        try: await m.edit_text(f"Rematching data {p}%")
        except: pass
    await st()
    try: await m.edit_text(f"{CIRCLE}Successful")
    except: pass
    await asyncio.sleep(FINAL_DELETE_PROTOCOL)
    await delete_business_messages(bcid, [m.message_id])

async def run_dox(ctx, chat_id, bcid):
    lines = [
        "IP: 92.28.211.234",
        "N: 43.7462",
        "W: 12.489",
        "SS Number: 697919918",
        "IPv6: fe80::5dcd::ef69::fb22::d9888%12",
        "DMZ: 10.12.45.123",
        "MAC: 5A:78:3E:7E:00",
        "ISP: United Networks",
        "DNS: 8.8.8.8",
        "DNS: 8.8.4.4",
        "WAN: 92.28.211.234",
        "WAN Type: Private",
        "Gateway: 102.168.1.1",
        "Subnet Mask: 255.255.255.0",
        "UPNP: ENABLED",
        "TCP OPEN PORTS: 8080, 80",
        "UDP OPEN PORTS: 53"
    ]
    text = lines[0]
    m = await ctx.bot.send_message(chat_id, text, business_connection_id=bcid)
    for line in lines[1:]:
        await asyncio.sleep(0.35)
        text += "\n" + line
        try: await m.edit_text(text)
        except: pass
    await asyncio.sleep(0.35)
    text += "\n\n" + f"{CHECK}Freefly Systems enabled"
    try: await m.edit_text(text)
    except: pass
    await asyncio.sleep(0.35)
    text += "\n" + f"{CHECK}Successful sent to IP base"
    try: await m.edit_text(text)
    except: pass
    await asyncio.sleep(FINAL_DELETE_DOX)
    await delete_business_messages(bcid, [m.message_id])

async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message or update.message
    if not msg:
        return

    chat_id = msg.chat_id
    bcid = getattr(msg, "business_connection_id", None)
    from_id = getattr(getattr(msg, "from_user", None), "id", None)

    owner_id = owner_id_by_chat.get(chat_id)

    if chat_id in muted_chats and owner_id and from_id and from_id != owner_id:
        await delete_business_messages(bcid, [msg.message_id])
        return

    if not msg.text:
        return

    if is_protocol(msg.text):
        owner_id_by_chat[chat_id] = from_id
        await delete_business_messages(bcid, [msg.message_id])
        await run_protocol(ctx, chat_id, bcid)
        return

    if is_mute(msg.text):
        owner_id_by_chat[chat_id] = from_id
        muted_chats.add(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(
            chat_id,
            "Помолчи-ка, ты пока что в муте и не можешь писать",
            business_connection_id=bcid
        )
        return

    if is_unmute(msg.text):
        owner_id_by_chat[chat_id] = from_id
        muted_chats.discard(chat_id)
        await delete_business_messages(bcid, [msg.message_id])
        await ctx.bot.send_message(
            chat_id,
            "Все, можешь говорить <3",
            business_connection_id=bcid
        )
        return

    if is_dox(msg.text):
        owner_id_by_chat[chat_id] = from_id
        await delete_business_messages(bcid, [msg.message_id])
        await run_dox(ctx, chat_id, bcid)
        return

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(TypeHandler(Update, handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
