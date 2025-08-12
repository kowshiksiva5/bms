from __future__ import annotations
import json

from store import (
    connect,
    get_monitor,
    get_indexed_theatres,
    set_ui_session,
    get_ui_session,
    clear_ui_session,
    set_dates,
    set_theatres,
)
from ..keyboards import kb_date_picker, kb_theatre_picker
from ..telegram_api import send_text
from ..utils import DEFAULT_THEATRES
from utils import titled


# ---- Edit flows ----

def cmd_edit_dates(chat_id: str, mid: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        if not r:
            send_text(chat_id, f"Monitor {mid} not found.")
            return
        cur = {x for x in (r["dates"] or "").split(",") if x}
        sess = {
            "mode": "edit_dates",
            "url": r["url"],
            "dates": sorted(list(cur)),
            "page_dates": 0,
        }
        set_ui_session(conn, chat_id, f"editd-{mid}", sess)
    send_text(
        chat_id,
        titled(r, "Edit dates (toggle then Save):"),
        reply_markup=kb_date_picker(mid, cur, 0, total_days=60, prefix="e"),
    )


def cb_epick(chat_id: str, mid: str, d8: str):
    sid = f"editd-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        sel = set(sess.get("dates", []))
        if d8 in sel:
            sel.remove(d8)
        else:
            sel.add(d8)
        sess["dates"] = sorted(list(sel))
        set_ui_session(conn, chat_id, sid, sess)
    send_text(
        chat_id,
        titled(sess.get("url", ""), f"{len(sel)} date(s) selected."),
        reply_markup=kb_date_picker(
            mid, sel, int(sess.get("page_dates", 0)), total_days=60, prefix="e"
        ),
    )


def cb_epg(chat_id: str, mid: str, page: int):
    sid = f"editd-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        sess["page_dates"] = max(0, int(page))
        set_ui_session(conn, chat_id, sid, sess)
        sel = set(sess.get("dates", []))
    send_text(
        chat_id,
        titled(sess.get("url", ""), "Page changed."),
        reply_markup=kb_date_picker(
            mid, sel, int(sess.get("page_dates", 0)), total_days=60, prefix="e"
        ),
    )


def cb_esave(chat_id: str, mid: str):
    sid = f"editd-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        dates = sorted(set(sess.get("dates", [])))
        if not dates:
            send_text(chat_id, "Please select at least one date.")
            return
        r = get_monitor(conn, mid)
        set_dates(conn, mid, ",".join(dates))
        clear_ui_session(conn, chat_id, sid)
    send_text(chat_id, titled(r or mid, f"[{mid}] Dates updated."))


def cb_ecancel(chat_id: str, mid: str):
    sid = f"editd-{mid}"
    with connect() as conn:
        clear_ui_session(conn, chat_id, sid)
    send_text(chat_id, f"[{mid}] Edit canceled.")


# ----- Edit: Theatres -----

def cmd_edit_theatres(chat_id: str, mid: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        if not r:
            send_text(chat_id, f"Monitor {mid} not found.")
            return
        current = []
        try:
            current = json.loads(r["theatres"]) if r.get("theatres") else []
        except Exception:
            current = []
        items = get_indexed_theatres(conn, mid) or list(DEFAULT_THEATRES)
        sess = {
            "mode": "edit_theatres",
            "url": r["url"],
            "theatres": current,
            "items": items,
            "page_theatres": 0,
        }
        set_ui_session(conn, chat_id, f"editt-{mid}", sess)
    kb = kb_theatre_picker(mid, items, set(current), page=0, page_size=8, prefix="et")
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"eany|{mid}"},
            {"text": "Clear", "callback_data": f"eclear|{mid}"},
        ],
    )
    send_text(chat_id, titled(r, "Edit theatres (toggle then Save):"), reply_markup=kb)


