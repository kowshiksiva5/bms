from __future__ import annotations
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text

Base = declarative_base()

class Monitor(Base):
    __tablename__ = 'monitors'
    id = Column(String, primary_key=True)
    url = Column(Text, nullable=False)
    dates = Column(Text, nullable=False)
    theatres = Column(Text, nullable=False)
    interval_min = Column(Integer, nullable=False)
    baseline = Column(Integer, nullable=False)
    state = Column(Text, nullable=False)
    snooze_until = Column(Integer)
    owner_chat_id = Column(Text)
    mode = Column(Text, default='FIXED')
    rolling_days = Column(Integer, default=0)
    end_date = Column(Text)
    time_start = Column(Text)
    time_end = Column(Text)
    heartbeat_minutes = Column(Integer, default=180)
    created_at = Column(Integer)
    updated_at = Column(Integer)
    last_run_ts = Column(Integer)
    last_alert_ts = Column(Integer)
    reload = Column(Integer, default=0)

class Seen(Base):
    __tablename__ = 'seen'
    monitor_id = Column(String, primary_key=True)
    date = Column(String, primary_key=True)
    theatre = Column(String, primary_key=True)
    time = Column(String, primary_key=True)
    first_seen_ts = Column(Integer)

class TheatreIndex(Base):
    __tablename__ = 'theatres_index'
    monitor_id = Column(String, primary_key=True)
    date = Column(String, primary_key=True)
    theatre = Column(String, primary_key=True)
    last_seen_ts = Column(Integer)

class Run(Base):
    __tablename__ = 'runs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    monitor_id = Column(String, nullable=False)
    started_ts = Column(Integer)
    finished_ts = Column(Integer)
    status = Column(Text)
    error = Column(Text)

class Snapshot(Base):
    __tablename__ = 'snapshots'
    monitor_id = Column(String, primary_key=True)
    date = Column(String, primary_key=True)
    theatre = Column(String, primary_key=True)
    times_json = Column(Text, nullable=False)
    updated_at = Column(Integer)

class Daily(Base):
    __tablename__ = 'daily'
    chat_id = Column(String, primary_key=True)
    hhmm = Column(String, nullable=False)
    enabled = Column(Integer, nullable=False, default=0)
    last_sent_ts = Column(Integer)

class UISession(Base):
    __tablename__ = 'ui_sessions'
    chat_id = Column(String, primary_key=True)
    monitor_id = Column(String, primary_key=True)
    data_json = Column(Text, nullable=False)
    updated_at = Column(Integer, nullable=False)
