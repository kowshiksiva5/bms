#!/usr/bin/env python3
from __future__ import annotations
import re
import time
from datetime import datetime, timedelta


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def fuzzy(name: str, targets):
    if any((t or "").strip().lower() in ("any", "*") for t in targets or []):
        return True
    n = norm(name)
    return any((tt in n or n in tt) for tt in map(norm, targets or []))


def to_bms_date(date_str: str) -> str | None:
    s = re.sub(r"\D", "", date_str or "")
    return s if len(s) == 8 else None


def ensure_date_in_url(url: str, date: str | None) -> str:
    if not date:
        return url
    s = to_bms_date(date)
    if not s:
        return url
    return url.rstrip("/") + "/" + s


def roll_dates(n: int) -> list[str]:
    today = datetime.now()
    return [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(max(1, n))]


def within_time_window(
    now_ts: int, start_hhmm: str | None, end_hhmm: str | None
) -> bool:
    if not (start_hhmm and end_hhmm):
        return True
    hhmm = time.strftime("%H:%M", time.localtime(now_ts))
    return start_hhmm <= hhmm <= end_hhmm
