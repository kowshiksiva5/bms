from typing import List, Optional, Tuple
import re
import os
from config import get_chrome_binary
from dataclasses import asdict
from functools import lru_cache
import time as pytime
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from models import Movie, Theatre

import random

def _jitter(min_s=0.8, max_s=1.6):
    pytime.sleep(random.uniform(min_s, max_s))

def _ua_override(driver)
            driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Kolkata'}):
    try:
        # Let Chrome decide major version; just set a sane UA override without Headless token
        ua = driver.execute_script("return navigator.userAgent") or ""
        if "Headless" in ua:
            ua = ua.replace("Headless", "")
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": ua.strip(),
            "platform": "Win32",
            "acceptLanguage": "en-US,en"
        })
    except Exception:
        pass

def _recover_oops_page(driver, url: str, attempts: int = 3) -> None:
    for i in range(attempts):
        try:
            page = (driver.page_source or "").lower()
        except Exception:
            page = ""
        if "oops! something went wrong" in page or "refresh page" in page:
            _save_debug_artifacts(driver, prefix="bms_oops")
            try:
                driver.execute_script("location.reload(true)")
            except Exception:
                try:
                    driver.get(url)
                except Exception:
                    pass
            _jitter(2.0, 3.5)
            _handle_popups_and_cookies(driver)
            _jitter()
        else:
            return


def _save_debug_artifacts(driver, prefix: str = "bms_debug"):
    try:
        ts = int(pytime.time())
        html_path = f"/mnt/data/{prefix}_{ts}.html"
        png_path = f"/mnt/data/{prefix}_{ts}.png"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        try:
            driver.save_screenshot(png_path)
        except Exception:
            png_path = None
        print(f"[debug] Saved page snapshot: {html_path}" + (f", {png_path}" if png_path else ""))
    except Exception:
        pass


