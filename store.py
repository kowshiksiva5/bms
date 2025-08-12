#!/usr/bin/env python3
from __future__ import annotations
import os
import time
import sqlite3
from config import STATE_DB as _STATE_DB
from typing import List

STATE_DB = _STATE_DB

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS monitors(
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  dates TEXT NOT NULL,
  theatres TEXT NOT NULL,
  interval_min INTEGER NOT NULL,
  baseline INTEGER NOT NULL,
  state TEXT NOT NULL,
  snooze_until INTEGER,
  owner_chat_id TEXT,
  mode TEXT DEFAULT 'FIXED',
  rolling_days INTEGER DEFAULT 0,
  end_date TEXT,
  time_start TEXT,
  time_end TEXT,
  heartbeat_minutes INTEGER DEFAULT 180,
  created_at INTEGER,
  updated_at INTEGER,
  last_run_ts INTEGER,
  last_alert_ts INTEGER,
  reload INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS seen(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  time TEXT NOT NULL,
  first_seen_ts INTEGER,
  PRIMARY KEY(monitor_id, date, theatre, time)
);
CREATE TABLE IF NOT EXISTS theatres_index(
  monitor_id TEXT NOT NULL,
  date TEXT NOT NULL,
  theatre TEXT NOT NULL,
  last_seen_ts INTEGER,
  PRIMARY KEY(monitor_id,date,theatre)
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
    conn.executescript(SCHEMA)
    for alter in [
        "ALTER TABLE monitors ADD COLUMN mode TEXT DEFAULT 'FIXED'",
        "ALTER TABLE monitors ADD COLUMN rolling_days INTEGER DEFAULT 0",
        "ALTER TABLE monitors ADD COLUMN end_date TEXT",
        "ALTER TABLE monitors ADD COLUMN time_start TEXT",
        "ALTER TABLE monitors ADD COLUMN time_end TEXT",
        "ALTER TABLE monitors ADD COLUMN reload INTEGER DEFAULT 0",
    ]:
        try:
            conn.execute(alter)
            conn.commit()
        except Exception:
            pass
    return conn


def list_monitors(conn, chat_id: str | None = None):
    if chat_id:
        return conn.execute(
            "SELECT * FROM monitors WHERE owner_chat_id=? ORDER BY created_at DESC",
            (chat_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM monitors ORDER BY created_at DESC").fetchall()


def get_monitor(conn, mid):
    return conn.execute("SELECT * FROM monitors WHERE id=?", (mid,)).fetchone()


def set_state(conn, mid, state):
    cur = conn.execute(
        "UPDATE monitors SET state=?,updated_at=? WHERE id=?",
        (state, int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


def set_reload(conn, mid):
    cur = conn.execute(
        "UPDATE monitors SET reload=1,updated_at=? WHERE id=?", (int(time.time()), mid)
    )
    conn.commit()
    return cur.rowcount > 0


def set_dates(conn, mid, csv):
    cur = conn.execute(
        "UPDATE monitors SET dates=?,updated_at=? WHERE id=?",
        (csv, int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


def set_interval(conn, mid, minutes):
    cur = conn.execute(
        "UPDATE monitors SET interval_min=?,updated_at=? WHERE id=?",
        (minutes, int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


def set_time_window(conn, mid, s, e):
    cur = conn.execute(
        "UPDATE monitors SET time_start=?, time_end=?, updated_at=? WHERE id=?",
        (s, e, int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


def set_theatres(conn, mid, theatres):
    import json as _json

    cur = conn.execute(
        "UPDATE monitors SET theatres=?, updated_at=? WHERE id=?",
        (_json.dumps(theatres, ensure_ascii=False), int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


def set_mode(conn, mid, mode, rolling_days=0, end_date=None):
    cur = conn.execute(
        "UPDATE monitors SET mode=?, rolling_days=?, end_date=?, updated_at=? WHERE id=?",
        (mode, int(rolling_days or 0), end_date, int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


# Snooze helpers
def set_snooze(conn, mid: str, until_ts: int):
    cur = conn.execute(
        "UPDATE monitors SET snooze_until=?, updated_at=? WHERE id=?",
        (int(until_ts), int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


def clear_snooze(conn, mid: str):
    cur = conn.execute(
        "UPDATE monitors SET snooze_until=NULL, updated_at=? WHERE id=?",
        (int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


def get_indexed_theatres(conn, mid) -> List[str]:
    rows = conn.execute(
        "SELECT DISTINCT theatre FROM theatres_index WHERE monitor_id=? ORDER BY theatre COLLATE NOCASE",
        (mid,),
    ).fetchall()
    return [r["theatre"] for r in rows]


def upsert_indexed_theatre(conn, mid, date, theatre):
    conn.execute(
        """INSERT INTO theatres_index(monitor_id,date,theatre,last_seen_ts)
                    VALUES(?,?,?,?)
                    ON CONFLICT(monitor_id,date,theatre) DO UPDATE SET last_seen_ts=excluded.last_seen_ts""",
        (mid, date, theatre, int(time.time())),
    )
    conn.commit()


# UI session helpers
def get_ui_session(conn, chat_id: str, sid: str):
    row = conn.execute(
        "SELECT data_json FROM ui_sessions WHERE chat_id=? AND monitor_id=?",
        (str(chat_id), str(sid)),
    ).fetchone()
    import json as _json

    return _json.loads(row["data_json"]) if row else None


def set_ui_session(conn, chat_id: str, sid: str, data: dict):
    import json as _json

    now = int(time.time())
    conn.execute(
        """INSERT INTO ui_sessions(chat_id, monitor_id, data_json, updated_at)
           VALUES(?,?,?,?)
           ON CONFLICT(chat_id, monitor_id) DO UPDATE SET
             data_json=excluded.data_json, updated_at=excluded.updated_at""",
        (str(chat_id), str(sid), _json.dumps(data, ensure_ascii=False), now),
    )
    conn.commit()


def clear_ui_session(conn, chat_id: str, sid: str):
    conn.execute(
        "DELETE FROM ui_sessions WHERE chat_id=? AND monitor_id=?",
        (str(chat_id), str(sid)),
    )
    conn.commit()


# ---- New helpers for scheduler ----
def get_active_monitors(conn):
    return conn.execute(
        "SELECT * FROM monitors WHERE state IN ('RUNNING','DISCOVER')"
    ).fetchall()


def upsert_seen(
    conn, monitor_id: str, date: str, theatre: str, time_: str, first_seen_ts: int
):
    conn.execute(
        """INSERT INTO seen(monitor_id,date,theatre,time,first_seen_ts)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(monitor_id,date,theatre,time) DO NOTHING""",
        (monitor_id, date, theatre, time_, first_seen_ts),
    )
    conn.commit()


def bulk_upsert_seen(conn, rows):
    # rows: list of (monitor_id, date, theatre, time, ts)
    if not rows:
        return
    conn.executemany(
        """INSERT INTO seen(monitor_id,date,theatre,time,first_seen_ts)
                        VALUES(?,?,?,?,?)
                        ON CONFLICT(monitor_id,date,theatre,time) DO NOTHING""",
        rows,
    )
    conn.commit()


def is_seen(conn, monitor_id: str, date: str, theatre: str, time_: str) -> bool:
    r = conn.execute(
        "SELECT 1 FROM seen WHERE monitor_id=? AND date=? AND theatre=? AND time=?",
        (monitor_id, date, theatre, time_),
    ).fetchone()
    return bool(r)


def set_baseline_done(conn, mid: str):
    cur = conn.execute(
        "UPDATE monitors SET baseline=0, updated_at=? WHERE id=?",
        (int(time.time()), mid),
    )
    conn.commit()
    return cur.rowcount > 0


# Deletion
def delete_monitor(conn, mid: str):
    conn.execute("DELETE FROM seen WHERE monitor_id=?", (mid,))
    conn.execute("DELETE FROM theatres_index WHERE monitor_id=?", (mid,))
    conn.execute("DELETE FROM snapshots WHERE monitor_id=?", (mid,))
    conn.execute("DELETE FROM runs WHERE monitor_id=?", (mid,))
    cur = conn.execute("DELETE FROM monitors WHERE id=?", (mid,))
    conn.commit()
    return cur.rowcount > 0
