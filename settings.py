from __future__ import annotations
from typing import Set, Optional
from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv
from pathlib import Path

# load .env from repository root
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ALLOWED_CHAT_IDS: Set[str] = Field(default_factory=set)

    TZ: str = "Asia/Kolkata"
    ART_DIR: str = "./artifacts"
    STATE_DB: Optional[str] = None
    BOT_OFFSET_FILE: Optional[str] = None
    DEFAULT_DAILY_TIME: str = "09:00"

    CHROME_BINARY: Optional[str] = None
    CHROMIUM_BINARY: Optional[str] = None
    BMS_FORCE_UC: bool = True
    BMS_USER_DATA_DIR: Optional[str] = None
    BMS_PROFILE_DIR: str = "Default"
    BMS_CHROME_VERSION_MAIN: Optional[int] = None

    SCHEDULER_SLEEP_SEC: int = 10
    DEFAULT_HEARTBEAT_MINUTES: int = 180

    @validator("TELEGRAM_ALLOWED_CHAT_IDS", pre=True)
    def _parse_chat_ids(cls, v):
        if isinstance(v, str):
            return {x.strip() for x in v.split(",") if x.strip()}
        return v or set()

    @validator("STATE_DB", pre=True, always=True)
    def _default_state_db(cls, v, values):
        art = values.get("ART_DIR", "./artifacts")
        return v or f"{art}/state.db"

    @validator("BOT_OFFSET_FILE", pre=True, always=True)
    def _default_bot_offset_file(cls, v, values):
        art = values.get("ART_DIR", "./artifacts")
        return v or f"{art}/bot_offset.txt"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
