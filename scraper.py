#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, random, tempfile, subprocess, json
from typing import List, Tuple, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ---------- trace / artifacts ----------
_TRACE = False
_ARTIFACTS_DIR: Optional[str] = None

def set_trace(enabled: bool, artifacts_dir: Optional[str] = None):
    """Enable verbose trace and saving HTML/PNG snapshots to artifacts_dir."""
    global _TRACE, _ARTIFACTS_DIR
    _TRACE = bool(enabled)
    _ARTIFACTS_DIR = artifacts_dir
    if _ARTIFACTS_DIR and not os.path.isdir(_ARTIFACTS_DIR):
        os.makedirs(_ARTIFACTS_DIR, exist_ok=True)

def _dbg(msg: str):
    if _TRACE:
        print(f"[trace] {msg}", flush=True)

def _save_artifacts(driver, label: str):
    if not (_TRACE and _ARTIFACTS_DIR):
        return
    ts = int(time.time())
    html = os.path.join(_ARTIFACTS_DIR, f"{ts}_{label}.html")
    png  = os.path.join(_ARTIFACTS_DIR, f"{ts}_{label}.png")
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source or "")
    except Exception:
        pass
    try:
        driver.save_screenshot(png)
    except Exception:
        pass
    _dbg(f"saved artifacts: {html}, {png}")

# ---------- Chrome discovery ----------
def get_chrome_binary() -> Optional[str]:
    for k in ("CHROME_BINARY", "CHROMIUM_BINARY"):
        if os.environ.get(k):
            return os.environ[k]
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    linux = "/usr/bin/google-chrome"
    if os.path.exists(mac): return mac
    if os.path.exists(linux): return linux
    return None

