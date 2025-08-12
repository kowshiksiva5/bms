#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, json
from typing import List, Dict
from datetime import datetime, timedelta
from config import SCHEDULER_SLEEP_SEC as _SLEEP

from bot.telegram_api import send_alert
from services.monitor_service import report_error

from store import (
    connect, get_active_monitors, set_state
)
from common import ensure_date_in_url, roll_dates, to_bms_date, within_time_window
from redis import Redis
from rq import Queue

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","")
FALLBACK_CHAT = os.environ.get("TELEGRAM_CHAT_ID","")

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
task_queue = Queue(connection=Redis.from_url(REDIS_URL))

# ---------- helpers ----------
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
    send_alert(row, chat, msg)
    heartbeat_book[mid] = now

# ---------- main loop ----------

def main_loop(debug=False, trace=False, artifacts_dir="./artifacts", sleep_sec=None):
    heartbeat_book: Dict[str, int] = {}

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
                        with connect() as conn:
                            conn.execute("UPDATE monitors SET reload=0, updated_at=? WHERE id=?", (now, r["id"]))
                            conn.commit()

                    if r["state"] == "STOPPING":
                        with connect() as conn:
                            set_state(conn, r["id"], "STOPPED")
                        send_alert(r, str(r["owner_chat_id"] or ""), f"⏹️ [{r['id']}] Stopped.")
                        continue

                    if not _should_run_now(r):
                        continue

                    last = int(r["last_run_ts"] or 0)
                    ivl = max(60, int(r["interval_min"] or 5) * 60)
                    if r["state"] == "DISCOVER" or now - last >= ivl:
                        with connect() as conn:
                            conn.execute(
                                "UPDATE monitors SET last_run_ts=?, updated_at=? WHERE id=?",
                                (now, now, r["id"]),
                            )
                            conn.commit()
                        if r["state"] == "DISCOVER":
                            task_queue.enqueue(
                                "tasks.monitor_tasks.run_discover",
                                r,
                                kwargs={"debug": debug, "trace": trace, "artifacts_dir": artifacts_dir},
                            )
                        else:
                            task_queue.enqueue(
                                "tasks.monitor_tasks.run_monitor",
                                r,
                                kwargs={"debug": debug, "trace": trace, "artifacts_dir": artifacts_dir},
                            )
                except Exception as e:
                    print("monitor error:", e)
                    report_error(r, e)
        except Exception as outer:
            print("scheduler loop error:", outer)
            time.sleep(3)
        time.sleep(int(sleep_sec or _SLEEP))

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
    main_loop(debug=a.debug, trace=a.trace, artifacts_dir=a.artifacts_dir, sleep_sec=a.sleep_sec)

if __name__ == "__main__":
    main()
