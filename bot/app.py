from __future__ import annotations
import os
import time

from config import TELEGRAM_ALLOWED_CHAT_IDS as _ALLOWED, BOT_OFFSET_FILE as _BOT_OFF
from .telegram_api import send_text, answer_cbq, get_updates
from .commands import ensure_bot_commands
from .handlers import create, edit, status


class Dispatcher:
    def __init__(self) -> None:
        self.command_handlers = {}
        self.callback_handlers = {}

    def command(self, name, func):
        self.command_handlers[name] = func

    def callback(self, action, func):
        self.callback_handlers[action] = func


dispatcher = Dispatcher()
create.register(dispatcher)
edit.register(dispatcher)
status.register(dispatcher)

HELP = status.HELP
ALLOWED = set(_ALLOWED)
UPD_OFF = _BOT_OFF


def _allowed(chat_id: int) -> bool:
    return (not ALLOWED) or (str(chat_id) in ALLOWED)


def handle_command(chat_id: str, text: str):
    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]
    if cmd in ("/start", "/help"):
        send_text(chat_id, HELP)
        return
    handler = dispatcher.command_handlers.get(cmd)
    if handler:
        handler(chat_id, args)
    else:
        send_text(chat_id, "Unknown or bad usage.\n\n" + HELP)


def handle_callback(upd):
    cq = upd["callback_query"]
    cbid = cq["id"]
    msg = cq.get("message") or {}
    chat_id = str(msg.get("chat", {}).get("id"))
    data = cq.get("data", "")
    answer_cbq(cbid)
    if not _allowed(int(chat_id)):
        return
    parts = data.split("|")
    action = parts[0] if parts else ""
    id1 = parts[1] if len(parts) > 1 else ""
    opt = parts[2] if len(parts) > 2 else ""
    handler = dispatcher.callback_handlers.get(action)
    if handler:
        handler(chat_id, id1, opt)
    else:
        send_text(chat_id, "Unknown action.")


def main():
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        ok = ensure_bot_commands()
        if not ok:
            print("Failed to update commands.")
    else:
        print("TELEGRAM_BOT_TOKEN not set; skipping setMyCommands")
    try:
        with open(UPD_OFF, "r") as f:
            offset = int((f.read() or "0").strip())
    except Exception:
        offset = 0
    while True:
        try:
            resp = get_updates(offset)
            for upd in resp.get("result", []):
                offset = upd["update_id"]
                if "callback_query" in upd:
                    handle_callback(upd)
                    continue
                m = upd.get("message") or upd.get("edited_message")
                if not m:
                    continue
                chat_id = str(m["chat"]["id"])
                text = (m.get("text") or "").strip()
                if not text:
                    continue
                if not _allowed(int(chat_id)):
                    send_text(chat_id, "Unauthorized.")
                    continue
                handle_command(chat_id, text)
            try:
                with open(UPD_OFF, "w") as f:
                    f.write(str(offset))
            except Exception:
                pass
        except Exception as e:
            print("poll error:", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
