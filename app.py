#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, json
from typing import List, Optional, Set
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from scraper import (
    get_driver, open_and_prepare_resilient, parse_theatres, set_trace
)

# Defaults (override via env if you want)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8435017096:AAGuyoNaHK6W0x2huypgBhgfV1BjQUQeqGk")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "953590033")

# ---------------- utils ----------------
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s?(AM|PM)\b", re.I)

def _canon_time(label: str) -> str:
    """Return canonical HH:MM AM/PM to avoid duplicate alerts from cosmetic label changes."""
    m = _TIME_RE.search(label or "")
    return m.group(0).upper() if m else (label or "").strip()

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

def _fuzzy_match(name: str, targets: List[str]) -> bool:
    if any(t.strip().lower() in ("any", "*") for t in (targets or [])):
        return True
    n = _norm(name)
    return any((tt in n or n in tt) for tt in map(_norm, targets or []))

def _to_bms_date(date_str: str) -> Optional[str]:
    if not date_str: return None
    s = re.sub(r"\D", "", date_str)
    return s if len(s) == 8 else None

def _ensure_date_in_url(url: str, date: Optional[str]) -> str:
    """BMS buytickets prefers /YYYYMMDD as a path suffix."""
    if not date: return url
    d = _to_bms_date(date)
    if not d: return url
    if url.endswith("/"): return url + d
    return url + "/" + d

def _roll_dates(days: int) -> List[str]:
    today = datetime.now()
    return [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(max(1, days))]

def _load_seen(path: Optional[str]) -> Set[str]:
    if not path: return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data if isinstance(data, list) else [])
    except Exception:
        return set()

def _save_seen(path: Optional[str], seen: Set[str]):
    if not path: return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen)), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def tg_send(text: str, dry: bool = False):
    """Send using form-encoded payload (like curl). Splits long messages."""
    if dry:
        print("[telegram dry-run]\n" + text)
        return True
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)] or [text]
    ok_all = True
    for chunk in chunks:
        try:
            r = requests.post(api, data={"chat_id": TELEGRAM_CHAT_ID, "text": chunk}, timeout=20)
            if r.status_code >= 300:
                print("[telegram] error:", r.status_code, r.text)
                ok_all = False
        except Exception as e:
            print("[telegram] exception:", e)
            ok_all = False
    return ok_all

def choose(prompt: str, options: List[str]) -> List[str]:
    print(prompt)
    if options:
        for i, o in enumerate(options, 1):
            print(f"{i}. {o}")
    else:
        print("(no theatres found on page yet)")
    got = input("Select by number(s), type names, 'all', 'any', or Enter to cancel: ").strip()
    if not got: return []
    low = got.lower()
    if low == "all":
        return options or ["any"]
    if low in ("any", "*"):
        return ["any"]
    nums = [x for x in re.split(r"[,\s]+", got) if x.strip().isdigit()]
    if nums and options:
        idxs = [int(x) for x in nums]
        return [options[i-1] for i in idxs if 1 <= i <= len(options)]
    return [x.strip() for x in re.split(r"[,\n;]+", got) if x.strip()]

