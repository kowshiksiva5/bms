#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, json, signal, sqlite3, secrets
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from scraper import (
    get_driver, open_and_prepare_resilient, parse_theatres, set_trace
)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")

# ---------- time helpers ----------
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s?(AM|PM)\b", re.I)
def _canon_time(label: str) -> str:
    m = _TIME_RE.search(label or "")
    return (m.group(0).upper() if m else (label or "").strip())

def _to_minutes(tcanon: str) -> Optional[int]:
    m = _TIME_RE.search(tcanon or "")
    if not m: return None
    h = int(m.group(1)); mnt = int(m.group(2)); ampm = m.group(3).upper()
    if h==12: h = 0
    if ampm=="PM": h += 12
    return h*60 + mnt

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
    if not date: return url
    d = _to_bms_date(date)
    if not d: return url
    if url.endswith("/"): return url + d
    return url + "/" + d

def _roll_dates(days: int) -> List[str]:
    today = datetime.now()
    return [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(max(1, days))]

def fmt_dt(ts: Optional[float]) -> str:
    if not ts: return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

def tg_send(text: str, dry: bool = False, reply_markup: dict|None=None):
    if dry:
        print("[telegram dry-run]\n" + text)
        return True
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] missing env; message:\n", text)
        return True
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        if reply_markup:
            r = requests.post(api, json={**payload, "reply_markup": reply_markup}, timeout=20)
        else:
            r = requests.post(api, data=payload, timeout=20)
        if r.status_code >= 300:
            print("[telegram] error:", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        print("[telegram] exception:", e)
        return False

def inline_controls(mid: str, running: bool=True) -> dict:
    row1 = [
        {"text":"Status","callback_data":f"status|{mid}"},
        {"text":("Pause" if running else "Resume"),"callback_data":f"{'pause' if running else 'resume'}|{mid}"},
        {"text":"Stop","callback_data":f"stop|{mid}"},
    ]
    row2 = [
        {"text":"Snooze 2h","callback_data":f"snooze|{mid}|2h"},
        {"text":"Snooze 6h","callback_data":f"snooze|{mid}|6h"},
        {"text":"Restart driver","callback_data":f"restart|{mid}"},
    ]
    row3 = [
        {"text":"Discover theatres","callback_data":f"discover|{mid}"},
        {"text":"Start","callback_data":f"start|{mid}"},
        {"text":"Edit…","callback_data":f"edit|{mid}"},
    ]
    return {"inline_keyboard":[row1,row2,row3]}

# ---------- sqlite ----------
SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS monitors(
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  dates TEXT NOT NULL,
  theatres TEXT NOT NULL,
  interval_min INTEGER NOT NULL,
  baseline INTEGER NOT NULL,
  state TEXT NOT NULL,
  snooze_until INTEGER,
  owner_chat_id TEXT,
  created_at INTEGER,
  updated_at INTEGER,
  last_run_ts INTEGER,
  last_alert_ts INTEGER,
  heartbeat_minutes INTEGER DEFAULT 180,
  reload INTEGER DEFAULT 0,
  time_start TEXT,
  time_end TEXT
);
CREATE TABLE IF NOT EXISTS seen(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  time TEXT NOT NULL,
  first_seen_ts INTEGER,
  PRIMARY KEY(monitor_id, date, theatre, time)
);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  started_ts INTEGER,
  finished_ts INTEGER,
  status TEXT,
  error TEXT
);
CREATE TABLE IF NOT EXISTS snapshots(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  times_json TEXT NOT NULL,
  updated_at INTEGER,
  PRIMARY KEY(monitor_id,date,theatre)
);
CREATE TABLE IF NOT EXISTS theatres_index(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  last_seen_ts INTEGER,
  PRIMARY KEY(monitor_id,date,theatre)
);
"""

def db_connect(path: str) -> sqlite3.Connection:
    d = os.path.dirname(os.path.abspath(path))
    if d: os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for stmt in SCHEMA.strip().split(";\n"):
        s = stmt.strip()
        if s: conn.execute(s)
    conn.commit()
    # migrations
    try: conn.execute("ALTER TABLE monitors ADD COLUMN reload INTEGER DEFAULT 0"); conn.commit()
    except Exception: pass
    try: conn.execute("ALTER TABLE monitors ADD COLUMN time_start TEXT"); conn.commit()
    except Exception: pass
    try: conn.execute("ALTER TABLE monitors ADD COLUMN time_end TEXT"); conn.commit()
    except Exception: pass
    return conn

def db_now() -> int: return int(time.time())

def db_upsert_monitor(conn: sqlite3.Connection, mid: str, **fields):
    rows = conn.execute("SELECT id FROM monitors WHERE id=?", (mid,)).fetchall()
    if rows:
        sets = ", ".join([f"{k}=?" for k in fields.keys()])
        conn.execute(f"UPDATE monitors SET {sets}, updated_at=? WHERE id=?",
                     (*fields.values(), db_now(), mid))
    else:
        cols = ",".join(["id"] + list(fields.keys()) + ["created_at","updated_at"])
        qs = ",".join(["?"]*(len(fields)+3))
        conn.execute(f"INSERT INTO monitors({cols}) VALUES ({qs})",
                     (mid, *fields.values(), db_now(), db_now()))
    conn.commit()

def db_get_monitor(conn, mid: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM monitors WHERE id=?", (mid,)).fetchone()

def db_set_state(conn, mid: str, state: str):
    conn.execute("UPDATE monitors SET state=?, updated_at=? WHERE id=?", (state, db_now(), mid)); conn.commit()

def db_set_last_run(conn, mid: str):
    conn.execute("UPDATE monitors SET last_run_ts=?, updated_at=? WHERE id=?", (db_now(), db_now(), mid)); conn.commit()

def db_set_last_alert(conn, mid: str):
    conn.execute("UPDATE monitors SET last_alert_ts=?, updated_at=? WHERE id=?", (db_now(), db_now(), mid)); conn.commit()

def db_add_seen_if_new(conn, mid: str, date: str, theatre: str, tcanon: str) -> bool:
    before = conn.total_changes
    conn.execute("""INSERT OR IGNORE INTO seen(monitor_id,date,theatre,time,first_seen_ts)
                    VALUES(?,?,?,?,?)""", (mid, date, theatre, tcanon, db_now()))
    conn.commit()
    return conn.total_changes > before

def db_get_snapshot(conn, mid: str, date: str, theatre: str) -> List[str]:
    r = conn.execute("""SELECT times_json FROM snapshots
                        WHERE monitor_id=? AND date=? AND theatre=?""", (mid,date,theatre)).fetchone()
    if not r: return []
    try: return json.loads(r["times_json"]) or []
    except Exception: return []

def db_set_snapshot(conn, mid: str, date: str, theatre: str, times: List[str]):
    conn.execute("""INSERT INTO snapshots(monitor_id,date,theatre,times_json,updated_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(monitor_id,date,theatre) DO UPDATE SET
                    times_json=excluded.times_json, updated_at=excluded.updated_at
                 """, (mid, date, theatre, json.dumps(sorted(list(set(times)))), db_now()))
    conn.commit()

def db_add_theatre_index(conn, mid: str, date: str, theatre: str):
    conn.execute("""INSERT OR IGNORE INTO theatres_index(monitor_id,date,theatre,last_seen_ts)
                    VALUES(?,?,?,?)""", (mid,date,theatre,db_now()))
    conn.commit()

# ---------- graceful stop ----------
_STOP_NOW = False
def _sigterm(_sig, _frm):
    global _STOP_NOW
    _STOP_NOW = True
signal.signal(signal.SIGTERM, _sigterm)
signal.signal(signal.SIGINT, _sigterm)

def _interruptible_sleep(seconds: int, probe):
    for _ in range(max(1, seconds)):
        if _STOP_NOW or probe():
            return
        time.sleep(1)

# ---------- main ----------
def run(url: str, dates: List[str] | None, theatres_wanted: List[str] | None,
        monitor: bool, interval: int, debug: bool, trace: bool, artifacts_dir: Optional[str],
        dry_alerts: bool, exit_on_alert: bool, baseline: bool, days: Optional[int],
        state_db: Optional[str], monitor_id: Optional[str], heartbeat_minutes: int,
        start_alert: bool, owner_chat_id: Optional[str]):

    set_trace(trace, artifacts_dir)

    conn = db_connect(state_db) if state_db else None
    mid = monitor_id or ("m" + secrets.token_hex(3))

    d = get_driver(debug=debug)
    if not d:
        print("Failed to create a browser session.")
        return

    try:
        # resolve dates
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
                if not dates: dates = _roll_dates(1)
        dates = sorted(set(dates))
        if not theatres_wanted: theatres_wanted = ["any"]

        # persist monitor
        if conn:
            db_upsert_monitor(conn, mid,
                url=url,
                dates=",".join(dates),
                theatres=json.dumps(theatres_wanted, ensure_ascii=False),
                interval_min=interval,
                baseline=1 if baseline else 0,
                state="RUNNING",
                snooze_until=None,
                owner_chat_id=owner_chat_id or os.environ.get("TELEGRAM_CHAT_ID",""),
                heartbeat_minutes=heartbeat_minutes,
                reload=0
            )
            print(f"[monitor] id={mid}  interval={interval}m  dates={','.join(dates)}  theatres={len(theatres_wanted)}")

        # baseline seeding
        if baseline and conn:
            for date in dates:
                target = _ensure_date_in_url(url, date)
                d = open_and_prepare_resilient(d, target, debug=debug)
                for name, shows in parse_theatres(d):
                    if _fuzzy_match(name, theatres_wanted):
                        tset = sorted({_canon_time(s) for s in shows})
                        for t in tset: db_add_seen_if_new(conn, mid, date, name, t)
                        db_set_snapshot(conn, mid, date, name, tset)
                        db_add_theatre_index(conn, mid, date, name)
            tg_send(f"[{mid}] Baseline captured. Alert only on newly added showtimes.", dry=dry_alerts)

        start_ts = time.time()
        checks_done = 0
        alerts_total = 0
        last_alert_ts: Optional[float] = None
        last_heartbeat_ts = time.time()

        def maybe_heartbeat():
            nonlocal last_heartbeat_ts
            hb = heartbeat_minutes
            if conn:
                row = db_get_monitor(conn, mid)
                if row: hb = int(row["heartbeat_minutes"])
            if hb <= 0: return
            now = time.time()
            if now - last_heartbeat_ts >= hb * 60:
                eta = "—"
                row = db_get_monitor(conn, mid) if conn else None
                if row and row["last_run_ts"]:
                    left = int(row["last_run_ts"]) + int(row["interval_min"])*60 - int(now)
                    if left > 0: eta = f"{left//60}m {left%60}s"
                body = [
                    f"Heartbeat [{mid}] ✅",
                    f"Checks: {checks_done} | New shows: {alerts_total}",
                    f"Last alert: {fmt_dt(last_alert_ts)} | Next ~ {eta}"
                ]
                tg_send("\n".join(body), dry=dry_alerts, reply_markup=inline_controls(mid, running=True))
                last_heartbeat_ts = now

        if start_alert:
            tg_send(
              f"[{mid}] Monitor started ✅\nDates: {', '.join(dates)}\nTheatres: {len(theatres_wanted)}\nInterval: {interval} min",
              dry=dry_alerts, reply_markup=inline_controls(mid, running=True)
            )

        def control_probe() -> bool:
            if not conn: return False
            row = db_get_monitor(conn, mid)
            if not row: return True
            return row["state"] == "STOPPING"

        def state_row(): return db_get_monitor(conn, mid) if conn else None

        def apply_reload_if_requested():
            nonlocal d
            if not conn: return
            row = db_get_monitor(conn, mid)
            if row and int(row["reload"] or 0) == 1:
                try: d.quit()
                except Exception: pass
                d = get_driver(debug=debug)
                with conn:
                    conn.execute("UPDATE monitors SET reload=0, updated_at=? WHERE id=?", (int(time.time()), mid))
                tg_send(f"[{mid}] Driver restarted 🔄", dry=dry_alerts, reply_markup=inline_controls(mid, running=True))

        def time_in_window(tcanon: str, s: Optional[str], e: Optional[str]) -> bool:
            if not s or not e: return True
            mm = _to_minutes(tcanon)
            if mm is None: return True
            def hm(x): 
                hh,mi = x.split(":"); return int(hh)*60+int(mi)
            a,b = hm(s), hm(e)
            if a<=b: return a<=mm<=b
            # overnight wrap (rare for shows) — allow both sides
            return mm>=a or mm<=b

        # DISCOVER: populate theatres_index once then pause
        def discover_theatres():
            count = 0
            for date in dates:
                target = _ensure_date_in_url(url, date)
                d2 = open_and_prepare_resilient(d, target, debug=debug)
                names = set()
                for name, shows in parse_theatres(d2):
                    names.add(name)
                for n in sorted(names):
                    db_add_theatre_index(conn, mid, date, n)
                    count += 1
            tg_send(f"[{mid}] Discovery complete. Found {count} theatre entries across {len(dates)} dates.\nUse /addth {mid} <name> to filter, or Start.", dry=dry_alerts, reply_markup=inline_controls(mid, running=False))
            db_set_state(conn, mid, "PAUSED")

        # core: check newly added times vs snapshot; honor time window and snooze
        def check_once() -> List[Tuple[str,str,str]]:
            nonlocal d
            found: List[Tuple[str,str,str]] = []
            row = state_row()
            tstart = row["time_start"] if row else None
            tend   = row["time_end"] if row else None
            for date in dates:
                target = _ensure_date_in_url(url, date)
                d = open_and_prepare_resilient(d, target, debug=debug)
                for _ in range(2):
                    d.execute_script("window.scrollTo(0, document.body.scrollHeight);"); time.sleep(0.5)
                current_map: Dict[Tuple[str,str], List[str]] = {}
                for name, shows in parse_theatres(d):
                    if _fuzzy_match(name, theatres_wanted):
                        tset = sorted({_canon_time(s) for s in shows})
                        if tstart or tend:
                            tset = [t for t in tset if time_in_window(t, tstart, tend)]
                        current_map[(name,date)] = tset
                        db_add_theatre_index(conn, mid, date, name)
                if conn:
                    for (name,d8), tset in current_map.items():
                        prev = set(db_get_snapshot(conn, mid, d8, name))
                        added = [t for t in tset if t not in prev]
                        if added:
                            for t in added:
                                if db_add_seen_if_new(conn, mid, d8, name, t):
                                    found.append((name, d8, t))
                        db_set_snapshot(conn, mid, d8, name, tset)
                else:
                    for (name,d8), tset in current_map.items():
                        for t in tset: found.append((name,d8,t))
            return found

        def fmt_date(d8): return f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"
        def alert(lines):
            groups: Dict[Tuple[str,str], List[str]] = {}
            for n,d_,t in lines: groups.setdefault((n,d_), []).append(t)
            parts = []
            for (n,d_), ts in sorted(groups.items()):
                parts.append(f"{n} | {fmt_date(d_)} | {', '.join(sorted(set(ts)))}")
            body = "\n".join(parts)
            print("\nFound shows:\n" + body)
            tg_send(f"New shows on BMS [{mid}]:\n{body}", dry=dry_alerts, reply_markup=inline_controls(mid, running=True))

        # run once or loop
        if not monitor:
            apply_reload_if_requested()
            row = state_row()
            if row and row["state"] == "DISCOVER": discover_theatres(); return
            if control_probe(): return
            lines = check_once(); checks_done += 1
            if conn: db_set_last_run(conn, mid)
            if lines:
                su = int(row["snooze_until"]) if row and row["snooze_until"] else None
                if su and time.time() < su:
                    print(f"[{mid}] Snoozed; {len(lines)} new shows suppressed until {fmt_dt(su)}")
                else:
                    alert(lines)
                    alerts_total += len(lines)
                    last_alert_ts = time.time()
                    if conn: db_set_last_alert(conn, mid)
            else:
                print("No new shows right now.")
            return
        else:
            print(f"Monitoring every {interval} min. Ctrl+C to stop.")
            while True:
                row = state_row()
                if row:
                    if row["state"] == "STOPPING":
                        tg_send(f"[{mid}] Stopping now. Final: checks={checks_done}, new-shows={alerts_total}", dry=dry_alerts)
                        db_set_state(conn, mid, "STOPPED"); return
                    if row["state"] == "PAUSED":
                        _interruptible_sleep(max(60, interval*60), control_probe); maybe_heartbeat(); continue
                    if row["state"] == "DISCOVER":
                        discover_theatres(); continue
                apply_reload_if_requested()
                lines = check_once(); checks_done += 1
                if conn: db_set_last_run(conn, mid)
                if lines:
                    su = int(row["snooze_until"]) if row and row["snooze_until"] else None
                    if su and time.time() < su:
                        print(f"[{mid}] Snoozed; {len(lines)} new shows suppressed until {fmt_dt(su)}")
                    else:
                        alert(lines)
                        alerts_total += len(lines)
                        last_alert_ts = time.time()
                        if conn: db_set_last_alert(conn, mid)
                        if exit_on_alert:
                            tg_send(f"[{mid}] Exit on first alert: done.", dry=dry_alerts)
                            db_set_state(conn, mid, "STOPPED"); return
                else:
                    print("No new shows.")
                maybe_heartbeat()
                _interruptible_sleep(max(60, interval*60), control_probe)
    finally:
        try: d.quit()
        except Exception: pass

# ---------- CLI ----------
def parse_args(argv=None):
    import argparse
    p = argparse.ArgumentParser("bms-worker")
    p.add_argument("url")
    p.add_argument("--dates", help="Comma separated dates YYYY-MM-DD or YYYYMMDD")
    p.add_argument("--days", type=int)
    p.add_argument("--theatres", nargs="*", help="Use 'any' to monitor all")
    p.add_argument("--monitor", action="store_true")
    p.add_argument("--interval", type=int, default=3)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--artifacts-dir", default="./artifacts")
    p.add_argument("--dry-alerts", action="store_true")
    p.add_argument("--exit-on-alert", action="store_true")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--state-db", default="./artifacts/state.db")
    p.add_argument("--monitor-id")
    p.add_argument("--heartbeat-minutes", type=int, default=180)
    p.add_argument("--no-start-alert", action="store_true")
    p.add_argument("--owner-chat-id")
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
        a.exit_on_alert, a.baseline, a.days,
        a.state_db, a.monitor_id, a.heartbeat_minutes,
        start_alert=(not a.no_start_alert), owner_chat_id=a.owner_chat_id)

if __name__ == "__main__":
    main()
