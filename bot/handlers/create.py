from __future__ import annotations
import json
import secrets
import time
from typing import Set

from store import (
    connect,
    get_ui_session,
    set_ui_session,
    clear_ui_session,
)
from ..keyboards import (
    kb_date_picker,
    kb_theatre_picker,
    kb_interval_picker,
    kb_duration_picker,
    kb_heartbeat_picker,
)
from ..telegram_api import send_text
from ..utils import DEFAULT_THEATRES, discover_theatre_names
from utils import titled


# ---- Creation flow handlers ----

def cmd_new(chat_id: str, url: str):
    url = url.strip()
    if not url:
        send_text(chat_id, "Usage: /new <buytickets URL>")
        return
    sid = "new-" + secrets.token_hex(3)
    sess = {
        "mode": "create",
        "url": url,
        "dates": [],
        "theatres": [],
        "interval": 5,
        "page_dates": 0,
        "page_theatres": 0,
        "dur_mode": "FIXED",
        "dur_rolling": 7,
        "dur_until": None,
        "heartbeat": 180,
    }
    with connect() as conn:
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(url, "Step 1/5 — Select dates for new monitor (toggle then Save):"),
        reply_markup=kb_date_picker(sid, set(), 0, total_days=28, prefix="c"),
    )


def _build_theatre_keyboard_for_create(sid: str, selected: Set[str], page: int):
    kb = kb_theatre_picker(sid, DEFAULT_THEATRES, selected, page=page, page_size=8, prefix="ct")
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    return kb


# dates

def cb_cpick(chat_id: str, sid: str, d8: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = set(sess.get("dates", []))
        if d8 in sel:
            sel.remove(d8)
        else:
            sel.add(d8)
        sess["dates"] = sorted(list(sel))
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess["url"], f"Step 1/5 — {len(sel)} date(s) selected. Save to continue."),
        reply_markup=kb_date_picker(sid, sel, sess.get("page_dates", 0), total_days=28, prefix="c"),
    )


