Awesome—here’s a clean, complete README you can drop into the repo so anyone can get up to speed fast.

---

# BMS Alerts – BookMyShow showtime monitor (Telegram-driven)

Get instant Telegram alerts when new showtimes appear on BookMyShow for the movies and theatres you care about. Drive everything from Telegram: create monitors, change dates/theatres, pause/resume, and see status/health.

---

## What this does (in one breath)

* You send the bot a BMS movie link (e.g., `https://in.bookmyshow.com/movies/hyderabad/coolie/ET00395817`).
* The bot guides you to pick dates and theatres (or use defaults), interval, and an end date.
* A background worker opens the corresponding `/buytickets/.../YYYYMMDD` pages in a headless Chrome, scrapes theatres & times, and compares with previously seen ones.
* New showtimes → Telegram alert.
* Every few hours → heartbeat summary so you know it’s alive.
* You can run multiple monitors at once, all managed via Telegram.

---

## High-level architecture

```
┌─────────────────┐        commands/callbacks          ┌──────────────────────────┐
│  Telegram App   │◀──────────────────────────────────▶│  bot (python-telegram-bot)│
└─────────────────┘                                    └─────────────┬─────────────┘
                                                                writes/reads
                                                             (SQLite, JSON state)
                                                            ┌──────────────────────┐
                                                            │   storage (SQLite)   │
                                                            │  data/monitors.db    │
                                                            └──────────┬───────────┘
                                                           schedules   │   reads configs
                                                ┌──────────────────────┴──────────────────────┐
                                                │            scheduler / worker               │
                                                │  (loops every N minutes per monitor)        │
                                                └──────────────────────┬──────────────────────┘
                                        opens pages, parses theatres/  │  send alerts/heartbeat
                                        showtimes, updates state        ▼
                                  ┌──────────────────────────────┐   ┌─────────────────┐
                                  │      scraper (Selenium/UC)   │   │ Telegram Alerts │
                                  │ CF/oops recovery + JSON/DOM  │   └─────────────────┘
                                  │ parsing + artifacts (HTML/PNG)│
                                  └──────────────────────────────┘
```

* **bot**: interactive Telegram bot; stores/edits monitor configs; exposes slash commands and inline keyboards.

## Local scripts

Environment variables

1) Create a `.env` from `.env.example` and fill values.
2) For local shell usage, you can also `source scripts/env.sh` (optional). Scripts will try to load `.env` automatically when using Docker compose.

```
# View SQLite DB summary
scripts/db_view.sh [--monitors]

# Clear DB and artifacts (destructive)
scripts/db_clear.sh --yes

# Run locally (choose one)
scripts/run_local.sh bot
scripts/run_local.sh scheduler
scripts/run_local.sh worker --monitor-id <MID>
scripts/run_local.sh onepass <URL or args>

# Docker lifecycle
scripts/docker_up.sh      # build+up
scripts/docker_down.sh    # down
scripts/docker_reset.sh   # rm containers, rebuild image, up
```

## Multi-chat behavior

- The bot is multi-tenant. Each monitor is tied to the chat that created it via `owner_chat_id`.
- Alerts, heartbeats, and error messages are delivered only to that chat. They will not appear in other chats by default.
- To allow any chat to use the bot, set `TELEGRAM_ALLOWED_CHAT_IDS` empty in `.env`. To restrict, list comma-separated chat IDs.

## Scraping scope (city vs URL)

- Scraping is driven entirely by the URL you provide (the BookMyShow buytickets link). If the URL targets a specific city/movie page, the scraper operates on that page’s content.
- The system injects the selected date(s) into that URL but does not change the city; choose the correct URL for your target city.

## Configuration quick start

1) Copy `.env.example` to `.env` and fill values (bot token, allowed chat IDs, etc.)
2) Run locally:
   - `scripts/run_local.sh bot`
   - `scripts/run_local.sh scheduler`
3) Or with Docker: `scripts/docker_up.sh`

* **scheduler/worker**: periodically runs checks per active monitor; de-dupes against a persisted “seen” set; posts alerts & heartbeats.
* **scraper**: resilient headless browser (Selenium / undetected-chromedriver), stealth tweaks, Cloudflare & oops recovery, JSON/DOM parsing, artifact snapshots for debugging.

---

## Repo layout (rev2)

```
.
├── bot/
│   ├── bot.py                # Telegram bot entrypoint
│   ├── keyboards.py          # Inline keyboards & helpers
│   ├── handlers.py           # Command & callback handlers
│   └── flows.py              # Multi-step /new flow (URL → dates → theatres → schedule)
├── scraper.py                # Headless browser + parsing (robust; artifacts)
├── scheduler.py              # Background worker loop; runs all monitors
├── storage.py                # SQLite models, migrations, CRUD
├── utils.py                  # Small helpers (date format, tg_send, etc.)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md                 # ← this file
```

> If your repo differs slightly, follow the commands here—paths in Docker use `/app/…`.

---

## Requirements

