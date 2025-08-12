from types import SimpleNamespace

import scraper


def test_parse_venues_from_json():
    html = (
        '<script>{"type":"venue-card","additionalData":{"venueName":"Cinema 1"},'
        '"showtimes":[{"title":"10:00 AM"},{"title":"1:00 PM"}]}</script>'
        '<script>{"type":"venue-card","additionalData":{"venueName":"Cinema 2"},'
        '"showtimes":[{"title":"2:00 PM"}]}</script>'
    )
    theatres = scraper._parse_venues_from_json(html)
    assert theatres == [
        ("Cinema 1", ["10:00 AM", "1:00 PM"]),
        ("Cinema 2", ["2:00 PM"]),
    ]


def test_parse_venues_from_dom():
    html = (
        '<div class="ReactVirtualized__Grid__innerScrollContainer">'
        "<div><h3>Cinema 1</h3><span>10:00 AM</span><span>1:00 PM</span></div>"
        "<div><h3>Cinema 2</h3><span>2:00 PM</span></div>"
        "</div>"
    )
    theatres = scraper._parse_venues_from_dom(html)
    assert ("Cinema 1", ["10:00 AM", "1:00 PM"]) in theatres
    assert ("Cinema 2", ["2:00 PM"]) in theatres


def test_parse_theatres_fallback():
    html = (
        '<script>{"type":"venue-card","additionalData":{"venueName":"Cinema 1"},"showtimes":[]}</script>'
        '<div class="ReactVirtualized__Grid__innerScrollContainer">'
        "<div><h3>Cinema 1</h3><span>10:00 AM</span></div>"
        "</div>"
    )
    driver = SimpleNamespace(page_source=html)
    theatres = scraper.parse_theatres(driver)
    assert theatres == [("Cinema 1", ["10:00 AM"])]
