#!/usr/bin/env python3
from __future__ import annotations
from typing import Dict, List, Tuple
import os, re, time, traceback

from utils import titled
import asyncio
import bot.telegram_api as tg
from store import connect, upsert_indexed_theatre, bulk_upsert_seen, is_seen, set_baseline_done, set_state
from common import ensure_date_in_url

def _fmt_date(d8: str)->str: return f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"

def _deeplink(row: dict, d8: str) -> str:
    m = re.search(r"(ET\d{5,})", row.get("url") or "")
    if m:
        et = m.group(1)
        return f"https://in.bookmyshow.com/buytickets/{et}/{d8}"
    return ensure_date_in_url(row.get("url",""), d8)

def format_new_shows(row: dict, found: List[Tuple[str,str,str]]) -> str:
    # bucket by date, then theatre → times
    by_date: Dict[str, Dict[str, List[str]]] = {}
    total_times = 0
    for nm, d8, t in found:
        by_date.setdefault(d8, {}).setdefault(nm, []).append(t)
        total_times += 1
    lines: List[str] = []
    for d8 in sorted(by_date.keys()):
        lines.append(f"🗓 {_fmt_date(d8)}")
        for nm in sorted(by_date[d8].keys()):
            times = ", ".join(sorted(set(by_date[d8][nm])))
            lines.append(f"  • 🏟 {nm}: {times}")
        lines.append("")
    first_d8 = sorted(by_date.keys())[0]
    link = _deeplink(row, first_d8)
    header = [
        "🎟️ New shows",
        f"🔎 Monitor: {row['id']} • every {row.get('interval_min','?')}m",
        f"🔗 {link}",
        "",
    ]
    summary = f"Totals: {total_times} time(s) • {sum(len(v) for v in by_date.values())} theatre entries • {len(by_date)} date(s)"
    body = "\n".join(header + lines).rstrip() + ("\n" + summary)
    return titled(row, body)

def build_new_shows_keyboard(row: dict, found: List[Tuple[str,str,str]]) -> Dict:
    if not found:
        return {}
    first_d8 = sorted({d8 for _, d8, _ in found})[0]
    link = _deeplink(row, first_d8)
    mid = row.get('id','')
    state = (row.get('state') or '').upper()
    running = state == 'RUNNING'
    kb = {
        "inline_keyboard": [
            [{"text":"Open Buy Page","url": link}],
            [
                {"text":"Status","callback_data": f"status|{mid}"},
                {"text":"Snooze 2h","callback_data": f"snooze|{mid}|2h"}
            ],
            [
                {"text": ("Pause" if running else "Resume"), "callback_data": f"{'pause' if running else 'resume'}|{mid}"},
                {"text":"Edit Theatres","callback_data": f"edit_theatres|{mid}"}
            ]
        ]
    }
    return kb

def report_error(row: dict, err: Exception):
    chat = str(row.get('owner_chat_id') or '')
    try:
        asyncio.run(tg.send_alert(row, chat, f"⚠️ Error on [{row['id']}]: {err}"))
    except Exception:
        pass
    try:
        art = os.environ.get("ART_DIR", "./artifacts")
        os.makedirs(art, exist_ok=True)
        with open(os.path.join(art, f"error_{int(time.time())}_{row['id']}.log"), "w", encoding="utf-8") as f:
            f.write(f"Monitor {row['id']} error\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


