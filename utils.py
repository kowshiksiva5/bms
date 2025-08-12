# utils.py
import re


def movie_title_from_url(url: str) -> str:
    """Best-effort title from a BMS movie URL, else ET code, else 'Movie'."""
    try:
        m = re.search(r"/movies/[^/]+/([^/?#]+)", url)  # slug after /movies/<city>/
        if m:
            slug = re.sub(r"[-_]+", " ", m.group(1)).strip()
            if slug:
                base = " ".join(w.capitalize() for w in slug.split())
                # keep common tokens uppercased
                base = re.sub(r"\b(Imax|3d|4dx)\b", lambda x: x.group(0).upper(), base)
                return base
        m2 = re.search(r"(ET\d{5,})", url)
        if m2:
            return m2.group(1)
    except Exception:
        pass
    return "Movie"


def titled(prefix_src, text: str) -> str:
    """
    prefix_src: monitor dict with 'url' OR the url string itself.
    Returns a message with a title prefix.
    """
    try:
        url = prefix_src["url"] if isinstance(prefix_src, dict) else str(prefix_src)
    except Exception:
        url = str(prefix_src)
    title = movie_title_from_url(url)
    return f"🎬 {title}\n{text}"
