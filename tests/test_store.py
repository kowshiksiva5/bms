import json

import pytest

import store


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    db = tmp_path / "state.db"
    monkeypatch.setattr(store, "STATE_DB", str(db))
    connection = store.connect()
    yield connection
    connection.close()


def _insert_monitor(conn):
    conn.execute(
        "INSERT INTO monitors(id,url,dates,theatres,interval_min,baseline,state) VALUES (?,?,?,?,?,?,?)",
        ("m1", "http://example", "20240101", json.dumps([]), 5, 1, "RUNNING"),
    )
    conn.commit()


def test_monitor_crud(conn):
    _insert_monitor(conn)
    rows = store.list_monitors(conn)
    assert len(rows) == 1
    row = store.get_monitor(conn, "m1")
    assert row["url"] == "http://example"
    store.set_state(conn, "m1", "PAUSED")
    store.set_snooze(conn, "m1", 123)
    row = store.get_monitor(conn, "m1")
    assert row["state"] == "PAUSED"
    assert row["snooze_until"] == 123
    store.clear_snooze(conn, "m1")
    store.set_baseline_done(conn, "m1")
    row = store.get_monitor(conn, "m1")
    assert row["baseline"] == 0
    assert row["snooze_until"] is None


def test_seen_helpers(conn):
    _insert_monitor(conn)
    store.upsert_seen(conn, "m1", "20240101", "T1", "10:00 AM", 1)
    assert store.is_seen(conn, "m1", "20240101", "T1", "10:00 AM")
    store.bulk_upsert_seen(conn, [("m1", "20240101", "T1", "11:00 AM", 2)])
    assert store.is_seen(conn, "m1", "20240101", "T1", "11:00 AM")
