#!/usr/bin/env python3
from __future__ import annotations
import os, time, re, json, secrets, sys
from typing import List, Set

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from store import (
    connect, list_monitors, get_monitor, set_state, set_reload, set_dates,
    set_interval, set_time_window, set_theatres, set_mode,
    get_indexed_theatres, get_ui_session, set_ui_session, clear_ui_session
)
from bot.keyboards import kb_main, kb_date_picker, kb_theatre_picker, kb_interval_picker, kb_duration_picker
from bot.telegram_api import send_text, answer_cbq, get_updates
from bot.commands import ensure_bot_commands
from utils import titled, movie_title_from_url


ALLOWED = set([x.strip() for x in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS","").split(",") if x.strip()])
UPD_OFF = os.environ.get("BOT_OFFSET_FILE","./artifacts/bot_offset.txt")

DEFAULT_THEATRES = [
    "AMB Cinemas: Gachibowli",
    "Bhramaramba 70MM A/C 4K Dolby: Kukatpally",
    "Cinepolis: Lulu Mall, Hyderabad",
    "INOX: GSM Mall, Hyderabad",
    "Miraj Cinemas: CineTown, Miyapur",
    "Miraj Cinemas: Geeta, Chandanagar",
    "PVR ICON: Hitech, Madhapur, Hyderabad",
    "PVR: Atrium Gachibowli, Hyderabad",
    "INOX: Prism Mall, Hyderabad",
    "PVR: Inorbit, Cyberabad",
    "PVR: Nexus Mall Kukatpally, Hyderabad",
    "PVR: Preston, Gachibowli Hyderabad",
    "INOX: SMR Vinay Metro Mall, Hyderabad",
    "GPR Multiplex: Nizampet, Hyderabad",
]

def _allowed(chat_id: int) -> bool:
    return (not ALLOWED) or (str(chat_id) in ALLOWED)

def _fmt_ts(ts: int|None) -> str:
    if not ts: return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

def _eta(row) -> str:
    now = int(time.time())
    eta = "—"
    if row and row["last_run_ts"]:
        left = int(row["last_run_ts"]) + int(row["interval_min"])*60 - now
        if left > 0: eta = f"{left//60}m {left%60}s"
    return eta

def _monitor_summary(r) -> str:
    th = len(json.loads(r["theatres"]) if r["theatres"] else [])
    return (f"[{r['id']}] {r['state']} • every {r['interval_min']}m • next ~ {_eta(r)}\n"
            f"Dates: {r['dates']}  |  Theatres: {th}  |  Window: {(r['time_start'] or '—')}–{(r['time_end'] or '—')}\n"
            f"Mode: {r['mode'] or 'FIXED'} | Rolling: {r['rolling_days']} | Until: {r['end_date'] or '—'}\n"
            f"Last run: {_fmt_ts(r['last_run_ts'])}  |  Last alert: {_fmt_ts(r['last_alert_ts'])}\n"
            f"URL: {r['url']}")

def cmd_list(chat_id: str):
    with connect() as conn:
        rows = list_monitors(conn)
    if not rows:
        send_text(chat_id, "No monitors."); return
    for r in rows:
        send_text(chat_id, titled(r, _monitor_summary(r)), reply_markup=kb_main(r["id"], r["state"]))

def cmd_status(chat_id: str, mid: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
    if not r:
        send_text(chat_id, f"Monitor {mid} not found."); return
    send_text(chat_id, titled(r, _monitor_summary(r)), reply_markup=kb_main(mid, r["state"]))

def cmd_new(chat_id: str, url: str):
    url = url.strip()
    if not url:
        send_text(chat_id, "Usage: /new <buytickets URL>"); return
    sid = "new-" + secrets.token_hex(3)
    sess = {
        "mode":"create",
        "url": url,
        "dates": [],
        "theatres": [],
        "interval": 5,
        "page_dates": 0,
        "page_theatres": 0,
        "dur_mode": "FIXED",
        "dur_rolling": 7,
        "dur_until": None,
    }
    with connect() as conn:
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(url, "Step 1/5 — Select dates for new monitor (toggle then Save):"),
              reply_markup=kb_date_picker(sid, set(), 0, total_days=28, prefix="c"))

def _build_theatre_keyboard_for_create(sid: str, selected: set, page: int):
    kb = kb_theatre_picker(sid, DEFAULT_THEATRES, selected, page=page, page_size=8, prefix="ct")
    kb["inline_keyboard"].insert(0, [
        {"text":"Use Any (all)","callback_data":f"cany|{sid}"},
        {"text":"All defaults","callback_data":f"call|{sid}"},
        {"text":"Clear","callback_data":f"cclear|{sid}"},
    ])
    return kb

# dates
def cb_cpick(chat_id: str, sid: str, d8: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = set(sess.get("dates", []))
        if d8 in sel: sel.remove(d8)
        else: sel.add(d8)
        sess["dates"] = sorted(list(sel))
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], f"Step 1/5 — {len(sel)} date(s) selected. Save to continue."),
              reply_markup=kb_date_picker(sid, sel, sess.get("page_dates",0), total_days=28, prefix="c"))

