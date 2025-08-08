#!/usr/bin/env python3
from __future__ import annotations
import os, re, time, random, tempfile, subprocess
from typing import List, Tuple, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ----------------- Chrome discovery -----------------
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

# ----------------- Stealth helpers ------------------
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
            driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"Referer": "https://in.bookmyshow.com/"}})
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
        body_len = driver.execute_script("return (document.body && document.body.innerText) ? document.body.innerText.length : 0;")
    except Exception:
        body_len = 0
    src_len = len(driver.page_source or "")
    page = (driver.page_source or "").lower()
    if body_len < 200 and src_len < 5000 or "oops! something went wrong" in page:
        try:
            driver.execute_script("location.reload(true)"); time.sleep(2.5)
        except Exception:
            try:
                driver.get(url); time.sleep(2)
            except Exception:
                pass

# ----------------- Driver factory -------------------
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
    force_uc = os.environ.get("BMS_FORCE_UC","1") == "1"
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
            _inject_stealth(d); _ua_override(d); return d
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
        d = uc.Chrome(options=uc_opts, headless=(not debug), version_main=major) if major else uc.Chrome(options=uc_opts, headless=(not debug))
        d.set_page_load_timeout(60); _inject_stealth(d); _ua_override(d); return d
    except Exception as e:
        print(f"[driver] UC failed: {e}"); return None

# ----------------- Navigation & parsing --------------
def open_and_prepare(driver, url: str):
    driver.get("about:blank"); driver.get(url); time.sleep(2)
    _recover_blank_or_oops(driver, url)
    if _is_cloudflare_block(driver):
        time.sleep(2); driver.get(url); time.sleep(2)

def parse_theatres(driver) -> List[Tuple[str, List[str]]]:
    theatres: List[Tuple[str, List[str]]] = []
    selectors = [
        'div[data-testid="venue-card"]','[data-testid="venue-card"]','.venue-card','.theatre-card',
        '[class*="venue"]','[class*="theatre"]'
    ]
    for sel in selectors:
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            for card in cards:
                name = None
                for name_sel in ['a[data-venue-code]', 'a', 'h3', 'h4', '.venue-name', '.theatre-name', '[class*="name"]']:
                    try:
                        el = card.find_element(By.CSS_SELECTOR, name_sel)
                        t = el.text.strip()
                        if t: name = t; break
                    except Exception: pass
                if not name: continue
                shows: List[str] = []
                for st_sel in ['button[data-testid="showtime-pill"]','[data-testid="showtime-pill"]','.showtime-pill','.showtime','button[class*="showtime"]','span[class*="time"]']:
                    try:
                        for e in card.find_elements(By.CSS_SELECTOR, st_sel):
                            t = e.text.strip()
                            if t: shows.append(t)
                        if shows: break
                    except Exception: pass
                theatres.append((name, shows))
            if theatres: break
        except Exception: pass
    if not theatres:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        candidates = soup.find_all(['h3','h4','a'], string=lambda x: x and any(w in x.lower() for w in ['cinema','theatre','multiplex']))
        for el in candidates:
            t = el.get_text(strip=True)
            if t and len(t)>3: theatres.append((t, []))
    return theatres