def cb_etpick(chat_id: str, mid: str, idx: int):
    sid = f"editt-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        items = sess.get("items") or list(DEFAULT_THEATRES)
        i = int(idx)
        if i < 0 or i >= len(items):
            return
        name = items[i]
        sel = set(sess.get("theatres", []))
        if name in sel:
            sel.remove(name)
        else:
            sel.add(name)
        sel.discard("any")
        sess["theatres"] = sorted(list(sel))
        set_ui_session(conn, chat_id, sid, sess)
        page = int(sess.get("page_theatres", 0))
    kb = kb_theatre_picker(
        mid, items, set(sess.get("theatres", [])), page=page, page_size=8, prefix="et"
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"eany|{mid}"},
            {"text": "Clear", "callback_data": f"eclear|{mid}"},
        ],
    )
    send_text(
        chat_id,
        titled(sess.get("url", ""), f"{len(sel)} theatre(s) selected."),
        reply_markup=kb,
    )


def cb_etpg(chat_id: str, mid: str, page: int):
    sid = f"editt-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        sess["page_theatres"] = max(0, int(page))
        set_ui_session(conn, chat_id, sid, sess)
        items = sess.get("items") or list(DEFAULT_THEATRES)
        sel = set(sess.get("theatres", []))
        pg = int(sess.get("page_theatres", 0))
    kb = kb_theatre_picker(mid, items, sel, page=pg, page_size=8, prefix="et")
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"eany|{mid}"},
            {"text": "Clear", "callback_data": f"eclear|{mid}"},
        ],
    )
    send_text(chat_id, titled(sess.get("url", ""), "Page changed."), reply_markup=kb)


def cb_eany(chat_id: str, mid: str):
    sid = f"editt-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        sess["theatres"] = ["any"]
        set_ui_session(conn, chat_id, sid, sess)
        items = sess.get("items") or list(DEFAULT_THEATRES)
    kb = kb_theatre_picker(
        mid,
        items,
        set(sess.get("theatres", [])),
        page=int(sess.get("page_theatres", 0)),
        page_size=8,
        prefix="et",
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"eany|{mid}"},
            {"text": "Clear", "callback_data": f"eclear|{mid}"},
        ],
    )
    send_text(chat_id, titled(sess.get("url", ""), "Selected: any (all)."), reply_markup=kb)


def cb_eclear(chat_id: str, mid: str):
    sid = f"editt-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        sess["theatres"] = []
        set_ui_session(conn, chat_id, sid, sess)
        items = sess.get("items") or list(DEFAULT_THEATRES)
    kb = kb_theatre_picker(
        mid, items, set(), page=int(sess.get("page_theatres", 0)), page_size=8, prefix="et"
    )
    kb["inline_keyboard"].insert(
        0,
        [
            {"text": "Use Any (all)", "callback_data": f"eany|{mid}"},
            {"text": "Clear", "callback_data": f"eclear|{mid}"},
        ],
    )
    send_text(chat_id, titled(sess.get("url", ""), "Cleared selection."), reply_markup=kb)


def cb_etsave(chat_id: str, mid: str):
    sid = f"editt-{mid}"
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Re-run edit.")
            return
        ths = sess.get("theatres", [])
        r = get_monitor(conn, mid)
        set_theatres(conn, mid, ths)
        clear_ui_session(conn, chat_id, sid)
    send_text(chat_id, titled(r or mid, f"[{mid}] Theatres updated."))


def cb_etcancel(chat_id: str, mid: str):
    sid = f"editt-{mid}"
    with connect() as conn:
        clear_ui_session(conn, chat_id, sid)
    send_text(chat_id, f"[{mid}] Edit canceled.")


def register(dp):
    dp.callback("edit_dates", cmd_edit_dates)
    dp.callback("edit_theatres", cmd_edit_theatres)
    dp.callback("epick", cb_epick)
    dp.callback("epg", lambda chat_id, mid, opt: cb_epg(chat_id, mid, int(opt or "0")))
    dp.callback("esave", cb_esave)
    dp.callback("ecancel", cb_ecancel)
    dp.callback("etpick", lambda chat_id, mid, opt: cb_etpick(chat_id, mid, int(opt)))
    dp.callback("etpg", lambda chat_id, mid, opt: cb_etpg(chat_id, mid, int(opt or "0")))
    dp.callback("eany", cb_eany)
    dp.callback("eclear", cb_eclear)
    dp.callback("etsave", cb_etsave)
    dp.callback("etcancel", cb_etcancel)
