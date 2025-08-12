#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
from typing import Optional, Dict, Any

import aiohttp
from aiogram import Bot

from config import TELEGRAM_BOT_TOKEN as _BOT, TELEGRAM_FALLBACK_CHAT_ID as _FALLBACK
from utils import titled

BOT_TOKEN = _BOT
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FALLBACK_CHAT = _FALLBACK

# aiogram bot instance with shared aiohttp session
_session: aiohttp.ClientSession | None = None
_bot: Bot | None = None


def _ensure_session() -> tuple[Bot, aiohttp.ClientSession]:
    """Ensure a shared aiogram Bot and aiohttp session exist."""
    global _session, _bot
    if _session is None:
        _session = aiohttp.ClientSession()
    if _bot is None:
        _bot = Bot(token=BOT_TOKEN, session=_session)
    return _bot, _session


def _effective_chat(chat_id: Optional[str]) -> Optional[str]:
    c = (chat_id or "").strip() or FALLBACK_CHAT
    return c if (c and BOT_TOKEN) else None


async def _post(method: str, *, json: Dict[str, Any] | None = None, data: Dict[str, Any] | None = None,
                params: Dict[str, Any] | None = None, timeout: int = 20) -> aiohttp.ClientResponse:
    bot, session = _ensure_session()
    url = f"{API}/{method}"
    return await session.post(url, json=json, data=data, params=params, timeout=timeout)


async def send_text(chat_id: str | None, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
    chat = _effective_chat(str(chat_id) if chat_id is not None else None)
    if not chat:
        print("[telegram] skipped (no chat or token)")
        return
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [text]
    for chunk in chunks:
        payload = {"chat_id": chat, "text": chunk}
        if reply_markup and chunk == chunks[-1]:
            payload["reply_markup"] = reply_markup
        try:
            resp = await _post("sendMessage", json=payload)
            if resp.status >= 300:
                body = await resp.text()
                print("[telegram] error:", resp.status, body)
        except Exception as e:
            print("[telegram] exception:", e)


async def send_alert(prefix_src, chat_id: str | None, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
    await send_text(chat_id, titled(prefix_src, text), reply_markup=reply_markup)


async def edit_text(chat_id: str, message_id: int, text: str,
                    reply_markup: Optional[Dict[str, Any]] = None) -> None:
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = await _post("editMessageText", json=payload)
        if resp.status >= 300:
            body = await resp.text()
            print("[telegram] edit error:", resp.status, body)
    except Exception as e:
        print("[telegram] edit exception:", e)


async def answer_cbq(cb_id: str, text: str = "") -> None:
    try:
        await _post("answerCallbackQuery", data={"callback_query_id": cb_id, "text": text}, timeout=10)
    except Exception:
        pass


async def get_updates(offset: int) -> dict:
    try:
        bot, session = _ensure_session()
        url = f"{API}/getUpdates"
        async with session.get(url, params={"timeout": 30, "offset": offset + 1}, timeout=35) as resp:
            return await resp.json()
    except Exception as e:
        print("[telegram] getUpdates exception:", e)
        return {"ok": False, "result": []}


async def close_session() -> None:
    global _session, _bot
    if _session is not None:
        await _session.close()
    _session = None
    _bot = None
