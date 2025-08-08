# Architecture Overview

This project is a modular, CLI-driven scraper and notifier for BookMyShow.

## Goals
- Reliable scraping of dynamic pages (Selenium)
- Easy configuration via environment variables or .env
- Extensible notification channels (email, Slack)
- Lightweight persistence for user preferences and state
- Simple deployment to free/low-cost cloud platforms

## Components

- scraper.py
  - Selenium-based browser automation
  - Functions: get_available_movies(city_slug), get_theatres_and_showtimes(movie_url)
  - Uses headless Chrome; Chrome binary can be overridden via env

- utils.py
  - Distance calculation (Haversine)
  - Time parsing and range checks
  - Fuzzy selection helper

- storage.py
  - JSON-backed store (default ~/.bms_config.json, configurable via env)
  - Saved theatres list, home location, and per-check state

- notifier.py
  - Email (Gmail app password) and Slack webhook notifications
  - notify() dispatches based on provided flags/env

- config.py
  - Loads .env (python-dotenv)
  - Centralizes env access for city, config path, email creds, Chrome path

- cli.py
  - Argparse subcommands and options
  - release-day, new-in-range, set-home, theatres

- main.py
  - Thin entrypoint delegating to CLI

## Data Flow
1. CLI parses arguments and reads configuration from env
2. Scraper navigates BookMyShow pages and collects movies/theatres/showtimes
3. storage.py manages persisted state (saved theatres, previous showtimes)
4. utils.py filters/sorts by distance and time windows
5. notifier.py sends email/Slack when new showtimes are detected

## Concurrency & Scaling
- Each CLI invocation is stateless except for the small JSON store
- To run concurrent monitors (e.g., many movies/time-windows):
  - Use separate processes (cron entries, serverless tasks, or multiple containers)
  - Provide different --state-key values to isolate state
  - Configure a remote, shared BMS_CONFIG_PATH (e.g., mounted volume or object store) if needed

## Deployment Options (Free/Low Cost)
- Docker on a small VM (Lightsail, Oracle Free Tier, etc.) with cron
- GitHub Actions cron (nightly/hourly jobs) for one-shot checks that notify via Slack/email
- Railway/Render free tier worker with a persistent volume (if available)
- Google Colab / Kaggle Notebook for manual, ad-hoc runs (no background)
  - Use pip install -r requirements.txt and run commands in cells

## Extensibility
- Add new notifiers: create send_*.py and integrate with notify()
- Add new filters: extend utils.py with parsing/validation helpers
- Adapt to site changes: update selectors in scraper.py

## Security Notes
- Use app passwords for email; never commit secrets
- Prefer .env (not committed) or platform secret managers
- Rate-limit scraping; respect ToS
