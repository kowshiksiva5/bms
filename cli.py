import argparse
from typing import List

from config import get_default_city_slug
from notifier import notify
from scraper import get_available_movies, get_theatres_and_showtimes
from storage import (
    get_saved_theatres, add_saved_theatre, remove_saved_theatre,
    set_home_location, get_home_location, get_state, set_state
)
from utils import fuzzy_select, haversine_km, is_time_in_range, parse_time_to_minutes


def cmd_set_home(args: argparse.Namespace) -> None:
    set_home_location(args.lat, args.lon)
    print("Home location saved.")


def cmd_theatres(args: argparse.Namespace) -> None:
    if args.list:
        for t in get_saved_theatres():
            print(f"- {t}")
        return
    if args.add:
        add_saved_theatre(args.add)
        print("Added.")
        return
    if args.remove:
        remove_saved_theatre(args.remove)
        print("Removed.")


def _nearest(theatres, max_km=None, nearest=None):
    home = get_home_location()
    if home:
        def dist(t):
            if t.lat is None or t.lon is None:
                return 1e9
            return haversine_km(home[0], home[1], t.lat, t.lon)
        theatres = sorted(theatres, key=dist)
        if max_km is not None:
            theatres = [t for t in theatres if dist(t) <= max_km]
    if nearest is not None:
        theatres = theatres[:nearest]
    return theatres


def _ensure_date(current_date: str | None, url_date: str | None) -> str | None:
    if current_date:
        return current_date
    if url_date:
        return url_date
    ans = input("Date (YYYY-MM-DD) [Enter to skip]: ").strip()
    return ans or None


def _prompt_time_range_if_missing(start: str | None, end: str | None) -> tuple[str, str]:
    if start and end:
        return start, end
    user = input("Time range (HH:MM-HH:MM) [Enter for all day]: ").strip()
    if not user:
        return "00:00", "23:59"
    if '-' in user:
        s, e = [x.strip() for x in user.split('-', 1)]
        if parse_time_to_minutes(s) is not None and parse_time_to_minutes(e) is not None:
            return s, e
    print("Invalid time range. Using all day.")
    return "00:00", "23:59"


def _prompt_notify_defaults(args: argparse.Namespace) -> tuple[str | None, bool, str | None, str | None]:
    if getattr(args, 'email', None) or getattr(args, 'slack', False) or getattr(args, 'slack_webhook', None) or getattr(args, 'slack_token', None):
        return args.email, args.slack, getattr(args, 'slack_webhook', None), getattr(args, 'slack_token', None)
    print("Notify via: 1) Email  2) Slack  3) Both  Enter) None")
    choice = input("> ").strip()
    email = None
    slack = False
    slack_webhook = getattr(args, 'slack_webhook', None)
    slack_token = getattr(args, 'slack_token', None)
    if choice == '1' or choice == '3':
        email = input("Email address: ").strip() or None
    if choice == '2' or choice == '3':
        slack = True
        if not (slack_webhook or slack_token):
            print("Provide Slack webhook URL or leave empty to use env:")
            val = input("Webhook URL (optional): ").strip()
            if val:
                slack_webhook = val
    return email, slack, slack_webhook, slack_token


def _select_theatres_from_list(theatres):
    if not theatres:
        return []
    home = get_home_location()
    def fmt_dist(t):
        if home and t.lat is not None and t.lon is not None:
            return f" - {haversine_km(home[0], home[1], t.lat, t.lon):.1f} km"
        return ""
    for i, t in enumerate(theatres, 1):
        print(f"{i}. {t.name} ({len(t.showtimes)} shows){fmt_dist(t)}")
    sel = input("Select theatres to use (comma-separated), 'all', or Enter to skip: ").strip().lower()
    if sel == 'all':
        return theatres
    if not sel:
        return []
    try:
        idxs = [int(x) for x in sel.split(',') if x.strip().isdigit()]
        return [theatres[i-1] for i in idxs if 1 <= i <= len(theatres)]
    except Exception:
        return []

