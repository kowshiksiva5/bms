#!/usr/bin/env python3
from __future__ import annotations
import os, time, requests
from typing import Optional, Dict, Any

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN","")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_text(chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]]=None):
    try:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            requests.post(f"{API}/sendMessage", json={**payload, "reply_markup": reply_markup}, timeout=20)
        else:
            requests.post(f"{API}/sendMessage", data=payload, timeout=20)
    except Exception as e:
        print("send error", e)

def edit_text(chat_id: str, message_id: int, text: str, reply_markup: Optional[Dict[str, Any]]=None):
    try:
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if reply_markup:
            requests.post(f"{API}/editMessageText", json={**payload, "reply_markup": reply_markup}, timeout=20)
        else:
            requests.post(f"{API}/editMessageText", data=payload, timeout=20)
    except Exception as e:
        print("edit error", e)

def answer_cbq(cb_id: str, text: str=""):
    try:
        requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cb_id, "text": text}, timeout=10)
    except Exception:
        pass

def get_updates(offset: int) -> dict:
    return requests.get(f"{API}/getUpdates", params={"timeout":30, "offset": offset+1}, timeout=35).json()