* **Python**: 3.11+
* **Chrome**: Google Chrome stable (or use Docker image that installs it)
* **Telegram**: bot token + your chat id

---

## 1) Telegram setup (one-time)

1. DM **@BotFather** → `/newbot` → get `TELEGRAM_BOT_TOKEN`.
2. Get your **chat id**: message your bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and grab your `chat.id` (or use any “get chat id” bot).
3. Optional: restrict usage to your id(s) with `ALLOWED_CHAT_IDS`.

---

## 2) Quickstart — run locally (no Docker)

```bash
# 0) clone repo and cd
pip install -r requirements.txt

# 1) env (macOS/Linux)
export TZ=Asia/Kolkata
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="953590033"
# optional
export ALLOWED_CHAT_IDS="953590033"        # comma-separated IDs allowed to use the bot
export DB_PATH="./data/monitors.db"         # SQLite path (dir must exist)
export ARTIFACTS_DIR="./artifacts"          # screenshots/HTML for debugging
export BMS_FORCE_UC=1                       # prefer undetected-chromedriver
mkdir -p "$(dirname "$DB_PATH")" "$ARTIFACTS_DIR"

# 2) run bot (terminal A)
python bot/bot.py

# 3) run worker (terminal B)
python scheduler.py --trace --artifacts-dir "$ARTIFACTS_DIR" --heartbeat-minutes 180
```

Now open Telegram and talk to your bot: `/start` → `/new`.

---

## 3) Quickstart — run in Docker/Compose (recommended for servers)

### Option A: single container (just the worker)

If you already have a running bot elsewhere, you can run only the worker:

```bash
docker build -t bms-rev2:latest .
docker run -d --name bms-scheduler --restart unless-stopped \
  -e TZ=Asia/Kolkata \
  -e TELEGRAM_BOT_TOKEN="123:ABC" \
  -e TELEGRAM_CHAT_ID="953590033" \
  -e ALLOWED_CHAT_IDS="953590033" \
  -e DB_PATH="/app/data/monitors.db" \
  -e ARTIFACTS_DIR="/app/artifacts" \
  -e BMS_FORCE_UC=1 \
  -v /var/lib/bms/data:/app/data \
  -v /var/lib/bms/artifacts:/app/artifacts \
  --shm-size=1g \
  bms-rev2:latest \
  python scheduler.py --trace --artifacts-dir /app/artifacts --heartbeat-minutes 180
```

### Option B: docker-compose (bot + worker)

`docker-compose.yml` (provided) runs **both** services and persists DB/artifacts:

```bash
# Edit .env with secrets then:
docker compose up -d --build
# logs:
docker compose logs -f bot
docker compose logs -f worker
```

**.env example**

```
TZ=Asia/Kolkata
TELEGRAM_BOT_TOKEN=123:ABC
TELEGRAM_CHAT_ID=953590033
ALLOWED_CHAT_IDS=953590033
DB_PATH=/app/data/monitors.db
ARTIFACTS_DIR=/app/artifacts
BMS_FORCE_UC=1
```

---

## Using the bot

### Core flow: `/new`

1. **Paste BMS movie URL.**
   e.g., `https://in.bookmyshow.com/movies/hyderabad/coolie/ET00395817`
2. **Pick date(s).**
   Inline date buttons (we normalize to `YYYYMMDD` for the URL).
3. **Pick theatres.**

   * If the page lists theatres, you’ll get a selectable list.
   * If not, we offer your **default list** (customizable).
   * You can also choose **Any** to watch all theatres.
4. **Pick check interval** (minutes).
5. **Pick “monitor until” date** (when to auto-stop; or choose “No end”).
6. **Baseline?**

   * **Yes** → we record current shows and only alert on **newly added** ones.
   * **No** → we alert immediately for anything visible.

When saved, you’ll receive a **Monitor ID** (e.g., `M-1027`). That’s your handle.

### Slash commands (shown in Telegram’s `⌨️` menu)

* `/new` – start a new monitor
* `/list` – see all monitors you own (id, movie, dates, status)
* `/status [id]` – status of one (or all if empty)
* `/pause [id]` – pause a monitor
* `/resume [id]` – resume a monitor
* `/stop [id]` – stop & archive a monitor
* `/interval [id] [min]` – change interval
* `/theatres [id]` – update theatre filters
* `/dates [id]` – update dates
* `/heartbeat [min]` – change global heartbeat cadence
* `/help` – quick help

> You can also tap inline buttons to confirm choices, navigate back, or cancel during the `/new` flow.

### Alerts you’ll see

* **New shows**

  ```
  🎟️ New shows detected
  Movie: COOLIE
  Date: 2025-08-13
  Theatre: PVR: Inorbit, Cyberabad
  Times: 11:10 PM, 11:55 PM
  Monitor: M-1027 | Interval: 10m
  ```
* **Heartbeat (health)**

  ```
  ✅ Worker healthy (last 3h)
  Running: 2 monitors
  No changes since last summary
  Next run: ~8m
  ```

---

## How scraping works (practical details)

