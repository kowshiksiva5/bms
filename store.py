#!/usr/bin/env python3
from __future__ import annotations
import os, time, json, sqlite3
from typing import List, Optional, Dict, Any

STATE_DB = os.environ.get("STATE_DB", "./artifacts/state.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS monitors(
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  dates TEXT NOT NULL,
  theatres TEXT NOT NULL,             -- JSON array
  interval_min INTEGER NOT NULL,
  baseline INTEGER NOT NULL,
  state TEXT NOT NULL,                -- RUNNING|PAUSED|STOPPING|STOPPED|DISCOVER
  snooze_until INTEGER,
  owner_chat_id TEXT,
  created_at INTEGER,
  updated_at INTEGER,
  last_run_ts INTEGER,
  last_alert_ts INTEGER,
  heartbeat_minutes INTEGER DEFAULT 180,
  reload INTEGER DEFAULT 0,
  time_start TEXT,
  time_end   TEXT
);
CREATE TABLE IF NOT EXISTS seen(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  time TEXT NOT NULL,
  first_seen_ts INTEGER,
  PRIMARY KEY(monitor_id, date, theatre, time)
);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  started_ts INTEGER,
  finished_ts INTEGER,
  status TEXT,
  error TEXT
);
CREATE TABLE IF NOT EXISTS snapshots(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  times_json TEXT NOT NULL,
  updated_at INTEGER,
  PRIMARY KEY(monitor_id,date,theatre)
);
CREATE TABLE IF NOT EXISTS theatres_index(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  last_seen_ts INTEGER,
  PRIMARY KEY(monitor_id,date,theatre)
);
CREATE TABLE IF NOT EXISTS daily(
  chat_id TEXT PRIMARY KEY,
  hhmm TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  last_sent_ts INTEGER
);
CREATE TABLE IF NOT EXISTS ui_sessions(
  chat_id TEXT NOT NULL,
  monitor_id TEXT NOT NULL,
  data_json TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(chat_id, monitor_id)
);
"""

def _ensure_dir(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

def connect() -> sqlite3.Connection:
    _ensure_dir(STATE_DB)
    conn = sqlite3.connect(STATE_DB, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for stmt in SCHEMA.strip().split(";\n"):
        s = stmt.strip()
        if s:
            conn.execute(s)
    conn.commit()
    # defensive migrations
    for alter in [
        "ALTER TABLE monitors ADD COLUMN reload INTEGER DEFAULT 0",
        "ALTER TABLE monitors ADD COLUMN time_start TEXT",
        "ALTER TABLE monitors ADD COLUMN time_end TEXT",
    ]:
        try:
            conn.execute(alter); conn.commit()
        except Exception:
            pass
    return conn

# --- Monitors CRUD ---
def list_monitors(conn) -> List[sqlite3.Row]:
    return conn.execute("""SELECT * FROM monitors ORDER BY created_at DESC""").fetchall()

def get_monitor(conn, mid: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM monitors WHERE id=?", (mid,)).fetchone()

def set_state(conn, mid: str, state: str) -> bool:
    cur = conn.execute("UPDATE monitors SET state=?, updated_at=? WHERE id=?", (state, int(time.time()), mid))
    conn.commit()
    return cur.rowcount > 0

def set_reload(conn, mid: str) -> bool:
    cur = conn.execute("UPDATE monitors SET reload=1, updated_at=? WHERE id=?", (int(time.time()), mid))
    conn.commit()
    return cur.rowcount > 0

def set_dates(conn, mid: str, dates_csv: str) -> bool:
    cur = conn.execute("UPDATE monitors SET dates=?, updated_at=? WHERE id=?", (dates_csv, int(time.time()), mid))
    conn.commit()
    return cur.rowcount > 0

def set_interval(conn, mid: str, minutes: int) -> bool:
    cur = conn.execute("UPDATE monitors SET interval_min=?, updated_at=? WHERE id=?", (minutes, int(time.time()), mid))
    conn.commit()
    return cur.rowcount > 0

def toggle_baseline(conn, mid: str) -> Optional[int]:
    r = get_monitor(conn, mid)
    if not r: return None
    newv = 0 if int(r["baseline"])==1 else 1
    conn.execute("UPDATE monitors SET baseline=?, updated_at=? WHERE id=?", (newv, int(time.time()), mid))
    conn.commit()
    return newv

def set_time_window(conn, mid: str, start_hhmm: Optional[str], end_hhmm: Optional[str]) -> bool:
    cur = conn.execute("UPDATE monitors SET time_start=?, time_end=?, updated_at=? WHERE id=?",
                       (start_hhmm, end_hhmm, int(time.time()), mid))
    conn.commit()
    return cur.rowcount > 0

def set_theatres(conn, mid: str, theatres: List[str]) -> bool:
    cur = conn.execute("UPDATE monitors SET theatres=?, updated_at=? WHERE id=?",
                       (json.dumps(theatres, ensure_ascii=False), int(time.time()), mid))
    conn.commit()
    return cur.rowcount > 0

# --- Theatre index helpers ---
def get_indexed_theatres(conn, mid: str) -> List[str]:
    rows = conn.execute("""SELECT DISTINCT theatre FROM theatres_index WHERE monitor_id=? ORDER BY theatre COLLATE NOCASE""", (mid,)).fetchall()
    return [r["theatre"] for r in rows]

# --- UI session helpers (inline editors) ---
def get_ui_session(conn, chat_id: str, mid: str) -> Dict[str, Any]:
    r = conn.execute("SELECT data_json FROM ui_sessions WHERE chat_id=? AND monitor_id=?", (chat_id, mid)).fetchone()
    if not r: return {}
    try:
        return json.loads(r["data_json"]) or {}
    except Exception:
        return {}

def set_ui_session(conn, chat_id: str, mid: str, data: Dict[str, Any]):
    conn.execute("""INSERT INTO ui_sessions(chat_id,monitor_id,data_json,updated_at)
                    VALUES(?,?,?,?)
                    ON CONFLICT(chat_id,monitor_id) DO UPDATE SET
                    data_json=excluded.data_json, updated_at=excluded.updated_at
    """, (chat_id, mid, json.dumps(data, ensure_ascii=False), int(time.time())))
    conn.commit()

def clear_ui_session(conn, chat_id: str, mid: str):
    conn.execute("DELETE FROM ui_sessions WHERE chat_id=? AND monitor_id=?", (chat_id, mid))
    conn.commit()