def cmd_release_day(args: argparse.Namespace) -> None:
    city = args.city or get_default_city_slug()
    # Accept URL or name
    mname, murl, mdate = _infer_movie_from_url(args.movie)
    if murl:
        movie = type('M', (), {'name': mname, 'url': murl})
        args.date = _ensure_date(args.date, mdate)
    else:
        movies = get_available_movies(city)
        movie = next((m for m in movies if args.movie.lower() in m.name.lower()), None)
        if not movie or not movie.url:
            print("Movie not found")
            return
        args.date = _ensure_date(args.date, None)
    theatres = get_theatres_and_showtimes(movie.url, date_str=args.date, debug=args.debug)
    theatres = _nearest(theatres, max_km=args.max_km, nearest=args.nearest)
    if args.include:
        theatres = [t for t in theatres if any(s.lower() in t.name.lower() for s in args.include)]
    if args.exclude:
        theatres = [t for t in theatres if all(s.lower() not in t.name.lower() for s in args.exclude)]
    # Show and select
    for i, t in enumerate(theatres[:max(len(theatres), 1)], 1):
        print(f"{i}. {t.name} ({len(t.showtimes)} shows)")
    print("Select theatres to save (comma-separated), or 'all', or press Enter to skip saving:")
    sel = input().strip().lower()
    selected = []
    if sel == 'all':
        selected = theatres
    elif sel:
        idxs = [int(x) for x in sel.split(',') if x.isdigit()]
        selected = [theatres[i-1] for i in idxs if 1 <= i <= len(theatres)]
    for t in selected:
        add_saved_theatre(t.name)
    # Notify immediately if any show open
    open_now = [(t.name, t.showtimes) for t in (selected or theatres) if t.showtimes]
    if open_now:
        lines = [f"{n}: {', '.join(st)}" for n, st in open_now]
        notify(
            f"Shows open for {movie.name}",
            "\n".join(lines),
            email=args.email,
            use_slack=args.slack,
            slack_webhook=args.slack_webhook,
            slack_token=args.slack_token,
            slack_channel=args.slack_channel,
        )
        print("Notification sent.")


def cmd_new_in_range(args: argparse.Namespace) -> None:
    city = args.city or get_default_city_slug()
    mname, murl, mdate = _infer_movie_from_url(args.movie)
    if murl:
        movie = type('M', (), {'name': mname, 'url': murl})
        args.date = _ensure_date(args.date, mdate)
    else:
        movies = get_available_movies(city)
        movie = next((m for m in movies if args.movie.lower() in m.name.lower()), None)
        if not movie or not movie.url:
            print("Movie not found")
            return
        args.date = _ensure_date(args.date, None)
    # Prompt-friendly defaults
    args.start, args.end = _prompt_time_range_if_missing(getattr(args, 'start', None), getattr(args, 'end', None))
    email, slack_flag, slack_webhook, slack_token = _prompt_notify_defaults(args)
    theatres = get_theatres_and_showtimes(movie.url, date_str=args.date, debug=args.debug)
    prev = get_state(args.state_key or f"range_{args.movie}_{args.start}_{args.end}")
    curr = set()
    for t in theatres:
        for st in t.showtimes:
            if is_time_in_range(st, args.start, args.end):
                curr.add(f"{t.name}|{st}")
    new_items = curr - prev
    if new_items:
        lines = []
        for item in sorted(new_items):
            tn, st = item.split('|', 1)
            lines.append(f"{tn}: {st}")
        notify(
            f"New show in range for {movie.name}",
            "\n".join(lines),
            email=email,
            use_slack=slack_flag,
            slack_webhook=slack_webhook,
            slack_token=slack_token,
            slack_channel=args.slack_channel,
        )
        print("Notification sent.")
    else:
        print("No new shows in range.")
    set_state(args.state_key or f"range_{args.movie}_{args.start}_{args.end}", curr)


def _infer_movie_from_url(url: str):
    # Accept full BMS movie URL; return (name, url, optional date)
    if '/movies/' not in url:
        return None, None, None
    parts = url.rstrip('/').split('/')
    date_iso = None
    # Detect YYYYMMDD tail
    tail = parts[-1]
    if len(tail) == 8 and tail.isdigit():
        y, m, d = tail[:4], tail[4:6], tail[6:8]
        date_iso = f"{y}-{m}-{d}"
        parts = parts[:-1]
    try:
        idx = parts.index('movies')
        slug = parts[idx + 2]  # movies/<city>/<slug>/...
    except Exception:
        slug = parts[-2]
    name = slug.replace('-', ' ').title()
    return name, url, date_iso



