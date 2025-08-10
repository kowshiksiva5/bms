#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, json, traceback
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from utils import titled

import requests

from store import (
    connect, get_active_monitors, get_monitor, set_state, set_reload, set_dates,
    get_indexed_theatres, upsert_indexed_theatre, bulk_upsert_seen, is_seen, set_baseline_done
)
from common import ensure_date_in_url, fuzzy, roll_dates, to_bms_date, within_time_window
from scraper import set_trace as set_scr_trace, get_driver, open_and_prepare_resilient, parse_theatres

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","")
FALLBACK_CHAT = os.environ.get("TELEGRAM_CHAT_ID","")

# ---------- Telegram ----------
def tg_send(chat_id: str, text: str):
    """Raw Telegram sender with fallback chat."""
    if not chat_id: chat_id = FALLBACK_CHAT
    if not chat_id or not BOT_TOKEN:
        print("[telegram] skipped (no chat or token)")
        return
    api=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chunk in [text[i:i+4000] for i in range(0,len(text),4000)] or [text]:
        try:
            r=requests.post(api, data={"chat_id": chat_id, "text": chunk}, timeout=20)
            if r.status_code>=300: print("[telegram] error:", r.status_code, r.text)
        except Exception as e:
            print("[telegram] exception:", e)

# ---------- helpers ----------
def _fmt_date(d8: str)->str: return f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"
def _now_i(): return int(time.time())

def _effective_dates(row)->List[str]:
    mode=(row["mode"] or "FIXED").upper()
    if mode=="ROLLING":
        days=max(1,int(row["rolling_days"] or 1))
        return roll_dates(days)
    if mode=="UNTIL":
        end=to_bms_date(row["end_date"] or "")
        if not end: return [x for x in (row["dates"] or "").split(",") if x]
        today=int(datetime.now().strftime("%Y%m%d"))
        endi=int(end)
        if today>endi: return []
        span=[]; cur=datetime.now()
        while int(cur.strftime("%Y%m%d"))<=endi:
            span.append(cur.strftime("%Y%m%d"))
            cur=cur+timedelta(days=1)
        return span
    return [x for x in (row["dates"] or "").split(",") if x]

def _should_run_now(row)->bool:
    if row["state"] not in ("RUNNING","DISCOVER"): return False
    if row["snooze_until"] and _now_i() < int(row["snooze_until"]): return False
    if not within_time_window(_now_i(), row["time_start"], row["time_end"]): return False
    return True

def _deeplink(row: dict, d8: str) -> str:
    """Try to build a buytickets deep link using ET code; fall back to date-injected URL."""
    m = re.search(r"(ET\d{5,})", row["url"] or "")
    if m:
        et = m.group(1)
        return f"https://in.bookmyshow.com/buytickets/{et}/{d8}"
    return ensure_date_in_url(row["url"], d8)

def _format_scope(row: dict) -> str:
    try:
        the = json.loads(row["theatres"]) if row.get("theatres") else []
    except Exception:
        the = []
    return "any" if "any" in the or not the else f"{len(the)} theatres"

def _format_new_shows(row: dict, found: List[Tuple[str,str,str]]) -> str:
    """
    found: list of (theatre_name, YYYYMMDD, '11:10 PM')
    Nice, grouped message with counts + deep link.
    """
    # bucket by date, then theatre → times
    by_date: Dict[str, Dict[str, List[str]]] = {}
    total_times = 0
    for nm, d8, t in found:
        by_date.setdefault(d8, {}).setdefault(nm, []).append(t)
        total_times += 1

    # build rows
    lines = []
    for d8 in sorted(by_date.keys()):
        lines.append(f"🗓 {_fmt_date(d8)}")
        for nm in sorted(by_date[d8].keys()):
            times = ", ".join(sorted(set(by_date[d8][nm])))
            lines.append(f"  • 🏟 {nm}: {times}")
        lines.append("")  # blank between dates

    first_d8 = sorted(by_date.keys())[0]
    link = _deeplink(row, first_d8)

    header = (
        f"🎟️ New shows\n"
        f"🔎 Monitor: {row['id']} • every {row.get('interval_min','?')}m • Theatres: {_format_scope(row)}\n"
        f"🔗 {link}\n"
    )
    summary = f"\nTotals: {total_times} time(s) • {sum(len(v) for v in by_date.values())} theatre entries • {len(by_date)} date(s)"
    body = header + "\n".join(lines).rstrip() + summary
    return titled(row, body)