* We always navigate to `/buytickets/<ETCODE>/<YYYYMMDD>` when possible.
* Headless Chrome with **Selenium**; fallback to **undetected-chromedriver** if `BMS_FORCE_UC=1`.
* Stealth tweaks: remove `webdriver`, timezone to IST, set `Referer`, accept-language.
* Resiliency:

  * Detects blank/oops pages → reload.
  * Detects Cloudflare interstitial → retry.
  * Scrolls a few times to trigger lazy loading.
  * Saves HTML/PNG artifacts (`ARTIFACTS_DIR`) when `--trace` is on.
* Parsing strategy:

  1. Parse embedded JSON fragments with `"type":"venue-card"` (fast, precise).
  2. Fallback DOM scan for theatre rows + times (`12:34 AM/PM`).

---

## Data model (SQLite)

`monitors` table (simplified):

* `id` (PK)
* `chat_id` – owner
* `url` – canonical movie URL
* `dates` – JSON list of `YYYYMMDD`
* `theatres` – JSON list (or `["any"]`)
* `interval_min` – check frequency
* `until` – ISO date or null (no end)
* `baseline` – bool
* `status` – running | paused | stopped
* `seen` – JSON set of `"Theatre|YYYYMMDD|HH:MM AM/PM"`
* `created_at`, `updated_at`, `last_run`, `last_heartbeat`

All changes happen via bot commands & inline flows; the worker only reads configs and writes `seen` and timestamps.

---

## CLI flags & env (worker)

**scheduler.py**

* `--trace` – verbose logs, save HTML/PNG to artifacts
* `--artifacts-dir PATH`
* `--heartbeat-minutes N` – default 180
* `--max-concurrent K` – (if implemented) cap parallel page checks

**Environment**

* `TZ` – `Asia/Kolkata` recommended
* `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` – how we send messages
* `ALLOWED_CHAT_IDS` – comma-separated list of users allowed to use the bot
* `DB_PATH` – SQLite path (dir must exist)
* `ARTIFACTS_DIR` – for snapshots
* `BMS_FORCE_UC=1` – prefer UC if needed
* `CHROME_BINARY` – override Chrome path if not the default

---

## Operating it (server)

* **Start (compose):**

  ```bash
  docker compose up -d --build
  ```
* **Logs:**

  ```bash
  docker compose logs -f bot
  docker compose logs -f worker
  ```
* **Stop:**

  ```bash
  docker compose down
  ```
* **Update code:**

  ```bash
  git pull
  docker compose up -d --build
  ```

---

## Troubleshooting

**1) “cannot open database file”**
Make sure the directory for `DB_PATH` exists and is writable by the process/container. In Docker, mount a host volume:

```
-v /var/lib/bms/data:/app/data
```

and set `DB_PATH=/app/data/monitors.db`.

**2) Cloudflare / blank pages**
Keep `BMS_FORCE_UC=1` set, and run with `--trace` to capture artifacts. Check `/app/artifacts/*_loaded.html/png` for clues.

**3) No theatres parsed**
Open the saved HTML artifact and search for `"type":"venue-card"`. If missing, the fallback DOM parser should still pick times. Sometimes you need a couple scrolls; the worker does that, but increase interval to reduce load if pages are heavy.

**4) Health alerts not arriving**
Confirm:

* The worker started with `--heartbeat-minutes N` (and N > 0).
* Bot can send messages to your chat id (try `/help` and a manual message).
* Timezone/env are set. Logs will print health emissions.

**5) Chromedriver/Chrome mismatch**
Docker image installs **google-chrome-stable** and uses Selenium’s bundled driver. On bare metal, keep Chrome up to date, or set `CHROME_BINARY`.

---

## Security notes

* Treat `TELEGRAM_BOT_TOKEN` as a secret. Don’t commit it.
* Use `ALLOWED_CHAT_IDS` to restrict who can create/alter monitors.
* Be mindful of scraping ethics: keep intervals reasonable (10+ min), and don’t hammer every date at once.

---

## Extending (ideas)

* Per-monitor chat targets (send alerts to different chats/groups).
* Web dashboard (read-only) for monitors & artifacts.
* Auto-retry strategy on CF blocks with exponential backoff.
* Multi-city support presets & templates per user.
* Export/import monitor definitions as JSON.

---

## Example end-to-end

1. Start bot & worker (local or Docker).
2. In Telegram:

   * `/new` → paste `https://in.bookmyshow.com/movies/hyderabad/coolie/ET00395817`
   * Select **2025-08-13**, **2025-08-14**
   * Pick **PVR: Inorbit, Cyberabad**, **AMB Cinemas: Gachibowli** (or **Any**)
   * Interval **10** minutes
   * Monitor until **2025-08-15**
   * Baseline **Yes**
3. Bot replies with `Monitor M-1027 created`.
   You’ll get **New shows** alerts as soon as shows appear, plus a **heartbeat** every \~3h.

---

If you want, I can also drop this directly into `README.md` in your repo—just say the word.
