#!/usr/bin/env python3
from __future__ import annotations

import re, time, json
from typing import List, Tuple, Dict
from datetime import datetime, timedelta

from bot.telegram_api import send_text, send_alert
from services.monitor_service import report_error, format_new_shows, build_new_shows_keyboard
from store import (
    connect, upsert_indexed_theatre, bulk_upsert_seen, is_seen, set_baseline_done, set_state
)
from common import ensure_date_in_url, fuzzy, roll_dates, to_bms_date
from services.driver_manager import DriverManager
from scraper import parse_theatres


def _now_i() -> int:
    return int(time.time())


def _effective_dates(row) -> List[str]:
    mode = (row.get("mode") or "FIXED").upper()
    if mode == "ROLLING":
        days = max(1, int(row.get("rolling_days") or 1))
        return roll_dates(days)
    if mode == "UNTIL":
        end = to_bms_date(row.get("end_date") or "")
        if not end:
            return [x for x in (row.get("dates") or "").split(",") if x]
        today = int(datetime.now().strftime("%Y%m%d"))
        endi = int(end)
        if today > endi:
            return []
        span = []
        cur = datetime.now()
        while int(cur.strftime("%Y%m%d")) <= endi:
            span.append(cur.strftime("%Y%m%d"))
            cur = cur + timedelta(days=1)
        return span
    return [x for x in (row.get("dates") or "").split(",") if x]


def _deeplink(row: dict, d8: str) -> str:
    m = re.search(r"(ET\d{5,})", row.get("url") or "")
    if m:
        et = m.group(1)
        return f"https://in.bookmyshow.com/buytickets/{et}/{d8}"
    return ensure_date_in_url(row.get("url"), d8)


def run_discover(row: Dict, debug: bool = False, trace: bool = False, artifacts_dir: str = "./artifacts"):
    dm = DriverManager(debug=debug, trace=trace, artifacts_dir=artifacts_dir)
    try:
        eff = _effective_dates(row) or roll_dates(1)
        date = eff[0]
        url = ensure_date_in_url(row["url"], date)
        d = dm.open(url)
        pairs = parse_theatres(d)
        names = sorted({n for n, _ in pairs})
        with connect() as conn:
            for nm in names:
                upsert_indexed_theatre(conn, row["id"], date, nm)
            set_state(conn, row["id"], "PAUSED")
        chat = str(row.get("owner_chat_id") or "")
        send_alert(
            row,
            chat,
            (
                f"🧭 Discover complete for [{row['id']}]\n"
                f"Captured {len(names)} theatres for {date[:4]}-{date[4:6]}-{date[6:]}\n"
                f"State set to PAUSED.\n"
                f"🔗 {_deeplink(row, date)}"
            ),
        )
    finally:
        dm.reset()


def run_monitor(row: Dict, debug: bool = False, trace: bool = False, artifacts_dir: str = "./artifacts"):
    dm = DriverManager(debug=debug, trace=trace, artifacts_dir=artifacts_dir)
    mid = row["id"]
    chat = str(row.get("owner_chat_id") or "")
    try:
        eff_dates = _effective_dates(row)
        if not eff_dates:
            if (row.get("mode") or "FIXED").upper() == "UNTIL":
                with connect() as conn:
                    set_state(conn, mid, "PAUSED")
                send_alert(row, chat, f"⏸️ [{mid}] End date reached; auto-paused.")
            return

        if int(row.get("baseline") or 0) == 1:
            try:
                for d8 in eff_dates:
                    turl = ensure_date_in_url(row["url"], d8)
                    d = dm.open(turl)
                    for name, shows in parse_theatres(d):
                        twanted = json.loads(row["theatres"]) if row.get("theatres") else []
                        if not twanted or fuzzy(name, twanted):
                            with connect() as conn:
                                bulk_upsert_seen(conn, [(mid, d8, name, st, _now_i()) for st in shows])
                with connect() as conn:
                    set_baseline_done(conn, mid)
                send_alert(
                    row,
                    chat,
                    f"📏 Baseline captured for [{mid}] — alerts will fire only on newly added showtimes.",
                )
            except Exception as e:
                send_alert(row, chat, f"⚠️ Baseline failed for [{mid}]: {e}")

        found: List[Tuple[str, str, str]] = []
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
                for nm, _ in pairs:
                    upsert_indexed_theatre(conn, mid, d8, nm)
            twanted = json.loads(row["theatres"]) if row.get("theatres") else []
            for nm, shows in pairs:
                if not twanted or fuzzy(nm, twanted):
                    for st in shows:
                        with connect() as conn:
                            if not is_seen(conn, mid, d8, nm, st):
                                found.append((nm, d8, st))

        if found:
            msg = format_new_shows(row, found)
            kb = build_new_shows_keyboard(row, found)
            send_text(chat, msg, reply_markup=kb or None)
            with connect() as conn:
                bulk_upsert_seen(conn, [(mid, d, n, t, _now_i()) for n, d, t in found])
                conn.execute(
                    "UPDATE monitors SET last_alert_ts=?, updated_at=? WHERE id=?",
                    (_now_i(), _now_i(), mid),
                )
                conn.commit()
    except Exception as e:
        report_error(row, e)
    finally:
        dm.reset()


