import re
from datetime import datetime

import common


def test_norm_and_fuzzy():
    assert common.norm("Hello, World!") == "helloworld"
    assert common.fuzzy("PVR Koramangala", ["koramangala"])
    assert not common.fuzzy("ABC", ["DEF"])


def test_date_helpers():
    assert common.to_bms_date("2024-01-02") == "20240102"
    assert common.to_bms_date("1/2/2024") is None
    url = common.ensure_date_in_url("http://x/y", "20240102")
    assert url.endswith("/20240102")


def test_roll_and_time_window():
    dates = common.roll_dates(3)
    assert len(dates) == 3
    assert all(re.fullmatch(r"\d{8}", d) for d in dates)
    ts = int(datetime(2024, 1, 1, 12, 30).timestamp())
    assert common.within_time_window(ts, "10:00", "13:00")
    assert not common.within_time_window(ts, "13:00", "14:00")
