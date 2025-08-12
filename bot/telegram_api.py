#!/usr/bin/env python3
from __future__ import annotations
import requests
from typing import Optional, Dict, Any
from settings import settings

from utils import titled

BOT_TOKEN=settings.TELEGRAM_BOT_TOKEN
API=f"https://api.telegram.org/bot{BOT_TOKEN}"
FALLBACK_CHAT=settings.TELEGRAM_CHAT_ID

def _effective_chat(chat_id: Optional[str]) -> Optional[str]:
    c = (chat_id or "").strip() or FALLBACK_CHAT
    return c if (c and BOT_TOKEN) else None

def _send_raw(payload: Dict[str, Any], reply_markup: Optional[Dict[str, Any]]):
    if reply_markup:
        return requests.post(f"{API}/sendMessage", json={**payload, "reply_markup": reply_markup}, timeout=20)
    return requests.post(f"{API}/sendMessage", data=payload, timeout=20)

def send_text(chat_id: str|None, text: str, reply_markup: Optional[Dict[str, Any]]=None):
    chat = _effective_chat(str(chat_id) if chat_id is not None else None)
    if not chat:
        print("[telegram] skipped (no chat or token)")
        return
    # Telegram message limit ~4096 characters
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)] or [text]
    for chunk in chunks:
        try:
            r = _send_raw({"chat_id": chat, "text": chunk}, reply_markup if chunk == chunks[-1] else None)
            if getattr(r, "status_code", 200) >= 300:
                print("[telegram] error:", r.status_code, getattr(r, "text", ""))
        except Exception as e:
            print("[telegram] exception:", e)

def send_alert(prefix_src, chat_id: str|None, text: str, reply_markup: Optional[Dict[str, Any]]=None):
    send_text(chat_id, titled(prefix_src, text), reply_markup=reply_markup)

def edit_text(chat_id: str, message_id: int, text: str, reply_markup: Optional[Dict[str, Any]]=None):
    payload={"chat_id":chat_id,"message_id":message_id,"text":text}
    try:
        if reply_markup:
            requests.post(f"{API}/editMessageText", json={**payload,"reply_markup":reply_markup}, timeout=20)
        else:
            requests.post(f"{API}/editMessageText", data=payload, timeout=20)
    except Exception as e:
        print("[telegram] edit exception:", e)

def answer_cbq(cb_id: str, text: str=""):
    try:
        requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cb_id, "text": text}, timeout=10)
    except Exception:
        pass

def get_updates(offset: int) -> dict:
    try:
        return requests.get(f"{API}/getUpdates", params={"timeout":30, "offset": offset+1}, timeout=35).json()
    except Exception as e:
        print("[telegram] getUpdates exception:", e)
        return {"ok": False, "result": []}
