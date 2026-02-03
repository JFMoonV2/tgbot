import os
import re
import ast
import json
import time
import math
import asyncio
import random
from typing import Optional, Tuple

import aiohttp
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.getenv("TG_API_ID", "0") or "0")
API_HASH = os.getenv("TG_API_HASH", "") or ""
SESSION_STRING = os.getenv("TG_SESSION_STRING", "") or ""

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
HF_URL = os.getenv("HF_URL", f"https://api-inference.huggingface.co/models/{HF_MODEL}")

STATE_FILE = os.getenv("STATE_FILE", "tb_state.json")
CMD_PREFIX = "."
DEFAULT_EMOJI_FALLBACK = "✨"

def _now_ms() -> int:
    return int(time.time() * 1000)

def _default_state():
    return {
        "muted_ids": [],
        "clean_on": False,
        "emoji_on": False,
        "aianswers_on": False,
        "last_toggle_ts": 0,
    }

def _load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = _default_state()
        base.update({k: data.get(k, base[k]) for k in base.keys()})
        base["muted_ids"] = list({int(x) for x in base.get("muted_ids", []) if str(x).lstrip("-").isdigit()})
        base["clean_on"] = bool(base.get("clean_on", False))
        base["emoji_on"] = bool(base.get("emoji_on", False))
        base["aianswers_on"] = bool(base.get("aianswers_on", False))
        base["last_toggle_ts"] = int(base.get("last_toggle_ts", 0) or 0)
        return base
    except Exception:
        return _default_state()

def _save_state(st):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

STATE = _load_state()
MUTED = set(STATE.get("muted_ids", []))

def _is_owner(event) -> bool:
    if OWNER_ID:
        return int(getattr(event.sender_id, 0) or 0) == int(OWNER_ID)
    return bool(getattr(event, "out", False))

def _strip_cmd(text: str) -> str:
    return (text or "").strip()

def _parse_on_off(arg: str) -> Optional[bool]:
    a = (arg or "").strip().lower()
    if a in ("on", "1", "true", "yes", "да", "вкл", "включить", "enable", "enabled"):
        return True
    if a in ("off", "0", "false", "no", "нет", "выкл", "выключить", "disable", "disabled"):
        return False
    return None

SAFE_NUMERIC_RE = re.compile(r"^[\d\s\.\+\-\*\/\%\(\)\^\,]+$")

def _safe_eval_numeric(expr: str):
    expr = (expr or "").strip().replace("^", "**")
    node = ast.parse(expr, mode="eval")
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.FloorDiv, ast.Load
    )
    for n in ast.walk(node):
        if not isinstance(n, allowed):
            raise ValueError("unsafe")
    val = eval(compile(node, "<calc>", "eval"), {"__builtins__": {}}, {})
    if isinstance(val, (int, float)) and math.isfinite(val):
        if isinstance(val, float):
            s = f"{val:.10f}".rstrip("0").rstrip(".")
            return s if s else "0"
        return str(val)
    return str(val)

async def _hf_generate(prompt: str, max_new_tokens: int = 128, temperature: float = 0.7, top_p: float = 0.9) -> str:
    headers = {"Content-Type": "application/json"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": int(max_new_tokens),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "return_full_text": False,
        },
        "options": {"wait_for_model": True}
    }
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(HF_URL, headers=headers, json=payload) as r:
            raw = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"hf_http_{r.status}")
            try:
                data = json.loads(raw)
            except Exception:
                return ""
            if isinstance(data, list) and data:
                item = data[0]
                if isinstance(item, dict) and "generated_text" in item:
                    return (item["generated_text"] or "").strip()
            if isinstance(data, dict) and "generated_text" in data:
                return (data["generated_text"] or "").strip()
            return ""

async def _ai_pick_emoji(text: str) -> str:
    prompt = (
        "Выбери ОДИН наиболее подходящий эмодзи для сообщения ниже. "
        "Ответь только одним эмодзи, без текста.\n\n"
        f"Сообщение:\n{text}"
    )
    try:
        out = await _hf_generate(prompt, max_new_tokens=8, temperature=0.5, top_p=0.9)
    except Exception:
        out = ""
    out = (out or "").strip().split()[0] if (out or "").strip() else ""
    if len(out) > 6:
        out = ""
    return out or DEFAULT_EMOJI_FALLBACK

async def _ai_confirm(feature: str, enabled: bool) -> str:
    prompt = (
        "Сгенерируй очень короткое подтверждение на русском (1 строка), "
        f"что функция '{feature}' теперь {'включена' if enabled else 'выключена'}. "
        "Без кавычек, без пояснений."
    )
    try:
        out = await _hf_generate(prompt, max_new_tokens=24, temperature=0.6, top_p=0.9)
    except Exception:
        out = ""
    out = (out or "").strip() or "Готово."
    if STATE.get("emoji_on", False):
        em = await _ai_pick_emoji(out)
        out = f"{out} {em}"
    return out

