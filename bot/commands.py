#!/usr/bin/env python3
from __future__ import annotations
import os, requests
BOT_TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN",""); API=f"https://api.telegram.org/bot{BOT_TOKEN}"
COMMANDS=[
    {"command":"new","description":"Create monitor (wizard)"},
    {"command":"list","description":"List monitors"},
    {"command":"status","description":"Status of a monitor (/status <id>)"},
    {"command":"pause","description":"Pause (/pause <id>)"},
    {"command":"resume","description":"Resume (/resume <id>)"},
    {"command":"stop","description":"Stop (/stop <id>)"},
    {"command":"restart","description":"Restart driver (/restart <id>)"},
    {"command":"discover","description":"Discover theatres (/discover <id>)"},
    {"command":"setinterval","description":"Set interval (/setinterval <id> <m>)"},
    {"command":"timewin","description":"Limit HH:MM-HH:MM or clear (/timewin <id> <win>)"},
    {"command":"health","description":"Show system health"},
    {"command":"import","description":"Import monitor from JSON (/import <json>)"},
    {"command":"snooze","description":"Snooze monitor (/snooze <id> <2h|6h|clear>)"},
    {"command":"delete","description":"Delete monitor (/delete <id>)"},
    {"command":"help","description":"Help"},
]
def ensure_bot_commands(scope="all_private_chats"):
    if not BOT_TOKEN: return False
    r=requests.post(f"{API}/setMyCommands", json={"commands":COMMANDS,"scope":{"type":scope}}, timeout=20)
    return r.status_code<300 and r.json().get("ok")
