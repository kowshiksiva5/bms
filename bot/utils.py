import json
import os
import time
from typing import Any

DEFAULT_THEATRES = [
    "AMB Cinemas: Gachibowli",
    "Bhramaramba 70MM A/C 4K Dolby: Kukatpally",
    "Cinepolis: Lulu Mall, Hyderabad",
    "INOX: GSM Mall, Hyderabad",
    "Miraj Cinemas: CineTown, Miyapur",
    "Miraj Cinemas: Geeta, Chandanagar",
    "PVR ICON: Hitech, Madhapur, Hyderabad",
    "PVR: Atrium Gachibowli, Hyderabad",
    "INOX: Prism Mall, Hyderabad",
    "PVR: Inorbit, Cyberabad",
    "PVR: Nexus Mall Kukatpally, Hyderabad",
    "PVR: Preston, Gachibowli Hyderabad",
    "INOX: SMR Vinay Metro Mall, Hyderabad",
    "GPR Multiplex: Nizampet, Hyderabad",
]


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _eta(row: Any) -> str:
    now = int(time.time())
    eta = "—"
    if row and row.get("last_run_ts"):
        left = int(row["last_run_ts"]) + int(row["interval_min"]) * 60 - now
        if left > 0:
            eta = f"{left//60}m {left%60}s"
    return eta


def monitor_summary(r: Any) -> str:
    th = len(json.loads(r["theatres"]) if r["theatres"] else [])
    return (
        f"[{r['id']}] {r['state']} • every {r['interval_min']}m • next ~ {_eta(r)}\n"
        f"Dates: {r['dates']}  |  Theatres: {th}  |  Window: {(r['time_start'] or '—')}–{(r['time_end'] or '—')}\n"
        f"Mode: {r['mode'] or 'FIXED'} | Rolling: {r['rolling_days']} | Until: {r['end_date'] or '—'}\n"
        f"Last run: {_fmt_ts(r['last_run_ts'])}  |  Last alert: {_fmt_ts(r['last_alert_ts'])}\n"
        f"URL: {r['url']}"
    )


def discover_theatre_names(url: str, d8: str) -> list[str]:
    try:
        from services.driver_manager import DriverManager
        from scraper import parse_theatres
        from common import ensure_date_in_url

        dm = DriverManager(
            debug=False, trace=False, artifacts_dir=os.environ.get("ART_DIR", "./artifacts")
        )
        turl = ensure_date_in_url(url, d8)
        d = dm.open(turl)
        pairs = parse_theatres(d)
        names = sorted({n for n, _ in pairs})
        return names
    except Exception:
        return []
