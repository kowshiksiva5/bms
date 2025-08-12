#!/usr/bin/env python3
from __future__ import annotations
import os, time, json
from typing import List
from sqlalchemy import create_engine, select, update, delete
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL as DB_URL
from db import Base, Monitor, Seen, TheatreIndex, Run, Snapshot, Daily, UISession


def _ensure_dir_from_url(url: str):
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)

_ensure_dir_from_url(DB_URL)
_engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)
Base.metadata.create_all(_engine)
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def connect():
    return SessionLocal()


def _to_dict(obj):
    if obj is None:
        return None
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def list_monitors(sess, chat_id: str = None):
    q = select(Monitor)
    if chat_id:
        q = q.where(Monitor.owner_chat_id == chat_id)
    q = q.order_by(Monitor.created_at.desc())
    rows = sess.execute(q).scalars().all()
    return [_to_dict(r) for r in rows]


def get_monitor(sess, mid):
    r = sess.get(Monitor, mid)
    return _to_dict(r)


def set_state(sess, mid, state):
    res = sess.execute(
        update(Monitor).where(Monitor.id == mid).values(state=state, updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def set_reload(sess, mid):
    res = sess.execute(
        update(Monitor).where(Monitor.id == mid).values(reload=1, updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def set_dates(sess, mid, csv):
    res = sess.execute(
        update(Monitor).where(Monitor.id == mid).values(dates=csv, updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def set_interval(sess, mid, minutes):
    res = sess.execute(
        update(Monitor).where(Monitor.id == mid).values(interval_min=minutes, updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def set_time_window(sess, mid, s, e):
    res = sess.execute(
        update(Monitor)
        .where(Monitor.id == mid)
        .values(time_start=s, time_end=e, updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def set_theatres(sess, mid, theatres):
    res = sess.execute(
        update(Monitor)
        .where(Monitor.id == mid)
        .values(theatres=json.dumps(theatres, ensure_ascii=False), updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def set_mode(sess, mid, mode, rolling_days=0, end_date=None):
    res = sess.execute(
        update(Monitor)
        .where(Monitor.id == mid)
        .values(
            mode=mode,
            rolling_days=int(rolling_days or 0),
            end_date=end_date,
            updated_at=int(time.time()),
        )
    )
    sess.commit()
    return res.rowcount > 0


def set_snooze(sess, mid: str, until_ts: int):
    res = sess.execute(
        update(Monitor)
        .where(Monitor.id == mid)
        .values(snooze_until=int(until_ts), updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def clear_snooze(sess, mid: str):
    res = sess.execute(
        update(Monitor)
        .where(Monitor.id == mid)
        .values(snooze_until=None, updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def get_indexed_theatres(sess, mid) -> List[str]:
    rows = sess.execute(
        select(TheatreIndex.theatre).where(TheatreIndex.monitor_id == mid).order_by(TheatreIndex.theatre)
    ).scalars().all()
    return rows


def upsert_indexed_theatre(sess, mid, date, theatre):
    sess.merge(
        TheatreIndex(
            monitor_id=mid,
            date=date,
            theatre=theatre,
            last_seen_ts=int(time.time()),
        )
    )
    sess.commit()


def get_ui_session(sess, chat_id: str, sid: str):
    row = sess.get(UISession, {"chat_id": str(chat_id), "monitor_id": str(sid)})
    return json.loads(row.data_json) if row else None


def set_ui_session(sess, chat_id: str, sid: str, data: dict):
    now = int(time.time())
    sess.merge(
        UISession(
            chat_id=str(chat_id),
            monitor_id=str(sid),
            data_json=json.dumps(data, ensure_ascii=False),
            updated_at=now,
        )
    )
    sess.commit()


def clear_ui_session(sess, chat_id: str, sid: str):
    sess.execute(
        delete(UISession).where(UISession.chat_id == str(chat_id), UISession.monitor_id == str(sid))
    )
    sess.commit()


def get_active_monitors(sess):
    rows = sess.execute(
        select(Monitor).where(Monitor.state.in_(["RUNNING", "DISCOVER"]))
    ).scalars().all()
    return [_to_dict(r) for r in rows]


def upsert_seen(sess, monitor_id: str, date: str, theatre: str, time_: str, first_seen_ts: int):
    sess.merge(
        Seen(
            monitor_id=monitor_id,
            date=date,
            theatre=theatre,
            time=time_,
            first_seen_ts=first_seen_ts,
        )
    )
    sess.commit()


def bulk_upsert_seen(sess, rows):
    if not rows:
        return
    for r in rows:
        sess.merge(
            Seen(
                monitor_id=r[0],
                date=r[1],
                theatre=r[2],
                time=r[3],
                first_seen_ts=r[4],
            )
        )
    sess.commit()


def is_seen(sess, monitor_id: str, date: str, theatre: str, time_: str) -> bool:
    r = sess.execute(
        select(Seen)
        .where(
            Seen.monitor_id == monitor_id,
            Seen.date == date,
            Seen.theatre == theatre,
            Seen.time == time_,
        )
    ).first()
    return bool(r)


def set_baseline_done(sess, mid: str):
    res = sess.execute(
        update(Monitor).where(Monitor.id == mid).values(baseline=0, updated_at=int(time.time()))
    )
    sess.commit()
    return res.rowcount > 0


def delete_monitor(sess, mid: str):
    sess.execute(delete(Seen).where(Seen.monitor_id == mid))
    sess.execute(delete(TheatreIndex).where(TheatreIndex.monitor_id == mid))
    sess.execute(delete(Snapshot).where(Snapshot.monitor_id == mid))
    sess.execute(delete(Run).where(Run.monitor_id == mid))
    res = sess.execute(delete(Monitor).where(Monitor.id == mid))
    sess.commit()
    return res.rowcount > 0