def _inject_stealth(driver):
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            """
        })
    except Exception:
        pass

def _recover_blank_page(driver, url: str, attempts: int = 3) -> None:
    for i in range(attempts):
        try:
            inner_len = driver.execute_script("return (document.body && document.body.innerText) ? document.body.innerText.length : 0;")
        except Exception:
            inner_len = 0
        src_len = len(driver.page_source or "")
        if inner_len > 200 or src_len > 5000:
            return
        pytime.sleep(2)
        try:
            driver.get(url)
        except Exception:
            pass
        pytime.sleep(3)
    # Final refresh
    try:
        driver.refresh()
        pytime.sleep(2)
    except Exception:
        pass





def _get_selenium_driver(debug: bool = False) -> Optional[webdriver.Chrome]:
    options = Options()
    chrome_binary = get_chrome_binary()
    if chrome_binary:
        options.binary_location = chrome_binary
    if not debug:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1366,768')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-features=IsolateOrigins,site-per-process,TranslateUI')
    options.page_load_strategy = 'eager'
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("prefs", {
        "intl.accept_languages": "en-US,en",
        "profile.default_content_setting_values.geolocation": 1,
    })
    use_uc = os.environ.get("BMS_FORCE_UC", "0") == "1"
    if use_uc:
        try:
            import undetected_chromedriver as uc
            driver = uc.Chrome(options=options, headless=(not debug))
            driver.set_page_load_timeout(60)
            _inject_stealth(driver); _ua_override(driver)
            driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Kolkata'})
            return driver
        except Exception as e2:
            print(f"Failed to create undetected Chrome driver: {e2}")
    try:
        driver = webdriver.Chrome(options=options)
        _inject_stealth(driver); _ua_override(driver)
            driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Kolkata'})
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        print(f"Failed to create Chrome driver (std): {e}")
        try:
            import undetected_chromedriver as uc
            driver = uc.Chrome(options=options, headless=(not debug))
            driver.set_page_load_timeout(60)
            _inject_stealth(driver); _ua_override(driver)
            driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Kolkata'})
            return driver
        except Exception as e2:
            print(f"Failed to create undetected Chrome driver: {e2}")
            return None


def _handle_popups_and_cookies(driver: webdriver.Chrome) -> None:
    popup_selectors = [
        '[id*="wzrk-cancel"]',
        '[id*="wzrk-close"]',
        '.modal-close',
        '.popup-close',
        '[data-testid="close-button"]',
        '.cookie-banner button',
        '.gdpr-banner button'
    ]
    for selector in popup_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if element.is_displayed():
                    element.click()
                    pytime.sleep(0.5)
        except Exception:
            continue

    # Try confirm/continue buttons that sometimes block UI
    try:
        ctas = driver.find_elements(By.XPATH, "//button[normalize-space()='Continue' or contains(translate(., 'ALLOW', 'allow'), 'allow') or contains(translate(., 'OK', 'ok'), 'ok')] | //a[contains(., 'Continue')]")
        for c in ctas:
            if c.is_displayed():
                c.click()
                pytime.sleep(0.5)
                break
    except Exception:
        pass


def _ensure_buytickets_page(driver: webdriver.Chrome) -> None:
    """If currently on a generic movie page, try navigating to the buytickets/showtimes page."""
    try:
        current = driver.current_url
        # If already on buytickets, nothing to do
        if '/buytickets/' in current:
            return
        # Try clicking a "Book" or "Buy" CTA
        cta_candidates = driver.find_elements(By.XPATH,
            "//a[contains(translate(., 'BOOK', 'book'), 'book') or contains(translate(., 'BUY', 'buy'), 'buy') or contains(., 'Tickets')] | "
            "//button[contains(translate(., 'BOOK', 'book'), 'book') or contains(translate(., 'BUY', 'buy'), 'buy') or contains(., 'Tickets')]"
        )
        for el in cta_candidates:
            try:
                if el.is_displayed() and el.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    el.click()
                    pytime.sleep(2)
                    if '/buytickets/' in driver.current_url:
                        return
            except Exception:
                continue

        # Fallback: click any anchor that links to buytickets
        links = driver.find_elements(By.XPATH, "//a[contains(@href, '/buytickets/')]")
        for a in links:
            href = a.get_attribute('href')
            if href:
                driver.get(href)
                pytime.sleep(2)
                if '/buytickets/' in driver.current_url:
                    return

        # Last resort: try to derive buytickets from ET code on page
        page = driver.page_source or ''
        m = re.search(r'(ET\d{5,})', page)
        if m:
            code = m.group(1)
            # Navigate to a generic buytickets URL; BMS will usually redirect correctly
            driver.get(f"https://in.bookmyshow.com/buytickets/{code}")
            pytime.sleep(2)
            return
    except Exception:
        return


def get_available_movies(city_slug: str = "hyderabad", debug: bool = False) -> List[Movie]:
    url = f"https://in.bookmyshow.com/explore/movies-{city_slug}"
    driver = _get_selenium_driver(debug)
    if not driver:
        return []
    
    movies: List[Movie] = []
    try:
        driver.get(url)
        _recover_blank_page(driver, url)
        _handle_popups_and_cookies(driver)
        _recover_oops_page(driver, url)
        pytime.sleep(3)
        selectors = [
            'div[data-testid="event-card"]',
            '[data-testid="movie-card"]',
            '.movie-card',
            '.event-card',
            'a[href*="/movies/"]'
        ]
        for selector in selectors:
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, selector)
                if not cards:
                    continue
                for card in cards[:40]:
                    try:
                        name = None
                        link = None
                        imgs = card.find_elements(By.TAG_NAME, 'img')
                        if imgs:
                            name = imgs[0].get_attribute('alt')
                        if not name:
                            heads = card.find_elements(By.CSS_SELECTOR, 'h3, h4, .title, .name')
                            if heads:
                                name = heads[0].text.strip()
                        anchors = card.find_elements(By.TAG_NAME, 'a')
                        if anchors:
                            link = anchors[0].get_attribute('href')
                        if name and link and '/movies/' in link:
                            movies.append(Movie(name=name.strip(), url=link))
                    except Exception:
                        continue
                if movies:
                    break
            except Exception:
                continue
        if not movies:
            # fallback parsing
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            links = soup.find_all('a', href=lambda x: x and '/movies/' in x)
            for a in links[:40]:
                text = a.get_text(strip=True)
                if text:
                    movies.append(Movie(name=text, url=a['href']))
        return movies
    finally:
        driver.quit()


def _try_select_date(driver: webdriver.Chrome, target_date: str) -> None:
    if not target_date:
        return
    try:
        # Common selectors that may hold date controls
        candidates = []
        candidates.extend(driver.find_elements(By.CSS_SELECTOR, '[data-date]'))
        candidates.extend(driver.find_elements(By.CSS_SELECTOR, 'button[data-testid*="date"], [data-testid*="date"] button, [role="tablist"] button'))
        candidates.extend(driver.find_elements(By.CSS_SELECTOR, 'li[role="tab"], button[role="tab"]'))
        # First, look for exact data-date match (YYYY-MM-DD)
        for el in candidates:
            try:
                data_date = el.get_attribute('data-date')
                if data_date and data_date.strip() == target_date:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    el.click()
                    pytime.sleep(2)
                    return
            except Exception:
                continue
        # Fallback: click by visible text contains day or month string
        for el in candidates:
            try:
                txt = el.text.strip()
                if not txt:
                    continue
                # crude match: check if target yyyy-mm-dd contains day and month digits
                parts = target_date.split('-')
                if len(parts) == 3 and (parts[2].lstrip('0') in txt or parts[1].lstrip('0') in txt):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    el.click()
                    pytime.sleep(2)
                    return
            except Exception:
                continue
    except Exception:
        return


def get_theatres_and_showtimes(movie_url: str, date_str: Optional[str] = None, debug: bool = False) -> List[Theatre]:
    driver = _get_selenium_driver(debug)
    if not driver:
        return []
    theatres: List[Theatre] = []
    try:
        driver.get(movie_url)
        _recover_blank_page(driver, movie_url)
        _handle_popups_and_cookies(driver)
        _recover_oops_page(driver, url)
        pytime.sleep(3)
        _ensure_buytickets_page(driver)
        # If a date was specified, try to select it
        if date_str:
            _try_select_date(driver, date_str)
        # Try multiple scrolls to trigger lazy load
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            pytime.sleep(1.0)
        selectors = [
            'div[data-testid="venue-card"]',
            '[data-testid="venue-card"]',
            '.venue-card',
            '.theatre-card',
            '[class*="venue"]',
            '[class*="theatre"]'
        ]
        for selector in selectors:
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, selector)
                if not cards:
                    continue
                for card in cards:
                    try:
                        name = None
                        for name_sel in ['a[data-venue-code]', 'a', 'h3', 'h4', '.venue-name', '.theatre-name', '[class*="name"]']:
                            try:
                                el = card.find_element(By.CSS_SELECTOR, name_sel)
                                text = el.text.strip()
                                if text:
                                    name = text
                                    break
                            except Exception:
                                continue
                        if not name:
                            continue
                        showtimes: List[str] = []
                        for st_sel in ['button[data-testid="showtime-pill"]', '[data-testid="showtime-pill"]', '.showtime-pill', '.showtime', 'button[class*="showtime"]', 'span[class*="time"]']:
                            try:
                                elements = card.find_elements(By.CSS_SELECTOR, st_sel)
                                for e in elements:
                                    t = e.text.strip()
                                    if t:
                                        showtimes.append(t)
                                if showtimes:
                                    break
                            except Exception:
                                continue
                        lat, lon = cached_geocode(name)
                        theatres.append(Theatre(name=name, lat=lat, lon=lon, showtimes=showtimes))
                    except Exception:
                        continue
                if theatres:
                    break
            except Exception:
                continue
        if not theatres:
            _save_debug_artifacts(driver, prefix='bms_no_theatres')
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            candidates = soup.find_all(['h3', 'h4', 'a'], string=lambda x: x and any(w in x.lower() for w in ['cinema', 'theatre', 'multiplex']))
            for el in candidates:
                text = el.get_text(strip=True)
                if text and len(text) > 3:
                    lat, lon = cached_geocode(text)
                    theatres.append(Theatre(name=text, lat=lat, lon=lon, showtimes=[]))
        return theatres
    finally:
        driver.quit()


def geocode_place(place: str, city: Optional[str] = None) -> Tuple[Optional[float], Optional[float]]:
    try:
        url = "https://nominatim.openstreetmap.org/search"
        q = f"{place}, {city}" if city else place
        params = {"q": q, "format": "json", "limit": 1}
        headers = {"User-Agent": "bms-scraper/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocoding failed for {place}: {e}")
    return None, None


@lru_cache(maxsize=128)
def cached_geocode(theatre_name: str) -> Tuple[Optional[float], Optional[float]]:
    return geocode_place(theatre_name)


def get_showtimes_for_theatre(movie_name: str, theatre_name: str, city_slug: str = "hyderabad") -> List[str]:
    movies = get_available_movies(city_slug=city_slug)
    movie_url = None
    for m in movies:
        if movie_name.lower() in m.name.lower():
            movie_url = m.url
            break
    if not movie_url:
        return []
    theatres = get_theatres_and_showtimes(movie_url, debug=False)
    for t in theatres:
        if theatre_name.lower() in t.name.lower():
            return t.showtimes
    return []