def cmd_from_url(args: argparse.Namespace) -> None:
    url = args.url.strip()
    name, url_parsed, date_from_url = _infer_movie_from_url(url)
    if not url_parsed:
        print("Invalid BookMyShow URL")
        return
    print(f"Movie: {name}")
    date = _ensure_date(None, date_from_url)
    theatres = get_theatres_and_showtimes(url_parsed, date_str=date, debug=args.debug)

    theatres_with_shows = [t for t in theatres if t.showtimes]

    radius = None
    if get_home_location():
        # If theatres provided explicitly, skip radius and selection
        if getattr(args, 'theatres', None):
            theatres_to_present = theatres_with_shows if theatres_with_shows else theatres
        else:
            while True:
                rad_in = input("Radius (km) from home to search [5/10/20/all, default 5]: ").strip().lower()
                if not rad_in:
                    radius = 5.0
                elif rad_in == 'all':
                    radius = None
                else:
                    try:
                        radius = float(rad_in)
                    except ValueError:
                        print("Invalid radius. Try 5, 10, 20 or 'all'.")
                        continue
                present_list = _nearest(theatres_with_shows if theatres_with_shows else theatres, max_km=radius)
                if not present_list and radius is not None:
                    print("No theatres found within this radius. Try a larger radius or 'all'.")
                    continue
                theatres_to_present = present_list
                break
    else:
        theatres_to_present = theatres_with_shows if theatres_with_shows else theatres

    if getattr(args, 'theatres', None):
        # Filter by provided theatre names
        chosen = []
        for t in theatres_to_present:
            if any(k.lower() in t.name.lower() for k in args.theatres):
                chosen.append(t)
        if not chosen:
            print("Provided theatres not found in current list; using all presented theatres.")
            chosen = theatres_to_present
    elif theatres_to_present:
        print("Available theatres (only those with shows listed first):")
        chosen = _select_theatres_from_list(theatres_to_present)
        if not chosen:
            chosen = theatres_to_present
    else:
        print("No theatres listed for this date.")
        saved = get_saved_theatres()
        if saved:
            print("Saved theatres:")
            for i, n in enumerate(saved, 1):
                print(f"{i}. {n}")
            sel = input("Select saved theatres (comma-separated) or Enter to use all: ").strip()
            if sel:
                idxs = [int(x) for x in sel.split(',') if x.strip().isdigit()]
                saved = [saved[i-1] for i in idxs if 1 <= i <= len(saved)]
            chosen = [type('T', (), {'name': n, 'showtimes': []}) for n in saved]
        else:
            print("No saved theatres. You can enter theatre names manually (comma-separated), or press Enter to exit.")
            manual = input("Enter theatre names: ").strip()
            if not manual:
                print("No theatres to monitor. Exiting.")
                return
            chosen = [type('T', (), {'name': n.strip(), 'showtimes': []}) for n in manual.split(',') if n.strip()]

    # Time range
    start = getattr(args, 'start', None)
    end = getattr(args, 'end', None)
    if not start or not end:
        start, end = _prompt_time_range_if_missing(start, end)

    action = '2' if getattr(args, 'monitor', False) else (input("Action: 1) Check now  2) Monitor (continuous) [1/2]: ").strip() or '1')

    if action == '1':
        lines = []
        theatres_now = get_theatres_and_showtimes(url_parsed, date_str=date, debug=args.debug)
        for t in theatres_now:
            if any(getattr(t, 'name', '') == c.name for c in chosen):
                for st in t.showtimes:
                    if is_time_in_range(st, start, end):
                        lines.append(f"{t.name}: {st}")
        if lines:
            print(f"\nFound {len(lines)} shows in the specified time range:")
            for line in sorted(lines):
                print(f"  {line}")
        else:
            print("No shows in that range right now.")
    else:
        print(f"\nMonitoring {name} on {date} for new shows...")
        print("Press Ctrl+C to stop monitoring.")
        email, slack_flag, slack_webhook, slack_token = _prompt_notify_defaults(args)
        interval_sec = (getattr(args, 'interval', None) or 5) * 60
        key = f"url_{name}_{date or 'any'}_{start}_{end}"
        prev = get_state(key)
        import time as _time
        try:
            while True:
                theatres = get_theatres_and_showtimes(url_parsed, date_str=date, debug=args.debug)
                curr = set()
                for t in theatres:
                    if any(getattr(t, 'name', '') == c.name for c in chosen):
                        for st in t.showtimes:
                            if is_time_in_range(st, start, end):
                                curr.add(f"{t.name}|{st}")
                new_items = curr - prev
                if new_items:
                    lines = []
                    for item in sorted(new_items):
                        tn, st = item.split('|', 1)
                        lines.append(f"{tn}: {st}")
                    notify(f"New shows for {name}", "\n".join(lines), email=email, use_slack=slack_flag, slack_webhook=slack_webhook, slack_token=slack_token)
                    print("Notification sent.")
                else:
                    print("No new shows.")
                prev = curr
                set_state(key, prev)
                print(f"Waiting {interval_sec//60} minutes...")
                _time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("Stopped.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='bms-cli')
    sub = p.add_subparsers(dest='cmd')

    sh = sub.add_parser('set-home')
    sh.add_argument('--lat', type=float, required=True)
    sh.add_argument('--lon', type=float, required=True)
    sh.set_defaults(func=cmd_set_home)

    th = sub.add_parser('theatres')
    th.add_argument('--list', action='store_true')
    th.add_argument('--add')
    th.add_argument('--remove')
    th.set_defaults(func=cmd_theatres)

    rd = sub.add_parser('release-day')
    rd.add_argument('movie', help='Movie name or BookMyShow movie URL')
    rd.add_argument('--city')
    rd.add_argument('--email')
    rd.add_argument('--slack', action='store_true', help='Send Slack notification (uses webhook or bot token env)')
    rd.add_argument('--slack-webhook', help='Override Slack webhook URL')
    rd.add_argument('--slack-token', help='Slack bot token (overrides env)')
    rd.add_argument('--slack-channel', help='Slack channel ID (overrides env)')
    rd.add_argument('--date', help='Target date in YYYY-MM-DD')
    rd.add_argument('--nearest', type=int)
    rd.add_argument('--max-km', type=float)
    rd.add_argument('--include', nargs='*')
    rd.add_argument('--exclude', nargs='*')
    rd.add_argument('--debug', action='store_true', help='Show browser window during scraping')
    rd.set_defaults(func=cmd_release_day)

    nr = sub.add_parser('new-in-range')
    nr.add_argument('movie', help='Movie name or BookMyShow movie URL')
    nr.add_argument('--city')
    nr.add_argument('--date', help='Target date in YYYY-MM-DD')
    nr.add_argument('--start', nargs='?', const='', help='Start time HH:MM (optional; will prompt)')
    nr.add_argument('--end', nargs='?', const='', help='End time HH:MM (optional; will prompt)')
    nr.add_argument('--email')
    nr.add_argument('--slack', action='store_true', help='Send Slack notification (uses webhook or bot token env)')
    nr.add_argument('--slack-webhook', help='Override Slack webhook URL')
    nr.add_argument('--slack-token', help='Slack bot token (overrides env)')
    nr.add_argument('--slack-channel', help='Slack channel ID (overrides env)')
    nr.add_argument('--state-key')
    nr.add_argument('--debug', action='store_true', help='Show browser window during scraping')
    nr.set_defaults(func=cmd_new_in_range)

    fu = sub.add_parser('from-url', help='Guided flow: paste a movie URL and follow prompts')
    fu.add_argument('url')
    fu.add_argument('--theatres', nargs='*', help='Theatre names to filter (skip prompt if provided)')
    fu.add_argument('--start', help='Start time HH:MM (skip prompt if provided)')
    fu.add_argument('--end', help='End time HH:MM (skip prompt if provided)')
    fu.add_argument('--interval', type=int, help='Monitoring interval in minutes (for monitor mode)')
    fu.add_argument('--monitor', action='store_true', help='Run in monitor mode without prompting')
    fu.add_argument('--email')
    fu.add_argument('--slack', action='store_true')
    fu.add_argument('--slack-webhook')
    fu.add_argument('--slack-token')
    fu.add_argument('--slack-channel')
    fu.add_argument('--debug', action='store_true', help='Show browser window during scraping')
    fu.set_defaults(func=cmd_from_url)

    return p


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, 'func'):
        parser.print_help()
        return
    args.func(args)


