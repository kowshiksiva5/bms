#!/usr/bin/env python3
from __future__ import annotations
import os, requests, sys, json

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

COMMANDS = [
    {"command":"new",          "description":"Create a paused monitor from a URL"},
    {"command":"list",         "description":"List monitors"},
    {"command":"status",       "description":"Show monitor status (/status <id>)"},
    {"command":"pause",        "description":"Pause a monitor (/pause <id>)"},
    {"command":"resume",       "description":"Resume a monitor (/resume <id>)"},
    {"command":"stop",         "description":"Stop a monitor (/stop <id>)"},
    {"command":"restart",      "description":"Restart browser driver (/restart <id>)"},
    {"command":"discover",     "description":"Discover theatres for a monitor (/discover <id>)"},
    {"command":"setinterval",  "description":"Set interval in minutes (/setinterval <id> <m>)"},
    {"command":"timewin",      "description":"Limit to HH:MM-HH:MM or clear (/timewin <id> <win>)"},
    {"command":"daily",        "description":"Daily digest on/off [HH:MM]"},
    {"command":"help",         "description":"Show help"},
]

def ensure_bot_commands(scope="all_private_chats"):
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set; skipping setMyCommands")
        return False
    payload = {
        "commands": COMMANDS,
        "scope": {"type": scope}
    }
    r = requests.post(f"{API}/setMyCommands", json=payload, timeout=20)
    ok = (r.status_code < 300 and r.json().get("ok"))
    if not ok:
        print("setMyCommands failed:", r.status_code, r.text)
    return ok

if __name__ == "__main__":
    ok = ensure_bot_commands()
    print("Commands updated." if ok else "Failed to update commands.")
