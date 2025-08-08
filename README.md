# BookMyShow Showtime Monitor

A modular, CLI-first tool to discover movies, find theatres and showtimes, and send email/Slack alerts when new shows are available on BookMyShow. Built with Selenium and designed for headless/cloud use.

## Capabilities

- ✅ Robust scraping with Selenium and multiple fallback selectors
- ✅ Environment-based configuration (`.env` supported via python-dotenv)
- ✅ Save your home location and sort theatres by nearest distance
- ✅ Save favourite theatres and manage them with commands
- ✅ Release-day flow: pick nearest theatres; alert when any shows are open
- ✅ Time-window alerts: get notified only when new showtimes appear in a range
- ✅ Stateful diffing so you only get alerts for newly opened shows
- ✅ Notifications via Email and Slack (Webhook or Bot Token)
- ✅ Docker container for easy deployment to cloud/cron

## Installation

1) Install dependencies
```bash
pip install -r requirements.txt
```

2) Install Chrome/Chromium and ChromeDriver
- macOS: `brew install --cask google-chrome` and `brew install chromedriver`
- Ubuntu/Debian: `sudo apt-get install -y google-chrome-stable chromium-chromedriver`
- Windows: Install Chrome and download matching ChromeDriver from `https://chromedriver.chromium.org/`

3) Optional: Create a `.env` with your defaults
```env
# City slug
BMS_CITY_SLUG=hyderabad
# Where to store saved theatres/home
BMS_CONFIG_PATH=~/.bms_config.json
# Email (Gmail recommended)
BMS_EMAIL_FROM=your_email@gmail.com
BMS_EMAIL_APP_PASSWORD=your_app_password
# Slack (either webhook or bot token + channel)
BMS_SLACK_WEBHOOK_URL=
BMS_SLACK_BOT_TOKEN=
BMS_SLACK_CHANNEL=
# Override Chrome path if needed
# CHROME_BINARY=/usr/bin/google-chrome
```

## Commands

All commands are invoked via:
```bash
python main.py <command> [options]
```

### 1) Set home location
Used for distance sorting and nearest filtering.
```bash
python main.py set-home --lat 17.4532618 --lon 78.3670597
```

### 2) Manage saved theatres
```bash
# List saved theatres
python main.py theatres --list

# Add or remove a theatre by name (as seen on BookMyShow)
python main.py theatres --add "AMB Cinemas Gachibowli"
python main.py theatres --remove "AMB Cinemas Gachibowli"
```

### 3) Release-day flow (pick nearest; alert if open)
- Finds the movie’s theatres
- Sorts by nearest (if home set)
- Lets you save selected theatres
- Optionally notifies immediately if any shows are open
```bash
python main.py release-day "Movie Name" \
  --city hyderabad \
  --email you@example.com \
  --slack \
  --slack-webhook https://hooks.slack.com/services/XXX/YYY/ZZZ \
  --nearest 10 \
  --max-km 12.5 \
  --include PVR INOX \
  --exclude 4DX
```
Options:
- `--city`: City slug (default from `BMS_CITY_SLUG` or `hyderabad`)
- `--email`: Email to notify immediately if shows are open
- `--slack`: Send Slack notification (uses webhook or bot token env)
- `--slack-webhook`: Override Slack webhook URL
- `--slack-token`: Provide Slack bot token directly
- `--slack-channel`: Provide Slack channel ID directly
- `--nearest N`: Only show the nearest N theatres
- `--max-km KM`: Only include theatres within KM of your home
- `--include STR ...`: Include theatres whose name contains any of STR
- `--exclude STR ...`: Exclude theatres whose name contains any of STR

### 4) New shows in a time window (stateful)
Notifies only for newly added showtimes between `--start` and `--end`. Re-run on a schedule (cron) to keep monitoring.
```bash
python main.py new-in-range "Movie Name" \
  --city hyderabad \
  --start 18:00 --end 22:00 \
  --email you@example.com \
  --slack \
  --slack-token xoxb-... \
  --slack-channel C0123456789 \
  --state-key evening
```
Options:
- `--start HH:MM` and `--end HH:MM`: Time window in 24h
- `--state-key`: Optional custom key for persisted state

## Running in Docker / Cloud

Build and run:
```bash
docker build -t bms .
# Test connectivity and scraping
docker run --rm --env-file .env bms python main.py --test
# Example: run a one-shot check for new-in-range
docker run --rm --env-file .env bms \
  python main.py new-in-range "Movie Name" --city hyderabad --start 18:00 --end 22:00 --email you@example.com --state-key evening
```

Cron example (every 10 minutes):
```cron
*/10 * * * * cd /path/to/bms && docker run --rm --env-file .env bms \
  python main.py new-in-range "Movie Name" --city hyderabad --start 18:00 --end 22:00 --email you@example.com --state-key evening
```

## Configuration Reference
- `BMS_CITY_SLUG`: Default city slug (e.g. `hyderabad`)
- `BMS_CONFIG_PATH`: Where to store `home_lat/home_lon` and `saved_theatres` (default `~/.bms_config.json`)
- `BMS_EMAIL_FROM`: Sender email (Gmail recommended)
- `BMS_EMAIL_APP_PASSWORD`: Gmail App Password (not your normal password)
- `BMS_SLACK_WEBHOOK_URL`: Slack webhook for channel notifications
- `BMS_SLACK_BOT_TOKEN`: Slack bot token for API-based notifications
- `BMS_SLACK_CHANNEL`: Slack channel ID for API-based notifications
- `CHROME_BINARY`: Path to Chrome binary (used in headless/Docker)

## How it works
- `scraper.py`: Selenium scraping logic for movies/theatres/showtimes
- `utils.py`: Distance, fuzzy/time helpers
- `storage.py`: JSON-backed persistent state and saved theatres
- `notifier.py`: Email and Slack delivery (uses env defaults)
- `cli.py`: Argparse CLI with subcommands
- `main.py`: Thin entrypoint that delegates to the CLI

## Troubleshooting
- Chrome/Driver issues: ensure versions match and `CHROME_BINARY` is set if needed
- No movies/theatres: the site may have changed; retry or update selectors
- Notifications not sent: set email or Slack creds and flags

## Notes
- Respect the target site’s terms of service and robots policies.
- Use reasonable scheduling intervals to avoid rate-limiting.
