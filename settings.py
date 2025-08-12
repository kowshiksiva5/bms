from __future__ import annotations
from typing import Optional, Set
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseSettings, Field, validator

# load .env if present (searches upwards from cwd)
load_dotenv()

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ALLOWED_CHAT_IDS: Set[str] = Field(default_factory=set)

    TZ: str = "Asia/Kolkata"
    ART_DIR: Path = Path("./artifacts")
    STATE_DB: Optional[Path] = None
    BOT_OFFSET_FILE: Optional[Path] = None
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
        art: Path = values.get("ART_DIR", Path("./artifacts"))
        return v or art / "state.db"

    @validator("BOT_OFFSET_FILE", pre=True, always=True)
    def _default_bot_offset_file(cls, v, values):
        art: Path = values.get("ART_DIR", Path("./artifacts"))
        return v or art / "bot_offset.txt"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