# ---------- selenium driver ----------
class DriverManager:
    def __init__(self, debug: bool=False, trace: bool=False, artifacts_dir: str="./artifacts"):
        self.debug = debug
        self.trace = trace
        self.artifacts_dir = artifacts_dir
        self.d = None
        set_scr_trace(trace, artifacts_dir)

    def ensure(self):
        if self.d: return self.d
        self.d = get_driver(debug=self.debug)
        if not self.d:
            raise RuntimeError("Failed to start Chrome driver")
        return self.d

    def reset(self):
        try:
            if self.d: self.d.quit()
        except Exception:
            pass
        self.d = None

    def open(self, url: str):
        d = self.ensure()
        return open_and_prepare_resilient(d, url, debug=self.debug)

# ---------- actions ----------
def _run_discover(dm: DriverManager, row):
    eff = _effective_dates(row) or roll_dates(1)
    date = eff[0]
    url = ensure_date_in_url(row["url"], date)
    d = dm.open(url)
    pairs = parse_theatres(d)
    names = sorted({n for n,_ in pairs})
    with connect() as conn:
        for nm in names:
            upsert_indexed_theatre(conn, row["id"], date, nm)
        set_state(conn, row["id"], "PAUSED")
    chat = str(row["owner_chat_id"] or "")
    tg_send(chat, titled(row, f"🧭 Discover complete for [{row['id']}]\n"
                              f"Captured {len(names)} theatres for {_fmt_date(date)}.\n"
                              f"State set to PAUSED.\n"
                              f"🔗 {_deeplink(row, date)}"))

def _run_monitor(dm: DriverManager, row, heartbeat_book: Dict[str,int]):
    mid = row["id"]; chat=str(row["owner_chat_id"] or "")
    eff_dates = _effective_dates(row)
    if not eff_dates:
        if (row["mode"] or "FIXED").upper()=="UNTIL":
            with connect() as conn: set_state(conn, mid, "PAUSED")
            tg_send(chat, titled(row, f"⏸️ [{mid}] End date reached; auto-paused."))
        return

    # one-time baseline
    if int(row["baseline"] or 0) == 1:
        try:
            for d8 in eff_dates:
                turl = ensure_date_in_url(row["url"], d8)
                d = dm.open(turl)
                for name, shows in parse_theatres(d):
                    twanted = json.loads(row["theatres"]) if row["theatres"] else []
                    if not twanted or fuzzy(name, twanted):
                        with connect() as conn:
                            bulk_upsert_seen(conn, [(mid, d8, name, st, _now_i()) for st in shows])
            with connect() as conn: set_baseline_done(conn, mid)
            tg_send(chat, titled(row, f"📏 Baseline captured for [{mid}] — alerts will fire only on newly added showtimes."))
        except Exception as e:
            tg_send(chat, titled(row, f"⚠️ Baseline failed for [{mid}]: {e}"))

    found: List[Tuple[str,str,str]] = []
    try:
        for d8 in eff_dates:
            turl = ensure_date_in_url(row["url"], d8)
            d = dm.open(turl)
            try:
                for _ in range(2):
                    d.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
            except Exception:
                pass
            pairs = parse_theatres(d)
            with connect() as conn:
                for nm,_ in pairs: upsert_indexed_theatre(conn, mid, d8, nm)
            twanted = json.loads(row["theatres"]) if row["theatres"] else []
            for nm, shows in pairs:
                if not twanted or fuzzy(nm, twanted):
                    for st in shows:
                        with connect() as conn:
                            if not is_seen(conn, mid, d8, nm, st):
                                found.append((nm, d8, st))
    except Exception:
        dm.reset()
        raise

    if found:
        tg_send(chat, _format_new_shows(row, found))
        with connect() as conn:
            bulk_upsert_seen(conn, [(mid, d, n, t, _now_i()) for n,d,t in found])
            conn.execute("UPDATE monitors SET last_alert_ts=?, updated_at=? WHERE id=?", (_now_i(), _now_i(), mid))
            conn.commit()