def cb_cpg(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["page_dates"] = max(0, int(page))
        set_ui_session(conn, chat_id, sid, sess)
        sel = set(sess.get("dates", []))
    send_text(chat_id, titled(sess["url"], "Page changed."),
              reply_markup=kb_date_picker(sid, sel, sess["page_dates"], total_days=28, prefix="c"))

def cb_csave(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = sorted(set(sess.get("dates", [])))
        if not sel:
            send_text(chat_id, "Pick at least 1 date."); return
        sess["page_theatres"] = 0
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 2/5 — Select theatres (toggle then Save):"),
              reply_markup=_build_theatre_keyboard_for_create(sid, set(sess.get("theatres", [])), 0))

def cb_ccancel(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        url = (sess or {}).get("url","")
        clear_ui_session(conn, chat_id, sid)
    text = "Creation canceled."
    send_text(chat_id, titled(url, text) if url else text)

# theatres
def cb_ctpick(chat_id: str, sid: str, idx: int):
    idx = int(idx)
    if idx < 0 or idx >= len(DEFAULT_THEATRES): return
    name = DEFAULT_THEATRES[idx]
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = set(sess.get("theatres", []))
        if name in sel: sel.remove(name)
        else: sel.add(name)
        sel.discard("any")
        sess["theatres"] = sorted(list(sel))
        set_ui_session(conn, chat_id, sid, sess)
        page = int(sess.get("page_theatres",0))
    send_text(chat_id, titled(sess["url"], f"Step 2/5 — {len(sel)} theatre(s) selected."),
              reply_markup=_build_theatre_keyboard_for_create(sid, sel, page))

def cb_ctpg(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["page_theatres"] = max(0, int(page))
        set_ui_session(conn, chat_id, sid, sess)
        sel = set(sess.get("theatres", []))
    send_text(chat_id, titled(sess["url"], "Page changed."),
              reply_markup=_build_theatre_keyboard_for_create(sid, sel, sess["page_theatres"]))

def cb_cany(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["theatres"] = ["any"]
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 2/5 — Selected: any (all theatres)."),
              reply_markup=_build_theatre_keyboard_for_create(sid, set(sess["theatres"]), sess.get("page_theatres",0)))

def cb_call(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["theatres"] = list(DEFAULT_THEATRES)
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 2/5 — All defaults selected."),
              reply_markup=_build_theatre_keyboard_for_create(sid, set(sess["theatres"]), sess.get("page_theatres",0)))

def cb_cclear(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["theatres"] = []
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 2/5 — Cleared selection."),
              reply_markup=_build_theatre_keyboard_for_create(sid, set(), sess.get("page_theatres",0)))

def cb_ctsave(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = sess.get("theatres", [])
        if not sel:
            send_text(chat_id, "Pick at least 1 theatre, or choose 'Use Any'."); return
        cur = int(sess.get("interval", 5))
    send_text(chat_id, titled(sess["url"], "Step 3/5 — Select interval (minutes):"),
              reply_markup=kb_interval_picker(sid, cur))

def cb_ctcancel(chat_id: str, sid: str):
    cb_ccancel(chat_id, sid)

# interval → duration
def cb_ivalset(chat_id: str, sid: str, minutes: int):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["interval"] = int(minutes)
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], f"Step 3/5 — Interval set to {minutes}m."),
              reply_markup=kb_interval_picker(sid, int(minutes)))

def cb_ivalback(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sel = set(sess.get("theatres", []))
    send_text(chat_id, titled(sess["url"], "Step 2/5 — Select theatres:"),
              reply_markup=_build_theatre_keyboard_for_create(sid, sel, sess.get("page_theatres",0)))

def cb_idurnext(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
    send_text(chat_id, titled(sess["url"], "Step 4/5 — Duration mode:"),
              reply_markup=kb_duration_picker(sid, sess.get("dur_mode","FIXED"), int(sess.get("dur_rolling",7)), sess.get("dur_until")))

def cb_idurback(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
    send_text(chat_id, titled(sess["url"], "Step 3/5 — Select interval (minutes):"),
              reply_markup=kb_interval_picker(sid, int(sess.get("interval",5))))

def cb_dur(chat_id: str, sid: str, mode: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        sess["dur_mode"] = mode
        set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 4/5 — Duration mode:"),
              reply_markup=kb_duration_picker(sid, mode, int(sess.get("dur_rolling",7)), sess.get("dur_until")))

def cb_rplus(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        r = int(sess.get("dur_rolling",7)); r = min(30, r+1); sess["dur_rolling"]=r
        sess["dur_mode"]="ROLLING"; set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 4/5 — Duration mode:"),
              reply_markup=kb_duration_picker(sid, "ROLLING", r, sess.get("dur_until")))

def cb_rminus(chat_id: str, sid: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        r = int(sess.get("dur_rolling",7)); r = max(1, r-1); sess["dur_rolling"]=r
        sess["dur_mode"]="ROLLING"; set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 4/5 — Duration mode:"),
              reply_markup=kb_duration_picker(sid, "ROLLING", r, sess.get("dur_until")))

# UNTIL date picker
def cb_uopen(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess=get_ui_session(conn, chat_id, sid)
        cur = set([sess["dur_until"]]) if sess.get("dur_until") else set()
    from bot.keyboards import kb_date_picker
    send_text(chat_id, titled(sess["url"], "Pick an end date (Save sets mode=UNTIL):"),
              reply_markup=kb_date_picker(sid, cur, int(page), total_days=60, prefix="u"))

def cb_upick(chat_id: str, sid: str, d8: str):
    with connect() as conn:
        sess=get_ui_session(conn, chat_id, sid)
        sess["dur_until"] = d8 if sess.get("dur_until")!=d8 else None
        set_ui_session(conn, chat_id, sid, sess)
    cur = set([sess["dur_until"]]) if sess.get("dur_until") else set()
    from bot.keyboards import kb_date_picker
    send_text(chat_id, titled(sess["url"], "Pick an end date (Save sets mode=UNTIL):"),
              reply_markup=kb_date_picker(sid, cur, int(sess.get("page_until",0)), total_days=60, prefix="u"))

def cb_upg(chat_id: str, sid: str, page: int):
    with connect() as conn:
        sess=get_ui_session(conn, chat_id, sid)
        sess["page_until"]=int(page)
        set_ui_session(conn, chat_id, sid, sess)
    cur = set([sess["dur_until"]]) if sess.get("dur_until") else set()
    from bot.keyboards import kb_date_picker
    send_text(chat_id, titled(sess["url"], "Pick an end date (Save sets mode=UNTIL):"),
              reply_markup=kb_date_picker(sid, cur, int(page), total_days=60, prefix="u"))

def cb_usave(chat_id: str, sid: str):
    with connect() as conn:
        sess=get_ui_session(conn, chat_id, sid)
        if not sess.get("dur_until"):
            send_text(chat_id, "Please pick an end date."); return
        sess["dur_mode"]="UNTIL"; set_ui_session(conn, chat_id, sid, sess)
    send_text(chat_id, titled(sess["url"], "Step 4/5 — Duration mode:"), 
              reply_markup=kb_duration_picker(sid, "UNTIL", int(sess.get("dur_rolling",7)), sess.get("dur_until")))

def cb_ucancel(chat_id: str, sid: str):
    cb_idurnext(chat_id, sid)

def cb_cfinish(chat_id: str, sid: str, mode: str):
    with connect() as conn:
        sess = get_ui_session(conn, chat_id, sid)
        if not sess:
            send_text(chat_id, "Session expired. Please /new again."); return
        url = sess.get("url","").strip()
        dates = sess.get("dates", [])
        ths = sess.get("theatres", [])
        interval = int(sess.get("interval", 5))
        dur_mode = (sess.get("dur_mode") or "FIXED").upper()
        dur_rolling = int(sess.get("dur_rolling") or 7)
        dur_until = sess.get("dur_until")
        if not url or not dates or not ths:
            send_text(chat_id, "Missing info. Make sure you selected dates, theatres and interval."); return
        mid = "m"+secrets.token_hex(3)
        state = "RUNNING" if mode=="start" else "PAUSED"
        now = int(time.time())
        conn.execute("""INSERT INTO monitors
            (id,url,dates,theatres,interval_min,baseline,state,owner_chat_id,created_at,updated_at,heartbeat_minutes,reload,mode,rolling_days,end_date)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", 
            (mid, url, ",".join(sorted(set(dates))),
             json.dumps(["any"] if "any" in ths else ths, ensure_ascii=False),
             interval, 1, state, chat_id, now, now, 180, 0, dur_mode, (dur_rolling if dur_mode=='ROLLING' else 0), (dur_until if dur_mode=='UNTIL' else None)))
        conn.commit()
        clear_ui_session(conn, chat_id, sid)

    cmd = f'python worker.py --monitor-id {mid} --monitor --trace --artifacts-dir ./artifacts'
    msg = [
        f"✅ Created [{mid}] ({state})",
        f"URL: {url}",
        f"Dates: {','.join(sorted(set(dates)))}",
        f"Theatres: {'any' if 'any' in ths else str(len(ths))+' selected'}",
        f"Interval: {interval}m",
        f"Mode: {dur_mode}{' '+str(dur_rolling)+'d' if dur_mode=='ROLLING' else (' until '+dur_until if dur_mode=='UNTIL' else '')}",
        "",
        "To start the worker (if not already running):",
        cmd
    ]
    send_text(chat_id, titled(url, "\n".join(msg)))

def cmd_pause(chat_id: str, mid: str):   _ack_state(chat_id, mid, "PAUSED", "Paused")
def cmd_resume(chat_id: str, mid: str):  _ack_state(chat_id, mid, "RUNNING", "Resumed")
def cmd_stop(chat_id: str, mid: str):    _ack_state(chat_id, mid, "STOPPING", "Stopping now")
def cmd_restart(chat_id: str, mid: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        ok = set_reload(conn, mid)
    text = f"[{mid}] {'Restarting driver…' if ok else 'Not found'}"
    send_text(chat_id, titled(r, text) if r else text)
def cmd_discover(chat_id: str, mid: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        ok = set_state(conn, mid, "DISCOVER")
    text = f"[{mid}] {'Discovering theatre list…' if ok else 'Not found'}\n(Worker will run discovery and then pause.)"
    send_text(chat_id, titled(r, text) if r else text)
def _ack_state(chat_id: str, mid: str, new_state: str, msg: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        ok = set_state(conn, mid, new_state)
    text = f"[{mid}] {msg if ok else 'Not found'}"
    send_text(chat_id, titled(r, text) if r else text)
def cmd_setinterval(chat_id: str, mid: str, val: str):
    try:
        n = int(val)
        if n < 1: raise ValueError()
    except Exception:
        send_text(chat_id, "Usage: /setinterval <id> <minutes>"); return
    with connect() as conn:
        r = get_monitor(conn, mid)
        set_interval(conn, mid, n)
    text = f"[{mid}] Interval set to {n} min"
    send_text(chat_id, titled(r, text) if r else text)
def cmd_timewin(chat_id: str, mid: str, arg: str):
    if arg.lower()=="clear":
        with connect() as conn:
            r = get_monitor(conn, mid)
            set_time_window(conn, mid, None, None)
        text = f"[{mid}] Time window cleared"
        send_text(chat_id, titled(r, text) if r else text); return
    m = re.match(r"^\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*$", arg)
    if not m:
        send_text(chat_id, "Usage: /timewin <id> HH:MM-HH:MM or 'clear'"); return
    s,e = m.group(1), m.group(2)
    with connect() as conn:
        r = get_monitor(conn, mid)
        set_time_window(conn, mid, s, e)
    text = f"[{mid}] Time window set: {s}–{e}"
    send_text(chat_id, titled(r, text) if r else text)

HELP = (
"Commands:\n"
"/new <url> — start inline creation wizard\n"
"/list — list monitors (with buttons)\n"
"/status <id>\n"
"/pause <id>  |  /resume <id>  |  /stop <id>  |  /restart <id>\n"
"/discover <id>\n"
"/setinterval <id> <minutes>\n"
"/timewin <id> <HH:MM-HH:MM|clear>\n"
"/help"
)

def handle_command(chat_id: str, text: str):
    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]
    if cmd in ("/start","/help"): send_text(chat_id, HELP); return
    if cmd == "/list":            cmd_list(chat_id); return
    if cmd == "/status" and args: cmd_status(chat_id, args[0]); return
    if cmd == "/new" and args:    cmd_new(chat_id, " ".join(args)); return
    if cmd == "/pause" and args:  cmd_pause(chat_id, args[0]); return
    if cmd == "/resume" and args: cmd_resume(chat_id, args[0]); return
    if cmd == "/stop" and args:   cmd_stop(chat_id, args[0]); return
    if cmd == "/restart" and args:cmd_restart(chat_id, args[0]); return
    if cmd == "/discover" and args: cmd_discover(chat_id, args[0]); return
    if cmd == "/setinterval" and len(args)>=2: 
        cmd_setinterval(chat_id, args[0], args[1]); return
    if cmd == "/timewin" and len(args)>=2: 
        cmd_timewin(chat_id, args[0], args[1]); return
    send_text(chat_id, "Unknown or bad usage.\n\n"+HELP)

def handle_callback(upd):
    cq = upd["callback_query"]; cbid = cq["id"]
    msg  = cq.get("message") or {}
    chat_id = str(msg.get("chat",{}).get("id"))
    data = cq.get("data","")
    from bot.telegram_api import answer_cbq as _answer_cbq
    _answer_cbq(cbid)
    if not _allowed(int(chat_id)): return
    parts = data.split("|")
    action = parts[0] if parts else ""
    id1 = parts[1] if len(parts)>1 else ""
    opt = parts[2] if len(parts)>2 else ""

    # Existing monitor controls
    if action == "status":        cmd_status(chat_id, id1); return
    if action == "pause":         cmd_pause(chat_id, id1); return
    if action == "resume":        cmd_resume(chat_id, id1); return
    if action == "stop":          cmd_stop(chat_id, id1); return
    if action == "restart":       cmd_restart(chat_id, id1); return
    if action == "discover":      cmd_discover(chat_id, id1); return

    # Creation: dates
    if action == "cpick":         cb_cpick(chat_id, id1, opt); return
    if action == "cpg":           cb_cpg(chat_id, id1, int(opt or "0")); return
    if action == "csave":         cb_csave(chat_id, id1); return
    if action == "ccancel":       cb_ccancel(chat_id, id1); return

    # Creation: theatres
    if action == "ctpick":        cb_ctpick(chat_id, id1, opt); return
    if action == "ctpg":          cb_ctpg(chat_id, id1, int(opt or "0")); return
    if action == "ctsave":        cb_ctsave(chat_id, id1); return
    if action == "ctcancel":      cb_ctcancel(chat_id, id1); return
    if action == "cany":          cb_cany(chat_id, id1); return
    if action == "call":          cb_call(chat_id, id1); return
    if action == "cclear":        cb_cclear(chat_id, id1); return

    # Interval
    if action == "ivalset":       cb_ivalset(chat_id, id1, int(opt or "5")); return
    if action == "ivalback":      cb_ivalback(chat_id, id1); return
    if action == "idurnext":      cb_idurnext(chat_id, id1); return

    # Duration
    if action == "idurback":      cb_idurback(chat_id, id1); return
    if action == "dur":           cb_dur(chat_id, id1, opt or "FIXED"); return
    if action == "rplus":         cb_rplus(chat_id, id1); return
    if action == "rminus":        cb_rminus(chat_id, id1); return
    if action == "uopen":         cb_uopen(chat_id, id1, int(opt or "0")); return
    if action == "upick":         cb_upick(chat_id, id1, opt); return
    if action == "upg":           cb_upg(chat_id, id1, int(opt or "0")); return
    if action == "usave":         cb_usave(chat_id, id1); return
    if action == "ucancel":       cb_ucancel(chat_id, id1); return

    if action == "cfinish":       cb_cfinish(chat_id, id1, opt or "pause"); return

    send_text(chat_id, "Unknown action.")

def main():
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        ok=ensure_bot_commands()
        if not ok:
            print("Failed to update commands.")
    else:
        print("TELEGRAM_BOT_TOKEN not set; skipping setMyCommands")
    try:
        with open(UPD_OFF,"r") as f: offset = int((f.read() or "0").strip())
    except Exception:
        offset = 0
    while True:
        try:
            resp = get_updates(offset)
            for upd in resp.get("result", []):
                offset = upd["update_id"]
                if "callback_query" in upd:
                    handle_callback(upd); continue
                m = upd.get("message") or upd.get("edited_message")
                if not m: continue
                chat_id = str(m["chat"]["id"])
                text = (m.get("text") or "").strip()
                if not text: continue
                if not _allowed(int(chat_id)):
                    send_text(chat_id, "Unauthorized."); continue
                handle_command(chat_id, text)
            try:
                with open(UPD_OFF,"w") as f: f.write(str(offset))
            except Exception: pass
        except Exception as e:
            print("poll error:", e); time.sleep(2)

if __name__ == "__main__":
    main()
