from typing import Iterable, List, Optional, Tuple
from math import radians, cos, sin, asin, sqrt
import difflib
import re


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r


def fuzzy_select(options: List[str], prompt: str) -> str:
    print(prompt)
    for idx, opt in enumerate(options, 1):
        print(f"{idx}. {opt}")
    choice = input("Select by number or type a name: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass
    matches = difflib.get_close_matches(choice, options, n=1, cutoff=0.5)
    if matches:
        print(f"Selected (fuzzy match): {matches[0]}")
        return matches[0]
    print("Invalid selection. Please try again.")
    return fuzzy_select(options, prompt)


def parse_time_to_minutes(hhmm: str) -> Optional[int]:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", hhmm.strip())
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2))
    if h < 0 or h > 23 or mi < 0 or mi > 59:
        return None
    return h * 60 + mi


def is_time_in_range(time_text: str, start_hhmm: str, end_hhmm: str) -> bool:
    # Accept formats like '10:30 AM', '22:15', '10:30AM'
    time_text = time_text.strip().upper().replace(" ", "")
    ampm = None
    if time_text.endswith("AM") or time_text.endswith("PM"):
        ampm = time_text[-2:]
        core = time_text[:-2]
    else:
        core = time_text
    if ':' not in core:
        return False
    hh_str, mm_str = core.split(':', 1)
    try:
        hh = int(hh_str)
        mm = int(mm_str)
    except ValueError:
        return False
    if ampm:
        if hh == 12:
            hh = 0
        if ampm == 'PM':
            hh += 12
    t_min = hh * 60 + mm
    s = parse_time_to_minutes(start_hhmm)
    e = parse_time_to_minutes(end_hhmm)
    if s is None or e is None:
        return False
    if s <= e:
        return s <= t_min <= e
    # Overnight range, e.g. 22:00-02:00
    return t_min >= s or t_min <= e


