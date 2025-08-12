#!/usr/bin/env python3
from __future__ import annotations
import os
from dotenv import load_dotenv

# Always load .env from repo root first
_ROOT = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_ROOT, ".env")
if os.path.isfile(_ENV_PATH):
    load_dotenv(_ENV_PATH, override=True)
from typing import Set

def _env(key: str, default: str|None=None) -> str|None:
    v = os.environ.get(key)
    return v if (v is not None and str(v) != "") else default

# Telegram
TELEGRAM_BOT_TOKEN: str = _env("TELEGRAM_BOT_TOKEN", "") or ""
TELEGRAM_ALLOWED_CHAT_IDS: Set[str] = set([x.strip() for x in (_env("TELEGRAM_ALLOWED_CHAT_IDS", "") or "").split(",") if x.strip()])
TELEGRAM_FALLBACK_CHAT_ID: str = _env("TELEGRAM_CHAT_ID", "") or ""

# Paths / runtime
TZ: str = _env("TZ", "Asia/Kolkata") or "Asia/Kolkata"
ART_DIR: str = _env("ART_DIR", "./artifacts") or "./artifacts"
STATE_DB: str = _env("STATE_DB", f"{ART_DIR}/state.db") or f"{ART_DIR}/state.db"
DATABASE_URL: str = _env("DATABASE_URL", f"sqlite:///{STATE_DB}") or f"sqlite:///{STATE_DB}"
BOT_OFFSET_FILE: str = _env("BOT_OFFSET_FILE", f"{ART_DIR}/bot_offset.txt") or f"{ART_DIR}/bot_offset.txt"
DEFAULT_DAILY_TIME: str = _env("DEFAULT_DAILY_TIME", "09:00") or "09:00"

# Chrome / scraping
CHROME_BINARY: str|None = _env("CHROME_BINARY", None)
BMS_FORCE_UC: str = _env("BMS_FORCE_UC", "0") or "0"
BMS_CHROME_VERSION_MAIN: str|None = _env("BMS_CHROME_VERSION_MAIN", None)

# Scheduler/worker
SCHEDULER_SLEEP_SEC: int = int(_env("SCHEDULER_SLEEP_SEC", "10") or "10")
DEFAULT_HEARTBEAT_MINUTES: int = int(_env("DEFAULT_HEARTBEAT_MINUTES", "180") or "180")


