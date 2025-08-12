from __future__ import annotations
import os
import re
import shutil
import time

from store import (
    connect,
    list_monitors,
    get_monitor,
    set_state,
    set_reload,
    set_interval,
    set_time_window,
    delete_monitor,
    set_snooze,
    clear_snooze,
)
from ..keyboards import kb_main
from ..telegram_api import send_text, send_alert
from ..utils import monitor_summary
from utils import titled


# ---- Helpers ----

def _health_summary() -> str:
    lines = []
    db_path = os.environ.get("STATE_DB", "./artifacts/state.db")
    size = 0
    try:
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
        lines.append(f"DB: {db_path} ({size//1024} KiB)")
    except Exception as e:  # pragma: no cover - best effort
        lines.append(f"DB: error: {e}")
    art = os.environ.get("ART_DIR", "./artifacts")
    try:
        os.makedirs(art, exist_ok=True)
        _, _, files = next(os.walk(art))
        lines.append(f"Artifacts: {art} ({len(files)} files)")
    except Exception:  # pragma: no cover - best effort
        lines.append(f"Artifacts: {art}")
    chrome = os.environ.get(
        "CHROME_BINARY",
        shutil.which("google-chrome") or shutil.which("chrome") or "(not set)",
    )
    lines.append(f"Chrome: {chrome}")
    return "\n".join(lines)


def cmd_health(chat_id: str):
    from store import get_active_monitors

    body = ["🩺 System health"]
    body.append(_health_summary())
    try:
        with connect() as conn:
            rows = get_active_monitors(conn)
        if rows:
            body.append("")
            body.append("Active monitors:")
            for r in rows:
                body.append(
                    f"• {r['id']} — {r['state']} • every {r['interval_min']}m • HB {r['heartbeat_minutes']}m"
                )
        else:
            body.append("")
            body.append("No active monitors.")
    except Exception as e:  # pragma: no cover
        body.append("")
        body.append(f"DB error: {e}")
    send_text(chat_id, "\n".join(body))


# ---- Status and monitor controls ----

def cmd_list(chat_id: str):
    with connect() as conn:
        rows = list_monitors(conn, chat_id)
    if not rows:
        send_text(chat_id, "No monitors.")
        return
    for r in rows:
        send_text(chat_id, titled(r, monitor_summary(r)), reply_markup=kb_main(r["id"], r["state"]))


