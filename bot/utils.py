from __future__ import annotations
from datetime import datetime
from typing import Optional


def format_date(d: str) -> str:
    """Return human friendly date like '12 Aug'."""
    try:
        return datetime.strptime(d, "%Y%m%d").strftime("%d %b")
    except ValueError:
        return d


def format_date_list(date_str: Optional[str]) -> str:
    """Format comma separated YYYYMMDD list."""
    if not date_str:
        return "—"
    parts = [format_date(x) for x in date_str.split(",") if x]
    return ", ".join(parts) if parts else "—"


def format_time(t: Optional[str]) -> str:
    """Format HH:MM into 'H:MM AM/PM'."""
    if not t:
        return "—"
    try:
        return datetime.strptime(t, "%H:%M").strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return t


def format_window(start: Optional[str], end: Optional[str]) -> str:
    """Combine start and end time into a window string."""
    return f"{format_time(start)}–{format_time(end)}"