def _send_heartbeat_if_due(row, heartbeat_book: Dict[str,int]):
    """Send heartbeat independently of scraping, so you always get a health ping."""
    mid = row["id"]; chat=str(row["owner_chat_id"] or "")
    hb_every = int(row["heartbeat_minutes"] or 180)
    now = _now_i()
    last_sent = heartbeat_book.get(mid, 0)
    if now - last_sent < hb_every*60:
        return
    eta = 0
    if row["last_run_ts"] and row["interval_min"]:
        eta = int(row["last_run_ts"]) + int(row["interval_min"])*60 - now
        eta = max(0, eta)
    link = _deeplink(row, (_effective_dates(row) or roll_dates(1))[0])
    msg = (
        f"💓 Heartbeat [{mid}]\n"
        f"State: {row['state']} • every {row['interval_min']}m • Theatres: {_format_scope(row)}\n"
        f"Next run in ~ {eta//60}m {eta%60}s\n"
        f"🔗 {link}"
    )
    tg_send(chat, titled(row, msg))
    heartbeat_book[mid] = now

# ---------- main loop ----------
class DriverManager:
    def __init__(self, debug: bool=False, trace: bool=False, artifacts_dir: str="./artifacts"):
        self.debug = debug
        self.trace = trace
        self.artifacts_dir = artifacts_dir
        self.d = None
        set_scr_trace(trace, artifacts_dir)

    def ensure(self):
        if self.d: return self.d
        self.d = get_driver(debug=self.debug)
        if not self.d:
            raise RuntimeError("Failed to start Chrome driver")
        return self.d

    def reset(self):
        try:
            if self.d: self.d.quit()
        except Exception:
            pass
        self.d = None

    def open(self, url: str):
        d = self.ensure()
        return open_and_prepare_resilient(d, url, debug=self.debug)

def main_loop(debug=False, trace=False, artifacts_dir="./artifacts", sleep_sec=10):
    dm = DriverManager(debug=debug, trace=trace, artifacts_dir=artifacts_dir)
    heartbeat_book: Dict[str,int] = {}

    while True:
        try:
            with connect() as conn:
                rows = get_active_monitors(conn)
            now = _now_i()

            for r in rows:
                try:
                    # always consider heartbeat first (even if not due to run)
                    _send_heartbeat_if_due(r, heartbeat_book)

                    if int(r["reload"] or 0) == 1:
                        dm.reset()
                        with connect() as conn:
                            conn.execute("UPDATE monitors SET reload=0, updated_at=? WHERE id=?", (now, r["id"])); conn.commit()

                    if r["state"] == "STOPPING":
                        with connect() as conn:
                            set_state(conn, r["id"], "STOPPED")
                        tg_send(str(r["owner_chat_id"] or ""), titled(r, f"⏹️ [{r['id']}] Stopped."))
                        continue

                    if not _should_run_now(r):
                        continue

                    last = int(r["last_run_ts"] or 0)
                    ivl = max(60, int(r["interval_min"] or 5)*60)
                    if r["state"] == "DISCOVER" or now - last >= ivl:
                        with connect() as conn:
                            conn.execute("UPDATE monitors SET last_run_ts=?, updated_at=? WHERE id=?", (now, now, r["id"])); conn.commit()
                        if r["state"] == "DISCOVER":
                            _run_discover(dm, r)
                        else:
                            _run_monitor(dm, r, heartbeat_book)
                except Exception as e:
                    tg_send(str(r["owner_chat_id"] or ""), titled(r, f"⚠️ Error on [{r['id']}]: {e}"))
                    print("monitor error:", e)
        except Exception as outer:
            print("scheduler loop error:", outer)
            time.sleep(3)
        time.sleep(sleep_sec)

def parse_args(argv=None):
    import argparse
    p = argparse.ArgumentParser("bms-scheduler")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--artifacts-dir", default="./artifacts")
    p.add_argument("--sleep-sec", type=int, default=10)
    return p.parse_args(argv)

def main(argv=None):
    a = parse_args(argv)
    set_scr_trace(a.trace, a.artifacts_dir)
    main_loop(debug=a.debug, trace=a.trace, artifacts_dir=a.artifacts_dir, sleep_sec=a.sleep_sec)

if __name__ == "__main__":
    main()