def cmd_status(chat_id: str, mid: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
    if not r:
        send_text(chat_id, f"Monitor {mid} not found.")
        return
    send_text(chat_id, titled(r, monitor_summary(r)), reply_markup=kb_main(mid, r["state"]))


def _ack_state(chat_id: str, mid: str, new_state: str, msg: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        ok = set_state(conn, mid, new_state)
    text = f"[{mid}] {msg if ok else 'Not found'}"
    send_text(chat_id, titled(r, text) if r else text)


def cmd_pause(chat_id: str, mid: str):
    _ack_state(chat_id, mid, "PAUSED", "Paused")


def cmd_resume(chat_id: str, mid: str):
    _ack_state(chat_id, mid, "RUNNING", "Resumed")


def cmd_stop(chat_id: str, mid: str):
    _ack_state(chat_id, mid, "STOPPING", "Stopping now")


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
    text = (
        f"[{mid}] {'Discovering theatre list…' if ok else 'Not found'}\n"
        "(Worker will run discovery and then pause.)"
    )
    send_text(chat_id, titled(r, text) if r else text)


def cmd_snooze(chat_id: str, mid: str, arg: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        if not r:
            send_text(chat_id, f"Monitor {mid} not found.")
            return
        now = int(time.time())
        if arg == "clear":
            clear_snooze(conn, mid)
            send_alert(r, chat_id, f"⏰ Snooze cleared for [{mid}].")
            return
        dur = 0
        if arg.endswith("h"):
            try:
                dur = int(arg[:-1]) * 3600
            except Exception:
                dur = 0
        elif arg.endswith("m"):
            try:
                dur = int(arg[:-1]) * 60
            except Exception:
                dur = 0
        if dur <= 0:
            send_text(chat_id, "Usage: /snooze <id> <2h|6h|30m|clear>")
            return
        until = now + dur
        set_snooze(conn, mid, until)
        send_alert(
            r,
            chat_id,
            f"⏰ Snoozed [{mid}] for {arg} (until {time.strftime('%H:%M', time.localtime(until))}).",
        )


def cmd_delete(chat_id: str, mid: str):
    with connect() as conn:
        r = get_monitor(conn, mid)
        if not r:
            send_text(chat_id, f"Monitor {mid} not found.")
            return
        ok = delete_monitor(conn, mid)
    send_alert(r, chat_id, f"🗑️ Deleted monitor [{mid}]." if ok else f"Could not delete [{mid}].")


def cmd_setinterval(chat_id: str, mid: str, val: str):
    try:
        n = int(val)
        if n < 1:
            raise ValueError()
    except Exception:
        send_text(chat_id, "Usage: /setinterval <id> <minutes>")
        return
    with connect() as conn:
        r = get_monitor(conn, mid)
        set_interval(conn, mid, n)
    text = f"[{mid}] Interval set to {n} min"
    send_text(chat_id, titled(r, text) if r else text)


def cmd_timewin(chat_id: str, mid: str, arg: str):
    if arg.lower() == "clear":
        with connect() as conn:
            r = get_monitor(conn, mid)
            set_time_window(conn, mid, None, None)
        text = f"[{mid}] Time window cleared"
        send_text(chat_id, titled(r, text) if r else text)
        return
    m = re.match(r"^\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*$", arg)
    if not m:
        send_text(chat_id, "Usage: /timewin <id> HH:MM-HH:MM or 'clear'")
        return
    s, e = m.group(1), m.group(2)
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
    "/snooze <id> <2h|6h|30m|clear>\n"
    "/delete <id>\n"
    "/health — show system health\n"
    "/help"
)


def register(dp):
    dp.command("/list", lambda chat_id, args: cmd_list(chat_id))
    dp.command(
        "/status", lambda chat_id, args: cmd_status(chat_id, args[0]) if args else send_text(chat_id, "Usage: /status <id>")
    )
    dp.command(
        "/pause", lambda chat_id, args: cmd_pause(chat_id, args[0]) if args else send_text(chat_id, "Usage: /pause <id>")
    )
    dp.command(
        "/resume", lambda chat_id, args: cmd_resume(chat_id, args[0]) if args else send_text(chat_id, "Usage: /resume <id>")
    )
    dp.command(
        "/stop", lambda chat_id, args: cmd_stop(chat_id, args[0]) if args else send_text(chat_id, "Usage: /stop <id>")
    )
    dp.command(
        "/restart", lambda chat_id, args: cmd_restart(chat_id, args[0]) if args else send_text(chat_id, "Usage: /restart <id>")
    )
    dp.command(
        "/discover", lambda chat_id, args: cmd_discover(chat_id, args[0]) if args else send_text(chat_id, "Usage: /discover <id>")
    )
    dp.command(
        "/snooze",
        lambda chat_id, args: cmd_snooze(chat_id, args[0], args[1]) if len(args) >= 2 else send_text(chat_id, "Usage: /snooze <id> <2h|6h|30m|clear>"),
    )
    dp.command(
        "/delete", lambda chat_id, args: cmd_delete(chat_id, args[0]) if args else send_text(chat_id, "Usage: /delete <id>")
    )
    dp.command(
        "/setinterval",
        lambda chat_id, args: cmd_setinterval(chat_id, args[0], args[1])
        if len(args) >= 2
        else send_text(chat_id, "Usage: /setinterval <id> <minutes>"),
    )
    dp.command(
        "/timewin",
        lambda chat_id, args: cmd_timewin(chat_id, args[0], args[1])
        if len(args) >= 2
        else send_text(chat_id, "Usage: /timewin <id> <HH:MM-HH:MM|clear>"),
    )
    dp.command("/health", lambda chat_id, args: cmd_health(chat_id))
    dp.callback("status", lambda chat_id, mid, opt: cmd_status(chat_id, mid))
    dp.callback("pause", lambda chat_id, mid, opt: cmd_pause(chat_id, mid))
    dp.callback("resume", lambda chat_id, mid, opt: cmd_resume(chat_id, mid))
    dp.callback("stop", lambda chat_id, mid, opt: cmd_stop(chat_id, mid))
    dp.callback("restart", lambda chat_id, mid, opt: cmd_restart(chat_id, mid))
    dp.callback("discover", lambda chat_id, mid, opt: cmd_discover(chat_id, mid))
    dp.callback("delete", lambda chat_id, mid, opt: cmd_delete(chat_id, mid))
    dp.callback("snooze", lambda chat_id, mid, opt: cmd_snooze(chat_id, mid, opt or "2h"))