def _chrome_major_from_binary(path: str) -> Optional[int]:
    try:
        out = subprocess.check_output([path, "--version"]).decode().strip()
        m = re.search(r"(\d+)\.", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None

# ---------- Stealth helpers ----------
def _inject_stealth(driver):
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": r"""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
""" })
    except Exception:
        pass

def _ua_override(driver):
    try:
        ua = driver.execute_script("return navigator.userAgent") or ""
        if "Headless" in ua: ua = ua.replace("Headless", "")
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": ua.strip(), "platform": "Win32", "acceptLanguage": "en-US,en"
        })
        try:
            driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "Asia/Kolkata"})
        except Exception:
            pass
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setExtraHTTPHeaders",
                                   {"headers": {"Referer": "https://in.bookmyshow.com/"}})
        except Exception:
            pass
    except Exception:
        pass

def _is_cloudflare_block(driver) -> bool:
    try:
        t = (driver.title or "").lower()
        b = (driver.page_source or "").lower()
    except Exception:
        return False
    return ("attention required | cloudflare" in t) or ("sorry, you have been blocked" in b)

def _recover_blank_or_oops(driver, url: str):
    try:
        body_len = driver.execute_script(
            "return (document.body && document.body.innerText) ? document.body.innerText.length : 0;")
    except Exception:
        body_len = 0
    src_len = len(driver.page_source or "")
    page = (driver.page_source or "").lower()
    if (body_len < 200 and src_len < 5000) or ("oops! something went wrong" in page):
        _dbg("blank/oops detected; reloading")
        try:
            driver.execute_script("location.reload(true)"); time.sleep(2.5)
        except Exception:
            try:
                driver.get(url); time.sleep(2)
            except Exception:
                pass
        _save_artifacts(driver, "after_reload")

# ---------- Driver factory ----------
def get_driver(debug: bool = False):
    """Try Selenium first (unless BMS_FORCE_UC=1), then undetected-chromedriver (pinned)."""
    def build_args():
        args = []
        if not debug: args.append("--headless=new")
        args += [
            "--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
            "--window-size=1366,768","--disable-blink-features=AutomationControlled",
            f"--remote-debugging-port={random.randint(9223,9555)}",
            "--no-first-run","--no-default-browser-check",
        ]
        udd = os.environ.get("BMS_USER_DATA_DIR") or tempfile.mkdtemp(prefix="bms-chrome-")
        prof = os.environ.get("BMS_PROFILE_DIR","Default")
        args.append(f"--user-data-dir={udd}"); args.append(f"--profile-directory={prof}")
        return args

    chrome_binary = get_chrome_binary()
    _dbg(f"chrome_binary={chrome_binary}")
    force_uc = os.environ.get("BMS_FORCE_UC","1") == "1"
    _dbg(f"force_uc={force_uc}")

    if not force_uc:
        try:
            opts = Options()
            if chrome_binary: opts.binary_location = chrome_binary
            for a in build_args(): opts.add_argument(a)
            opts.page_load_strategy = "eager"
            opts.add_experimental_option("prefs", {
                "intl.accept_languages": "en-US,en",
                "profile.default_content_setting_values.geolocation": 1,
            })
            d = webdriver.Chrome(options=opts); d.set_page_load_timeout(60)
            _inject_stealth(d); _ua_override(d)
            _dbg("selenium driver OK")
            return d
        except Exception as e:
            print(f"[driver] Selenium failed: {e}")

    try:
        import undetected_chromedriver as uc
        uc_opts = uc.ChromeOptions()
        if chrome_binary: uc_opts.binary_location = chrome_binary
        for a in build_args(): uc_opts.add_argument(a)
        major = _chrome_major_from_binary(chrome_binary) if chrome_binary else None
        env_major = os.environ.get("BMS_CHROME_VERSION_MAIN")
        if not major and env_major and env_major.isdigit(): major = int(env_major)
        _dbg(f"UC version_main={major}")
        d = uc.Chrome(options=uc_opts, headless=(not debug), version_main=major) if major else uc.Chrome(options=uc_opts, headless=(not debug))
        d.set_page_load_timeout(60); _inject_stealth(d); _ua_override(d)
        _dbg("UC driver OK")
        return d
    except Exception as e:
        print(f"[driver] UC failed: {e}")
        return None

# ---------- Navigation ----------
def open_and_prepare(driver, url: str):
    _dbg(f"open {url}")
    driver.get("about:blank"); driver.get(url); time.sleep(2)
    _save_artifacts(driver, "loaded")
    _recover_blank_or_oops(driver, url)
    if _is_cloudflare_block(driver):
        _dbg("cloudflare block detected: retry")
        time.sleep(2); driver.get(url); time.sleep(2)
        _save_artifacts(driver, "after_cf_retry")

def open_and_prepare_resilient(driver, url: str, debug: bool = False):
    """Open URL; if the session died, rebuild the driver and retry. Returns a (possibly new) driver."""
    try:
        open_and_prepare(driver, url)
        return driver
    except Exception as e:
        _dbg(f"driver.get failed ({e}); recreating driver")
        try:
            driver.quit()
        except Exception:
            pass
        d2 = get_driver(debug=debug)
        if not d2:
            raise
        open_and_prepare(d2, url)
        return d2

# ---------- Parsing ----------
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s?(AM|PM)\b", re.I)

def _parse_venues_from_json(html: str) -> List[Tuple[str, List[str]]]:
    """Extract venues from embedded JSON fragments with type:'venue-card'."""
    theatres: List[Tuple[str, List[str]]] = []
    anchor = '"type":"venue-card"'
    i = 0
    while True:
        i = html.find(anchor, i)
        if i == -1:
            break
        start = html.rfind("{", 0, i)
        if start == -1:
            i += len(anchor); continue
        depth = 0; j = start; in_str = False; esc = False
        while j < len(html):
            ch = html[j]
            if in_str:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': in_str = False
            else:
                if ch == '"': in_str = True
                elif ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0: break
            j += 1
        if depth != 0:
            i += len(anchor); continue
        frag = html[start:j+1]
        try:
            obj = json.loads(frag)
            name = obj.get("additionalData", {}).get("venueName")
            shows: List[str] = []
            for st in obj.get("showtimes", []) or []:
                t = (st.get("title") or "").strip()
                if t and _TIME_RE.search(t):
                    shows.append(t)
            if name:
                theatres.append((name, shows))
        except Exception:
            pass
        i = j + 1
    return theatres

def _parse_venues_from_dom(html: str) -> List[Tuple[str, List[str]]]:
    """Fallback: scan visible rows and pull theatre name + showtime tokens."""
    theatres: List[Tuple[str, List[str]]] = []
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select('.ReactVirtualized__Grid__innerScrollContainer > div') or soup.find_all("div")
    for row in rows:
        text = row.get_text(" ", strip=True)
        times_full = [m.group(0) for m in _TIME_RE.finditer(text)]
        if not times_full:
            continue
        name_el = None
        for sel in ["h3", "h4", "a", "span"]:
            cand = row.select_one(sel)
            if cand and len(cand.get_text(strip=True)) >= 6:
                name_el = cand; break
        name = name_el.get_text(strip=True) if name_el else None
        if name and "AM" not in name and "PM" not in name and len(name) > 5:
            theatres.append((name, times_full))
    # dedupe by name
    out: dict[str, List[str]] = {}
    for n, ts in theatres:
        out.setdefault(n, [])
        for t in ts:
            if t not in out[n]:
                out[n].append(t)
    return [(n, out[n]) for n in out]

def parse_theatres(driver) -> List[Tuple[str, List[str]]]:
    html = driver.page_source or ""
    theatres = _parse_venues_from_json(html)
    if not theatres or any(len(ts) == 0 for _, ts in theatres):
        dom = _parse_venues_from_dom(html)
        if theatres:
            dom_map = {n: ts for n, ts in dom}
            theatres = [(n, dom_map.get(n, ts) or ts) for n, ts in theatres]
        else:
            theatres = dom
    _dbg(f"parsed theatres: {len(theatres)}")
    return theatres
