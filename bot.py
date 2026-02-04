import os
import re
import ast
import json
import time
import math
import asyncio
import random
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.getenv("TG_API_ID", "0") or "0")
API_HASH = os.getenv("TG_API_HASH", "") or ""
SESSION_STRING = os.getenv("TG_SESSION_STRING", "") or ""
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

STATE_FILE = os.getenv("STATE_FILE", "/tmp/tb_state.json")
CMD_PREFIX = "."

def _now_ms() -> int:
    return int(time.time() * 1000)

def _default_state():
    return {"muted_ids": []}

def _load_state():
    p = Path(STATE_FILE)
    if not p.exists():
        s = _default_state()
        _save_state(s)
        return s
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore") or "{}")
    except Exception:
        data = {}
    base = _default_state()
    if isinstance(data, dict):
        base.update({k: data.get(k, base.get(k)) for k in base.keys()})
    if not isinstance(base.get("muted_ids"), list):
        base["muted_ids"] = []
    return base

def _save_state(state: dict):
    p = Path(STATE_FILE)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        try:
            p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

def _is_owner(event) -> bool:
    if OWNER_ID > 0:
        sid = int(getattr(event, "sender_id", 0) or 0)
        return sid == OWNER_ID
    return bool(getattr(event, "out", False))

def _strip_cmd(text: str) -> str:
    return (text or "").strip()

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

async def _delete_after(chat_id: int, msg_id: int, delay: float):
    await asyncio.sleep(max(0.0, float(delay)))
    try:
        await client.delete_messages(chat_id, msg_id)
    except Exception:
        pass

client = TelegramClient(StringSession(SESSION_STRING) if SESSION_STRING else "tb_session", API_ID, API_HASH)

STATE = _load_state()
MUTED = set(int(x) for x in (STATE.get("muted_ids") or []) if isinstance(x, int) or (isinstance(x, str) and str(x).lstrip("-").isdigit()))

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
    asyncio.create_task(_delete_after(int(event.chat_id), int(msg.id), 0.8))

@client.on(events.NewMessage(pattern=re.compile(rf"^{re.escape(CMD_PREFIX)}dox(?:\s+.*)?$", re.I)))
async def cmd_dox(event):
    if not _is_owner(event):
        return
    try:
        await event.delete()
    except Exception:
        pass
    out = "\n".join([
        "IP: <IP> N: <N> Q: <Q>",
        "SS Number: <SSN>",
        "IPv6: <IPV6>",
        "UPNP: <ON/OFF>",
        "DMZ: <DMZ_IP>",
        "MAC: <MAC>",
        "ISP: <ISP>",
        "DNS: <DNS>",
        "ALT DNS: <ALT_DNS>",
        "DNS SUFFIX: <SUFFIX>",
        "WAN <WAN_IP>",
        "WAN TYPE: <TYPE>",
        "GATEWAY: <GATEWAY>",
        "SUBNET MASK: <MASK>",
        "UDP OPEN PORTS: <UDP_PORTS>",
        "TCP OPEN PORTS: <TCP_PORTS>"
    ])
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
            target_id = int(getattr(rep, "sender_id", 0) or 0)
        except Exception:
            target_id = None

    if not target_id and args:
        m = re.search(r"-?\d+", args)
        if m:
            try:
                target_id = int(m.group(0))
            except Exception:
                target_id = None

    if not target_id and event.is_private:
        try:
            target_id = int(getattr(event, "chat_id", 0) or 0)
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
            target_id = int(getattr(rep, "sender_id", 0) or 0)
        except Exception:
            target_id = None

    if not target_id and args:
        m = re.search(r"-?\d+", args)
        if m:
            try:
                target_id = int(m.group(0))
            except Exception:
                target_id = None

    if not target_id and event.is_private:
        try:
            target_id = int(getattr(event, "chat_id", 0) or 0)
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
    try:
        await client.send_message(event.chat_id, res)
    except Exception:
        pass

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

async def main():
    if API_ID <= 0 or not API_HASH:
        raise RuntimeError("Missing TG_API_ID / TG_API_HASH")
    await client.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