async def _ai_clean_text(text: str) -> Tuple[str, bool]:
    original = (text or "")
    if not original.strip():
        return original, False
    prompt = (
        "Задача: замаскировать ненормативную лексику в тексте.\n"
        "Правила:\n"
        "- Только слова с ненормативной лексикой замени на звёздочки той же длины.\n"
        "- Остальной текст НЕ меняй.\n"
        "- Если ненормативной лексики нет — верни текст БЕЗ изменений.\n"
        "- Ответь только итоговым текстом.\n\n"
        f"Текст:\n{original}"
    )
    try:
        out = await _hf_generate(prompt, max_new_tokens=min(220, max(80, len(original) + 24)), temperature=0.2, top_p=0.9)
    except Exception:
        out = ""
    cleaned = (out or "").strip()
    if not cleaned:
        return original, False
    if cleaned == original:
        return original, False
    return cleaned, True

async def _ai_reply(text: str, context: str = "") -> str:
    base = (
        "Ты в Telegram. Ответь естественно, дружелюбно и кратко на русском.\n"
        "Не упоминай, что ты модель. Не используй markdown.\n"
    )
    if context:
        prompt = f"{base}\nКонтекст:\n{context}\n\nСообщение:\n{text}\n\nОтвет:"
    else:
        prompt = f"{base}\nСообщение:\n{text}\n\nОтвет:"
    try:
        out = await _hf_generate(prompt, max_new_tokens=240, temperature=0.8, top_p=0.9)
    except Exception:
        out = ""
    out = (out or "").strip() or "Понял."
    return out

async def _delete_after(chat_id: int, msg_id: int, delay: float):
    try:
        await asyncio.sleep(delay)
        await client.delete_messages(chat_id, msg_id)
    except Exception:
        pass

client = TelegramClient(StringSession(SESSION_STRING) if SESSION_STRING else "tb_session", API_ID, API_HASH)

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}protocol(?:\s+.*)?$", re.I)))
async def cmd_protocol(event):
    if not _is_owner(event):
        return
    try:
        await event.delete()
    except Exception:
        pass
    msg = await client.send_message(event.chat_id, "0%")
    p = 0
    while p < 100:
        p = min(100, p + random.randint(1, 4))
        try:
            await msg.edit(f"{p}%")
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.12, 0.28))
    asyncio.create_task(_delete_after(event.chat_id, msg.id, 0.8))

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}dox(?:\s+.*)?$", re.I)))
async def cmd_dox(event):
    if not _is_owner(event):
        return
    try:
        await event.delete()
    except Exception:
        pass
    out = "Команда .dox отключена по соображениям безопасности."
    if STATE.get("emoji_on", False):
        em = await _ai_pick_emoji(out)
        out = f"{out} {em}"
    await client.send_message(event.chat_id, out)

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}mute(?:\s+.+)?$", re.I)))
async def cmd_mute(event):
    if not _is_owner(event):
        return
    args = _strip_cmd(event.raw_text)[len(CMD_PREFIX) + 4:].strip()
    target_id = None
    if event.is_reply:
        try:
            rep = await event.get_reply_message()
            target_id = int(rep.sender_id or 0)
        except Exception:
            target_id = None
    if not target_id and args:
        m = re.search(r"-?\d+", args)
        if m:
            try:
                target_id = int(m.group(0))
            except Exception:
                target_id = None
    try:
        await event.delete()
    except Exception:
        pass
    if not target_id:
        return
    MUTED.add(target_id)
    STATE["muted_ids"] = list(MUTED)
    _save_state(STATE)

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}unmute(?:\s+.+)?$", re.I)))
async def cmd_unmute(event):
    if not _is_owner(event):
        return
    args = _strip_cmd(event.raw_text)[len(CMD_PREFIX) + 6:].strip()
    target_id = None
    if event.is_reply:
        try:
            rep = await event.get_reply_message()
            target_id = int(rep.sender_id or 0)
        except Exception:
            target_id = None
    if not target_id and args:
        m = re.search(r"-?\d+", args)
        if m:
            try:
                target_id = int(m.group(0))
            except Exception:
                target_id = None
    try:
        await event.delete()
    except Exception:
        pass
    if not target_id:
        return
    if target_id in MUTED:
        MUTED.discard(target_id)
        STATE["muted_ids"] = list(MUTED)
        _save_state(STATE)

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}clean(?:\s+.+)?$", re.I)))
async def cmd_clean(event):
    if not _is_owner(event):
        return
    args = _strip_cmd(event.raw_text)[len(CMD_PREFIX) + 5:].strip()
    val = _parse_on_off(args)
    try:
        await event.delete()
    except Exception:
        pass
    if val is None:
        return
    STATE["clean_on"] = bool(val)
    STATE["last_toggle_ts"] = _now_ms()
    _save_state(STATE)
    await client.send_message(event.chat_id, await _ai_confirm("clean", STATE["clean_on"]))

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}emoji(?:\s+.+)?$", re.I)))
async def cmd_emoji(event):
    if not _is_owner(event):
        return
    args = _strip_cmd(event.raw_text)[len(CMD_PREFIX) + 5:].strip()
    val = _parse_on_off(args)
    try:
        await event.delete()
    except Exception:
        pass
    if val is None:
        return
    STATE["emoji_on"] = bool(val)
    STATE["last_toggle_ts"] = _now_ms()
    _save_state(STATE)
    await client.send_message(event.chat_id, await _ai_confirm("emoji", STATE["emoji_on"]))

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}aianswers(?:\s+.+)?$", re.I)))
async def cmd_aianswers(event):
    if not _is_owner(event):
        return
    args = _strip_cmd(event.raw_text)[len(CMD_PREFIX) + 9:].strip()
    val = _parse_on_off(args)
    try:
        await event.delete()
    except Exception:
        pass
    if val is None:
        return
    STATE["aianswers_on"] = bool(val)
    STATE["last_toggle_ts"] = _now_ms()
    _save_state(STATE)
    await client.send_message(event.chat_id, await _ai_confirm("aianswers", STATE["aianswers_on"]))

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}calc(?:\s+.+)?$", re.I)))
async def cmd_calc(event):
    if not _is_owner(event):
        return
    expr = _strip_cmd(event.raw_text)[len(CMD_PREFIX) + 4:].strip()
    try:
        await event.delete()
    except Exception:
        pass
    if not expr:
        out = "Укажи выражение после .calc"
        if STATE.get("emoji_on", False):
            em = await _ai_pick_emoji(out)
            out = f"{out} {em}"
        await client.send_message(event.chat_id, out)
        return
    res = None
    if SAFE_NUMERIC_RE.match(expr):
        try:
            res = _safe_eval_numeric(expr)
        except Exception:
            res = None
    if res is None:
        parts = [p for p in re.split(r"\s+", expr) if p]
        res = "".join(parts)
    out = res
    if STATE.get("emoji_on", False):
        em = await _ai_pick_emoji(out)
        out = f"{out} {em}"
    await client.send_message(event.chat_id, out)

