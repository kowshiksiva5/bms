#!/usr/bin/env python3
from __future__ import annotations
import os, re, time
from typing import List, Optional, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

from scraper import get_driver, open_and_prepare, parse_theatres

# Defaults (can override via env)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8435017096:AAGuyoNaHK6W0x2huypgBhgfV1BjQUQeqGk")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "953590033")

# ---------------- utils ----------------
def _norm(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "", (s or "").lower())

def _fuzzy_match(name: str, targets: List[str]) -> bool:
    n = _norm(name)
    for t in targets:
        tt = _norm(t)
        if tt and (tt in n or n in tt):
            return True
    return False

def _to_bms_date(date_str: str) -> Optional[str]:
    if not date_str: return None
    s = re.sub(r"\D", "", date_str)
    return s if len(s) == 8 else None

def _ensure_date_in_url(url: str, date: Optional[str]) -> str:
    if not date: return url
    d = _to_bms_date(date)
    if not d: return url
    u = urlparse(url); q = parse_qs(u.query); q["date"] = [d]
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))

def tg_send(text: str, token: Optional[str] = None, chat_id: Optional[str] = None):
    token = token or TELEGRAM_BOT_TOKEN
    chat_id = chat_id or TELEGRAM_CHAT_ID
    if not token or not chat_id: return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat_id, "text": text}, timeout=15)
        return r.status_code < 300
    except Exception:
        return False

def choose(prompt: str, options: List[str]) -> List[str]:
    print(prompt)
    for i, o in enumerate(options, 1):
        print(f"{i}. {o}")
    got = input("Select by number(s) comma-separated, 'all', or Enter to cancel: ").strip().lower()
    if got == "all": return options
    if not got: return []
    try:
        idxs = [int(x) for x in re.split(r"[,\s]+", got) if x.strip().isdigit()]
        return [options[i-1] for i in idxs if 1 <= i <= len(options)]
    except Exception:
        return []

# ------------- core orchestration -------------
def run(url: str, dates: List[str] | None, theatres_wanted: List[str] | None, monitor: bool, interval: int, debug: bool):
    d = get_driver(debug=debug)
    if not d:
        print("Failed to create a browser session."); return
    try:
        if not dates:
            dates = []
            open_and_prepare(d, url)
            soup = BeautifulSoup(d.page_source, "html.parser")
            for a in soup.find_all("a", href=True):
                m = re.search(r"[?&]date=(\d{8})", a["href"])
                if m: dates.append(m.group(1))
            if not dates:
                from datetime import datetime
                dates = [datetime.now().strftime("%Y%m%d")]
            dates = sorted(set(dates))
            print("Detected dates:", ", ".join(dates))

        if not theatres_wanted:
            first_url = _ensure_date_in_url(url, dates[0])
            open_and_prepare(d, first_url); time.sleep(1.5)
            ths = parse_theatres(d)
            names = sorted({name for name, _ in ths})
            chosen = choose("Pick theatres to watch:", names)
            if not chosen: print("No theatres chosen."); return
            theatres_wanted = chosen

        watch_set: Set[str] = set()

        def check_once():
            found = []
            for date in dates:
                target = _ensure_date_in_url(url, date)
                open_and_prepare(d, target)
                for _ in range(2):
                    d.execute_script("window.scrollTo(0, document.body.scrollHeight);"); time.sleep(0.5)
                ths = parse_theatres(d)
                for name, shows in ths:
                    if _fuzzy_match(name, theatres_wanted):
                        for st in shows:
                            key = f"{name}|{date}|{st}"
                            if key not in watch_set:
                                found.append((name, date, st))
            return found

        def fmt(d8): return f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"
        def alert(lines):
            body = "\n".join([f"{n} | {fmt(d)} | {t}" for n,d,t in sorted(lines)])
            print("\nFound shows:\n"+body)
            tg_send(f"New shows on BMS:\n{body}")

        if not monitor:
            lines = check_once()
            if lines: alert(lines); [watch_set.add(f"{n}|{d}|{t}") for n,d,t in lines]
            else: print("No new shows right now."); return
        else:
            print(f"Monitoring every {interval} min. Ctrl+C to stop.")
            while True:
                lines = check_once()
                if lines: alert(lines); [watch_set.add(f"{n}|{d}|{t}") for n,d,t in lines]
                else: print("No new shows.")
                time.sleep(max(60, interval*60))
    finally:
        try: d.quit()
        except Exception: pass

# ------------- CLI -------------
def parse_args(argv=None):
    import argparse
    p = argparse.ArgumentParser("bms-alert")
    p.add_argument("url", help="BMS *buytickets* URL")
    p.add_argument("--dates", help="Comma separated dates YYYY-MM-DD or YYYYMMDD")
    p.add_argument("--theatres", nargs="*", help="Theatre filters")
    p.add_argument("--monitor", action="store_true")
    p.add_argument("--interval", type=int, default=3)
    p.add_argument("--debug", action="store_true")
    return p.parse_args(argv)

def main(argv=None):
    a = parse_args(argv)
    if "/buytickets/" not in a.url:
        print("Please pass a *buytickets* URL."); return
    dates = None
    if a.dates:
        dates = [x.strip() for x in re.split(r"[,\s]+", a.dates) if x.strip()]
        dates = [(_to_bms_date(d) or d) for d in dates]
    run(a.url.strip(), dates, a.theatres, a.monitor, a.interval, a.debug)

if __name__ == "__main__":
    main()