def cb_cpg(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["page_dates"] = max(0, int(page))
        set_ui_session(conn, chat_id, sid, sess)
        sel = set(sess.get("dates", []))
    send_text(
        chat_id,
        titled(sess["url"], "Page changed."),
        reply_markup=kb_date_picker(sid, sel, sess["page_dates"], total_days=28, prefix="c"),
    )


def cb_csave(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = sorted(set(sess.get("dates", [])))
        if not sel:
            send_text(chat_id, "Pick at least 1 date.")
            return
        sess["page_theatres"] = 0
        # try to discover available theatres for the first picked date
        names = discover_theatre_names(sess["url"], sel[0])
        if names:
            sess["items"] = names
        set_ui_session(conn, chat_id, sid, sess)
    items = sess.get("items") or DEFAULT_THEATRES
    kb = kb_theatre_picker(
        sid, items, set(sess.get("theatres", [])), page=0, page_size=8, prefix="ct"
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    send_text(
        chat_id,
        titled(sess["url"], "Step 2/6 — Select theatres (toggle then Save):"),
        reply_markup=kb,
    )


def cb_ccancel(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        url = (sess or {}).get("url", "")
        clear_ui_session(conn, chat_id, sid)
    text = "Creation canceled."
    send_text(chat_id, titled(url, text) if url else text)


# theatres

def cb_ctpick(chat_id: str, sid: str, idx: int):
    idx = int(idx)
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        items = sess.get("items") or DEFAULT_THEATRES
        if idx < 0 or idx >= len(items):
            return
        name = items[idx]
        sel = set(sess.get("theatres", []))
        if name in sel:
            sel.remove(name)
        else:
            sel.add(name)
        sel.discard("any")
        sess["theatres"] = sorted(list(sel))
        set_ui_session(conn, chat_id, sid, sess)
        page = int(sess.get("page_theatres", 0))
    items = sess.get("items") or DEFAULT_THEATRES
    kb = kb_theatre_picker(sid, items, sel, page=page, page_size=8, prefix="ct")
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    send_text(
        chat_id,
        titled(sess["url"], f"Step 2/6 — {len(sel)} theatre(s) selected."),
        reply_markup=kb,
    )


def cb_ctpg(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["page_theatres"] = max(0, int(page))
        set_ui_session(conn, chat_id, sid, sess)
        sel = set(sess.get("theatres", []))
        items = sess.get("items") or DEFAULT_THEATRES
    kb = kb_theatre_picker(
        sid, items, sel, page=sess["page_theatres"], page_size=8, prefix="ct"
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    send_text(chat_id, titled(sess["url"], "Page changed."), reply_markup=kb)


def cb_cany(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["theatres"] = ["any"]
        set_ui_session(conn, chat_id, sid, sess)
    items = sess.get("items") or DEFAULT_THEATRES
    kb = kb_theatre_picker(
        sid,
        items,
        set(sess["theatres"]),
        page=int(sess.get("page_theatres", 0)),
        page_size=8,
        prefix="ct",
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    send_text(
        chat_id,
        titled(sess["url"], "Step 2/6 — Selected: any (all theatres)."),
        reply_markup=kb,
    )


def cb_call(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["theatres"] = list(DEFAULT_THEATRES)
        set_ui_session(conn, chat_id, sid, sess)
    items = sess.get("items") or DEFAULT_THEATRES
    kb = kb_theatre_picker(
        sid,
        items,
        set(sess["theatres"]),
        page=int(sess.get("page_theatres", 0)),
        page_size=8,
        prefix="ct",
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    send_text(
        chat_id,
        titled(sess["url"], "Step 2/6 — All defaults selected."),
        reply_markup=kb,
    )


def cb_cclear(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["theatres"] = []
        set_ui_session(conn, chat_id, sid, sess)
    items = sess.get("items") or DEFAULT_THEATRES
    kb = kb_theatre_picker(
        sid,
        items,
        set(),
        page=int(sess.get("page_theatres", 0)),
        page_size=8,
        prefix="ct",
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    send_text(
        chat_id,
        titled(sess["url"], "Step 2/6 — Cleared selection."),
        reply_markup=kb,
    )


def cb_ctsave(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = sess.get("theatres", [])
        if not sel:
            send_text(chat_id, "Pick at least 1 theatre, or choose 'Use Any'.")
            return
        cur = int(sess.get("interval", 5))
    send_text(
        chat_id,
        titled(sess["url"], "Step 3/5 — Select interval (minutes):"),
        reply_markup=kb_interval_picker(sid, cur),
    )


def cb_ctcancel(chat_id: str, sid: str):
    cb_ccancel(chat_id, sid)


# interval → duration

def cb_ivalset(chat_id: str, sid: str, minutes: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["interval"] = int(minutes)
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess["url"], f"Step 3/5 — Interval set to {minutes}m."),
        reply_markup=kb_interval_picker(sid, int(minutes)),
    )


def cb_ivalback(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = set(sess.get("theatres", []))
        items = sess.get("items") or DEFAULT_THEATRES
    kb = kb_theatre_picker(
        sid, items, sel, page=int(sess.get("page_theatres", 0)), page_size=8, prefix="ct"
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"cany|{sid}"},
            {"text": "All defaults", "callback_data": f"call|{sid}"},
            {"text": "Clear", "callback_data": f"cclear|{sid}"},
        ],
    )
    send_text(chat_id, titled(sess["url"], "Step 2/6 — Select theatres:"), reply_markup=kb)


def cb_idurnext(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
    send_text(
        chat_id,
        titled(sess["url"], "Step 4/6 — Duration mode:"),
        reply_markup=kb_duration_picker(
            sid,
            sess.get("dur_mode", "FIXED"),
            int(sess.get("dur_rolling", 7)),
            sess.get("dur_until"),
        ),
    )


def cb_idurback(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
    send_text(
        chat_id,
        titled(sess["url"], "Step 3/6 — Select interval (minutes):"),
        reply_markup=kb_interval_picker(sid, int(sess.get("interval", 5))),
    )


def cb_dur(chat_id: str, sid: str, mode: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["dur_mode"] = mode
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess["url"], "Step 4/6 — Duration mode:"),
        reply_markup=kb_duration_picker(
            sid, mode, int(sess.get("dur_rolling", 7)), sess.get("dur_until")
        ),
    )


def cb_rplus(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        r = int(sess.get("dur_rolling", 7))
        r = min(30, r + 1)
        sess["dur_rolling"] = r
        sess["dur_mode"] = "ROLLING"
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess["url"], "Step 4/6 — Duration mode:"),
        reply_markup=kb_duration_picker(sid, "ROLLING", r, sess.get("dur_until")),
    )


def cb_rminus(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        r = int(sess.get("dur_rolling", 7))
        r = max(1, r - 1)
        sess["dur_rolling"] = r
        sess["dur_mode"] = "ROLLING"
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess["url"], "Step 4/6 — Duration mode:"),
        reply_markup=kb_duration_picker(sid, "ROLLING", r, sess.get("dur_until")),
    )


# UNTIL date picker

def cb_uopen(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        cur = {sess["dur_until"]} if sess.get("dur_until") else set()
    send_text(
        chat_id,
        titled(sess["url"], "Pick an end date (Save sets mode=UNTIL):"),
        reply_markup=kb_date_picker(sid, cur, int(page), total_days=60, prefix="u"),
    )


def cb_upick(chat_id: str, sid: str, d8: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["dur_until"] = d8 if sess.get("dur_until") != d8 else None
        set_ui_session(conn, chat_id, sid, sess)
    cur = {sess["dur_until"]} if sess.get("dur_until") else set()
    send_text(
        chat_id,
        titled(sess["url"], "Pick an end date (Save sets mode=UNTIL):"),
        reply_markup=kb_date_picker(
            sid, cur, int(sess.get("page_until", 0)), total_days=60, prefix="u"
        ),
    )


def cb_upg(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["page_until"] = int(page)
        set_ui_session(conn, chat_id, sid, sess)
    cur = {sess["dur_until"]} if sess.get("dur_until") else set()
    send_text(
        chat_id,
        titled(sess["url"], "Pick an end date (Save sets mode=UNTIL):"),
        reply_markup=kb_date_picker(sid, cur, int(page), total_days=60, prefix="u"),
    )


def cb_usave(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess.get("dur_until"):
            send_text(chat_id, "Please pick an end date.")
            return
        sess["dur_mode"] = "UNTIL"
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess["url"], "Step 4/6 — Duration mode:"),
        reply_markup=kb_duration_picker(
            sid, "UNTIL", int(sess.get("dur_rolling", 7)), sess.get("dur_until")
        ),
    )


def cb_ucancel(chat_id: str, sid: str):
    cb_idurnext(chat_id, sid)


# Heartbeat step

def cb_idur2hb(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
    hb = int(sess.get("heartbeat", 180)) if sess else 180
    send_text(
        chat_id,
        titled(sess["url"], "Step 5/6 — Heartbeat interval (minutes):"),
        reply_markup=kb_heartbeat_picker(sid, hb),
    )


def cb_hbset(chat_id: str, sid: str, minutes: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["heartbeat"] = int(minutes)
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess["url"], f"Step 5/6 — Heartbeat set to {minutes}m."),
        reply_markup=kb_heartbeat_picker(sid, int(minutes)),
    )


def cb_hbback(chat_id: str, sid: str):
    cb_idurnext(chat_id, sid)


def cb_cfinish(chat_id: str, sid: str, mode: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Please /new again.")
            return
        url = sess.get("url", "").strip()
        dates = sess.get("dates", [])
        ths = sess.get("theatres", [])
        interval = int(sess.get("interval", 5))
        dur_mode = (sess.get("dur_mode") or "FIXED").upper()
        dur_rolling = int(sess.get("dur_rolling") or 7)
        dur_until = sess.get("dur_until")
        if not url or not dates or not ths:
            send_text(chat_id, "Missing info. Make sure you selected dates, theatres and interval.")
            return
        mid = "m" + secrets.token_hex(3)
        state = "RUNNING" if mode == "start" else "PAUSED"
        now = int(time.time())
        hb = int(sess.get("heartbeat", 180))
        conn.execute(
            """INSERT INTO monitors
            (id,url,dates,theatres,interval_min,baseline,state,owner_chat_id,created_at,updated_at,heartbeat_minutes,reload,mode,rolling_days,end_date)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                mid,
                url,
                ",".join(sorted(set(dates))),
                json.dumps(["any"] if "any" in ths else ths, ensure_ascii=False),
                interval,
                1,
                state,
                chat_id,
                now,
                now,
                hb,
                0,
                dur_mode,
                (dur_rolling if dur_mode == "ROLLING" else 0),
                (dur_until if dur_mode == "UNTIL" else None),
            ),
        )
        conn.commit()
        clear_ui_session(conn, chat_id, sid)

    cmd = f"python worker.py --monitor-id {mid} --monitor --trace --artifacts-dir ./artifacts"
    msg = [
        f"✅ Created [{mid}] ({state})",
        f"URL: {url}",
        f"Dates: {','.join(sorted(set(dates)))}",
        f"Theatres: {'any' if 'any' in ths else str(len(ths)) + ' selected'}",
        f"Interval: {interval}m",
        f"Heartbeat: {hb}m",
        f"Mode: {dur_mode}{' '+str(dur_rolling)+'d' if dur_mode=='ROLLING' else (' until '+dur_until if dur_mode=='UNTIL' else '')}",
        "",
        "To start the worker (if not already running):",
        cmd,
    ]
    send_text(chat_id, titled(url, "\n".join(msg)))

def register(dp):
    dp.command("/new", lambda chat_id, args: cmd_new(chat_id, " ".join(args)))
    dp.callback("cpick", cb_cpick)
    dp.callback("cpg", lambda chat_id, sid, opt: cb_cpg(chat_id, sid, int(opt or "0")))
    dp.callback("csave", cb_csave)
    dp.callback("ccancel", cb_ccancel)
    dp.callback("ctpick", lambda chat_id, sid, opt: cb_ctpick(chat_id, sid, int(opt)))
    dp.callback("ctpg", lambda chat_id, sid, opt: cb_ctpg(chat_id, sid, int(opt or "0")))
    dp.callback("ctsave", cb_ctsave)
    dp.callback("ctcancel", cb_ctcancel)
    dp.callback("cany", cb_cany)
    dp.callback("call", cb_call)
    dp.callback("cclear", cb_cclear)
    dp.callback("ivalset", lambda chat_id, sid, opt: cb_ivalset(chat_id, sid, int(opt or "5")))
    dp.callback("ivalback", cb_ivalback)
    dp.callback("idurnext", cb_idurnext)
    dp.callback("idurback", cb_idurback)
    dp.callback("dur", cb_dur)
    dp.callback("rplus", cb_rplus)
    dp.callback("rminus", cb_rminus)
    dp.callback("uopen", lambda chat_id, sid, opt: cb_uopen(chat_id, sid, int(opt or "0")))
    dp.callback("upick", cb_upick)
    dp.callback("upg", lambda chat_id, sid, opt: cb_upg(chat_id, sid, int(opt or "0")))
    dp.callback("usave", cb_usave)
    dp.callback("ucancel", cb_ucancel)
    dp.callback("idur2hb", cb_idur2hb)
    dp.callback("hbset", lambda chat_id, sid, opt: cb_hbset(chat_id, sid, int(opt or "180")))
    dp.callback("hbback", cb_hbback)
    dp.callback("cfinish", cb_cfinish)