@client.on(events.NewMessage)
async def on_any_message(event):
    if getattr(event, "out", False):
        return

    sender_id = int(getattr(event, "sender_id", 0) or 0)
    if sender_id and sender_id in MUTED:
        try:
            await event.delete()
        except Exception:
            pass
        return

    text = getattr(event, "raw_text", "") or ""
    if text.strip().startswith(CMD_PREFIX):
        return

    if STATE.get("clean_on", False) and text.strip():
        cleaned, changed = await _ai_clean_text(text)
        if changed and cleaned.strip():
            try:
                await event.delete()
            except Exception:
                pass
            try:
                await client.send_message(event.chat_id, cleaned, reply_to=event.reply_to_msg_id or None)
            except Exception:
                pass
            return

    if not STATE.get("aianswers_on", False):
        return

    try:
        me = await client.get_me()
        my_id = int(getattr(me, "id", 0) or 0)
        my_username = (getattr(me, "username", "") or "").lower()
    except Exception:
        my_id = 0
        my_username = ""

    should_answer = False
    if event.is_private:
        should_answer = True
    if not should_answer and my_username and f"@{my_username}" in text.lower():
        should_answer = True
    if not should_answer and event.is_reply and my_id:
        try:
            rep = await event.get_reply_message()
            if rep and int(getattr(rep, "sender_id", 0) or 0) == my_id:
                should_answer = True
        except Exception:
            pass

    if not should_answer:
        return

    ctx = ""
    try:
        if event.is_reply:
            rep = await event.get_reply_message()
            if rep and (rep.raw_text or "").strip():
                ctx = (rep.raw_text or "").strip()
    except Exception:
        ctx = ""

    answer = await _ai_reply(text, context=ctx)
    if STATE.get("emoji_on", False):
        em = await _ai_pick_emoji(answer)
        answer = f"{answer} {em}"
    try:
        await client.send_message(event.chat_id, answer, reply_to=event.id)
    except Exception:
        pass

async def main():
    if API_ID <= 0 or not API_HASH:
        raise RuntimeError("TG_API_ID/TG_API_HASH не заданы")
    await client.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