# ------------- core orchestration -------------
def run(url: str, dates: List[str] | None, theatres_wanted: List[str] | None,
        monitor: bool, interval: int, debug: bool, trace: bool, artifacts_dir: Optional[str],
        dry_alerts: bool, exit_on_alert: bool, baseline: bool, days: Optional[int],
        state_file: Optional[str], heartbeat_minutes: int, start_alert: bool):
    set_trace(trace, artifacts_dir)

    d = get_driver(debug=debug)
    if not d:
        print("Failed to create a browser session.")
        return
    try:
        # 1) Resolve dates
        if not dates:
            if days and days > 0:
                dates = _roll_dates(days)
            else:
                dates = []
                d = open_and_prepare_resilient(d, url, debug=debug)
                soup = BeautifulSoup(d.page_source, "html.parser")
                for a in soup.find_all("a", href=True):
                    m = re.search(r"/(\d{8})(?:[/?#]|$)", a["href"])
                    if m: dates.append(m.group(1))
                if not dates:
                    dates = _roll_dates(1)
            dates = sorted(set(dates))
            print("Monitoring dates:", ", ".join(dates))

        # 2) Resolve theatres (also send the list to Telegram to test alerts)
        if not theatres_wanted:
            first_url = _ensure_date_in_url(url, dates[0])
            d = open_and_prepare_resilient(d, first_url, debug=debug); time.sleep(1.0)
            ths = parse_theatres(d)
            names = sorted({n for n, _ in ths})

            if names:
                tg_send("BMS theatre list for testing:\n" + "\n".join(f"- {n}" for n in names), dry=dry_alerts)
            else:
                tg_send("BMS theatre list for testing: (none visible yet on the page)", dry=dry_alerts)

            chosen = choose("Pick theatres to watch (you can also type names or 'any'):", names)
            if not chosen:
                print("No theatres chosen. Tip: re-run with --theatres 'any' to monitor all.")
                return
            theatres_wanted = chosen

        # 3) Dedupe across restarts
        seen: Set[str] = _load_seen(state_file)

        # Optional: baseline pass to avoid alerting on existing showtimes
        if baseline:
            for date in dates:
                target = _ensure_date_in_url(url, date)
                d = open_and_prepare_resilient(d, target, debug=debug)
                for name, shows in parse_theatres(d):
                    if _fuzzy_match(name, theatres_wanted):
                        for st in shows:
                            seen.add(f"{name}|{date}|{_canon_time(st)}")
            _save_seen(state_file, seen)
            tg_send("Baseline captured. Will alert only on **newly added** showtimes.", dry=dry_alerts)

        # 4) Heartbeat / start alert setup
        start_ts = time.time()
        checks_done = 0
        alerts_sent_total = 0
        last_alert_ts: Optional[float] = None
        last_heartbeat_ts = time.time()

        def fmt_dt(ts: Optional[float]) -> str:
            if not ts: return "—"
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

        if monitor and start_alert:
            intro = [
                "BMS monitor started ✅",
                f"URL: {url}",
                f"Dates: {', '.join(dates)}",
                f"Theatres: {len(theatres_wanted)} selected",
                f"Interval: {interval} min",
            ]
            if state_file: intro.append(f"State file: {state_file}")
            if baseline:  intro.append("Mode: baseline active (alert only on new shows)")
            tg_send("\n".join(intro), dry=dry_alerts)

        def maybe_heartbeat():
            nonlocal last_heartbeat_ts
            if heartbeat_minutes <= 0: return
            now = time.time()
            if now - last_heartbeat_ts >= heartbeat_minutes * 60:
                body = [
                    "Heartbeat: monitor running 💡",
                    f"Since: {fmt_dt(start_ts)}",
                    f"Checks: {checks_done}",
                    f"New shows alerted: {alerts_sent_total}",
                    f"Last alert at: {fmt_dt(last_alert_ts)}",
                    f"Dates: {', '.join(dates)}",
                    f"Theatres: {len(theatres_wanted)}"
                ]
                tg_send("\n".join(body), dry=dry_alerts)
                last_heartbeat_ts = now

        # 5) Main pass / loop
        def check_once():
            nonlocal d
            found = []
            for date in dates:
                target = _ensure_date_in_url(url, date)
                d = open_and_prepare_resilient(d, target, debug=debug)
                for _ in range(2):
                    d.execute_script("window.scrollTo(0, document.body.scrollHeight);"); time.sleep(0.5)
                for name, shows in parse_theatres(d):
                    if _fuzzy_match(name, theatres_wanted):
                        for st in shows:
                            tcanon = _canon_time(st)
                            key = f"{name}|{date}|{tcanon}"
                            if key not in seen:
                                found.append((name, date, tcanon))
            return found

        def fmt_date(d8): return f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"
        def alert(lines):
            body = "\n".join([f"{n} | {fmt_date(d_)} | {t}" for n,d_,t in sorted(lines)])
            print("\nFound shows:\n" + body)
            tg_send(f"New shows on BMS:\n{body}", dry=dry_alerts)

        if not monitor:
            lines = check_once()
            if lines:
                alert(lines)
                for n,d_,t in lines: seen.add(f"{n}|{d_}|{t}")
                _save_seen(state_file, seen)
            else:
                print("No new shows right now.")
                return
        else:
            print(f"Monitoring every {interval} min. Ctrl+C to stop.")
            while True:
                lines = check_once()
                checks_done += 1
                if lines:
                    alert(lines)
                    for n,d_,t in lines: seen.add(f"{n}|{d_}|{t}")
                    _save_seen(state_file, seen)
                    alerts_sent_total += len(lines)
                    last_alert_ts = time.time()
                    if exit_on_alert:
                        print("Exit on first alert: done.")
                        return
                else:
                    print("No new shows.")
                maybe_heartbeat()
                time.sleep(max(60, interval*60))
    finally:
        try: d.quit()
        except Exception: pass

# ------------- CLI -------------
def parse_args(argv=None):
    import argparse
    p = argparse.ArgumentParser("bms-alert")
    p.add_argument("url")
    p.add_argument("--dates", help="Comma separated dates YYYY-MM-DD or YYYYMMDD")
    p.add_argument("--days", type=int, help="If --dates not provided, monitor today+next N-1 days")
    p.add_argument("--theatres", nargs="*", help="Theatre filters (use 'any' to monitor all)")
    p.add_argument("--monitor", action="store_true")
    p.add_argument("--interval", type=int, default=3)
    p.add_argument("--debug", action="store_true", help="Show browser window")
    p.add_argument("--trace", action="store_true", help="Verbose logs + save HTML/PNG artifacts")
    p.add_argument("--artifacts-dir", default="./artifacts")
    p.add_argument("--dry-alerts", action="store_true", help="Print alerts instead of Telegram")
    p.add_argument("--exit-on-alert", action="store_true", help="Stop after sending the first alert")
    p.add_argument("--baseline", action="store_true", help="Seed with current showtimes; alert only on new ones")
    p.add_argument("--state-file", help="Persist dedupe state to a JSON file (e.g. /artifacts/seen.json)")
    p.add_argument("--heartbeat-minutes", type=int, default=180, help="Send a summary heartbeat every N minutes (0 to disable)")
    p.add_argument("--no-start-alert", action="store_true", help="Don't send the initial 'monitor started' alert")
    return p.parse_args(argv)

def _to_bms_date(date_str: str) -> Optional[str]:
    if not date_str: return None
    s = re.sub(r"\D", "", date_str)
    return s if len(s) == 8 else None

def main(argv=None):
    a = parse_args(argv)
    dates = None
    if a.dates:
        dates = [x.strip() for x in re.split(r"[,\s]+", a.dates) if x.strip()]
        dates = [(_to_bms_date(d) or d) for d in dates]
    run(a.url.strip(), dates, a.theatres, a.monitor, a.interval,
        a.debug, a.trace, a.artifacts_dir, a.dry_alerts,
        a.exit_on_alert, a.baseline, a.days, a.state_file,
        a.heartbeat_minutes, start_alert=(not a.no_start_alert))

if __name__ == "__main__":
    main()
