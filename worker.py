#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, json
from typing import List, Set, Optional
from datetime import datetime, timedelta
from config import DEFAULT_HEARTBEAT_MINUTES as _DEF_HB

from bot.telegram_api import send_text, send_alert
from services.monitor_service import format_new_shows, build_new_shows_keyboard
from bs4 import BeautifulSoup

from store import connect, get_monitor, set_state, set_reload, upsert_indexed_theatre
from common import ensure_date_in_url, fuzzy, roll_dates, to_bms_date, within_time_window
from scraper import set_trace as set_scr_trace, parse_theatres
from services.driver_manager import DriverManager
from services.monitor_service import report_error

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","")
FALLBACK_CHAT = os.environ.get("TELEGRAM_CHAT_ID","")

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

def run_one(monitor_id: Optional[str], url: Optional[str], dates: Optional[List[str]],
            theatres_wanted: Optional[List[str]], interval: int, monitor: bool,
            baseline: bool, debug: bool, trace: bool, artifacts_dir: str):
    set_scr_trace(trace, artifacts_dir)
    dm = DriverManager(debug=debug, trace=trace, artifacts_dir=artifacts_dir)
    d = dm.ensure()
    try:
        with connect() as conn:
            row=get_monitor(conn, monitor_id) if monitor_id else None
            if row:
                chat=str(row["owner_chat_id"] or "")
                send_alert(row, chat, f"▶️ Monitor [{row['id']}] started\nURL: {row['url']}\nMode: {row['mode'] or 'FIXED'} | Interval: {row['interval_min']}m")

        seen: Set[str]=set()
        last_heartbeat=_now_i()
        heartbeat=int((row and row["heartbeat_minutes"]) or _DEF_HB)

        if baseline:
            eff_dates = dates or (row and _effective_dates(row)) or []
            target_url = url or (row and row["url"])
            if target_url:
                for d8 in eff_dates:
                    t = ensure_date_in_url(target_url, d8)
                    d = dm.open(t)
                    for name, shows in parse_theatres(d):
                        if not theatres_wanted or fuzzy(name, theatres_wanted):
                            for st in shows: seen.add(f"{name}|{d8}|{st}")

        def one_pass():
            nonlocal d
            with connect() as conn:
                r = get_monitor(conn, monitor_id) if monitor_id else None
            target_url = (r and r["url"]) or url
            eff_dates = (r and _effective_dates(r)) or dates or []
            if not eff_dates or not target_url:
                time.sleep(3); return False
            found=[]
            for d8 in eff_dates:
                turl=ensure_date_in_url(target_url, d8)
                d = dm.open(turl)
                try:
                    for _ in range(2): d.execute_script("window.scrollTo(0, document.body.scrollHeight);"); time.sleep(0.5)
                except Exception: pass
                pairs = parse_theatres(d)
                if monitor_id:
                    with connect() as conn:
                        for nm,_ in pairs: upsert_indexed_theatre(conn, monitor_id, d8, nm)
                twanted = (r and json.loads(r["theatres"])) if (r and r["theatres"]) else (theatres_wanted or [])
                for nm, shows in pairs:
                    if not twanted or fuzzy(nm, twanted):
                        for st in shows:
                            key=f"{nm}|{d8}|{st}"
                            if key not in seen:
                                found.append((nm,d8,st))
            if found:
                with connect() as conn:
                    if monitor_id:
                        conn.execute("UPDATE monitors SET last_alert_ts=?, updated_at=? WHERE id=?", (_now_i(), _now_i(), monitor_id)); conn.commit()
                chat=str((r and r["owner_chat_id"]) or os.environ.get("TELEGRAM_CHAT_ID",""))
                msg = format_new_shows(r or {}, found)
                kb = build_new_shows_keyboard(r or {}, found)
                send_text(chat, msg, reply_markup=kb or None)
                for n,d8,t in found: seen.add(f"{n}|{d8}|{t}")
                return True
            return False

        if not monitor:
            one_pass(); return

        while True:
            try:
                with connect() as conn:
                    r = get_monitor(conn, monitor_id) if monitor_id else None
                    if r:
                        conn.execute("UPDATE monitors SET last_run_ts=?, updated_at=? WHERE id=?", (_now_i(),_now_i(),monitor_id)); conn.commit()
                        if int(r["reload"] or 0)==1:
                            conn.execute("UPDATE monitors SET reload=0 WHERE id=?", (monitor_id,)); conn.commit()
                            dm.reset()
                            d = dm.ensure()
                            if not d:
                                send_alert(r, str(r["owner_chat_id"] or ""), f"❌ [{monitor_id}] could not restart driver.")
                                return
                            send_alert(r, str(r["owner_chat_id"] or ""), f"🔄 [{monitor_id}] driver restarted.")
                        if r["state"]=="STOPPING":
                            set_state(conn, monitor_id, "STOPPED"); send_alert(r, str(r["owner_chat_id"] or ""), f"⏹️ [{monitor_id}] stopped."); return

                if r and not _should_run_now(r):
                    time.sleep(10); continue

                alerted = one_pass()

                if r and (r["mode"] or "FIXED")=="UNTIL":
                    eff=_effective_dates(r)
                    if not eff:
                        with connect() as conn:
                            set_state(conn, monitor_id, "PAUSED")
                        send_alert(r, str(r["owner_chat_id"] or ""), f"⏸️ [{monitor_id}] end date reached; auto-paused.")
                        return

                if _now_i()-last_heartbeat > (heartbeat*60):
                    with connect() as conn: rr=get_monitor(conn, monitor_id) if monitor_id else None
                    eta = (int(rr["last_run_ts"]) + int(rr["interval_min"])*60 - _now_i()) if rr and rr["last_run_ts"] else 0
                    eta = max(0,eta)
                    msg = f"💓 Heartbeat [{monitor_id or 'ad-hoc'}]\nState: {(rr and rr['state']) or 'RUNNING'}\nInterval: {(rr and rr['interval_min']) or interval}m\nNext in ~ {eta//60}m {eta%60}s"
                    send_alert(rr or (row or {}), str((rr and rr["owner_chat_id"]) or os.environ.get("TELEGRAM_CHAT_ID","")), msg)
                    last_heartbeat=_now_i()

                time.sleep(max(60, int((r and r["interval_min"]) or interval)*60))
            except Exception as e:
                # Report and keep going
                try:
                    report_error(r or (row or {}), e)
                except Exception:
                    pass
                time.sleep(5)
    finally:
        try: d.quit()
        except Exception: pass

def _parse_args(argv=None):
    import argparse
    p=argparse.ArgumentParser("bms-worker")
    p.add_argument("--monitor-id", help="Monitor id from DB. If set, URL/dates/theatres can be omitted.")
    p.add_argument("url", nargs="?", help="Buytickets URL (if no monitor-id).")
    p.add_argument("--dates", help="CSV of YYYY-MM-DD or YYYYMMDD (if no monitor-id)")
    p.add_argument("--theatres", nargs="*", help="Theatres (use 'any' for all) (if no monitor-id)")
    p.add_argument("--interval", type=int, default=5)
    p.add_argument("--monitor", action="store_true")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--artifacts-dir", default="./artifacts")
    return p.parse_args(argv)

def main(argv=None):
    a=_parse_args(argv)
    dates=None
    if a.dates:
        parts=[x.strip() for x in re.split(r"[,\s]+", a.dates) if x.strip()]
        from common import to_bms_date
        dates=[to_bms_date(x) or x for x in parts]
    run_one(a.monitor_id, a.url, dates, a.theatres, a.interval, a.monitor, a.baseline, a.debug, a.trace, a.artifacts_dir)

if __name__=="__main__":
    main()
