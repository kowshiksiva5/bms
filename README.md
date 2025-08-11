# 🎬 BMS Movie Show Notifier Bot

> **Real-time movie show alerts for BookMyShow** - Never miss your favorite movies! Get instant notifications when new shows are available in your preferred theatres and dates.

## 🤖 Bot Placeholder Message

```
🎬 BMS Movie Show Notifier Bot

Get real-time alerts for movie shows on BookMyShow!

🔍 What you can do:
• Monitor specific movies for new showtimes
• Set up alerts for your favorite theatres
• Get notified when tickets become available
• Track multiple movies simultaneously
• Customize alert frequency and timing

📱 Commands:
/new - Create a new movie monitor
/list - View your active monitors
/help - Show all available commands

Start monitoring your favorite movies now! 🎭🎪
```

## ✨ Features

### 🎯 **Smart Monitoring**
- **Real-time scraping** of BookMyShow for instant show updates
- **Multi-theatre support** - Monitor specific theatres or any theatre
- **Date range monitoring** - Track shows across multiple dates
- **Custom intervals** - Set your preferred check frequency (1-60 minutes)

### 🔔 **Intelligent Notifications**
- **Instant alerts** when new shows are detected
- **Beautiful formatting** with movie details and booking links
- **Actionable buttons** for quick theatre/date management
- **Snooze functionality** - Pause alerts temporarily (2h/6h)

### 🛠️ **Advanced Controls**
- **Edit monitors** - Modify dates, theatres, and settings anytime
- **Health monitoring** - Check system status and performance
- **Import/Export** - Backup and restore your monitor configurations
- **Multi-user support** - Each user sees only their own monitors

### 🚀 **Reliable Infrastructure**
- **Docker deployment** - Easy setup and scaling
- **Error handling** - Automatic recovery and user notifications
- **Logging system** - Comprehensive debugging and monitoring
- **Platform compatibility** - Works on ARM64 (Apple Silicon) and x86_64

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │   Scheduler     │    │   Worker(s)     │
│                 │    │                 │    │                 │
│ • User Commands │    │ • Monitor Loop  │    │ • Web Scraping  │
│ • Notifications │    │ • Job Dispatch  │    │ • Chrome Driver │
│ • UI Sessions   │    │ • Error Handling│    │ • Data Parsing  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   SQLite DB     │
                    │                 │
                    │ • Monitors      │
                    │ • Show History  │
                    │ • User Sessions │
                    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- Telegram Bot Token (from @BotFather)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd bms
```

### 2. Environment Configuration
```bash
# Copy environment template
cp scripts/env.sh .env

# Edit .env with your settings
nano .env
```

**Required Environment Variables:**
```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Database Configuration
STATE_DB=./artifacts/bms.db

# Scraping Configuration
BMS_FORCE_UC=1
CHROME_BINARY=/usr/bin/google-chrome

# Timezone
TZ=Asia/Kolkata
```

### 3. Docker Deployment
```bash
# Start all services
./scripts/docker_up.sh

# Check status
./scripts/docker_logs.sh

# Follow logs in real-time
./scripts/docker_logs.sh bot -f
```

### 4. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run bot locally
./scripts/run_local.sh bot

# Run scheduler locally
./scripts/run_local.sh scheduler

# Run worker locally
./scripts/run_local.sh worker
```

## 📱 Bot Commands

### 🆕 **Create Monitor** (`/new <url>`)
Create a new movie monitor with interactive setup:
```
/new https://in.bookmyshow.com/movies/movie-name/ET00311782
```

**Setup Flow:**
1. **URL Validation** - Verify BookMyShow URL
2. **Date Selection** - Choose monitoring dates (up to 60 days)
3. **Theatre Selection** - Pick specific theatres or monitor all
4. **Interval Setup** - Set check frequency (1-60 minutes)
5. **Duration Mode** - Choose monitoring duration:
   - **Fixed** - Monitor specific dates
   - **Rolling** - Always monitor next N days
   - **Until** - Monitor until specific date
6. **Heartbeat** - Set health check interval (30-480 minutes)

### 📋 **List Monitors** (`/list`)
View all your active monitors with status and controls.

### ⚙️ **Monitor Management**
- **`/status <id>`** - View detailed monitor status
- **`/pause <id>`** - Pause monitoring temporarily
- **`/resume <id>`** - Resume paused monitoring
- **`/stop <id>`** - Stop monitoring permanently
- **`/delete <id>`** - Delete monitor and all data

### 🔧 **Advanced Controls**
- **`/edit_dates <id>`** - Modify monitoring dates
- **`/edit_theatres <id>`** - Change theatre selection
- **`/setinterval <id> <minutes>`** - Update check frequency
- **`/timewin <id> HH:MM-HH:MM`** - Set time window filter
- **`/snooze <id> <2h|6h|clear>`** - Temporarily pause alerts

### 📊 **System Commands**
- **`/health`** - Check system health and performance
- **`/import`** - Import monitor configurations
- **`/help`** - Show all available commands

## 🛠️ Management Scripts

### Docker Operations
```bash
# Start services
./scripts/docker_up.sh

# Stop services
./scripts/docker_down.sh

# Stop and remove everything
./scripts/docker_down.sh --purge

# Complete reset (rebuild)
./scripts/docker_reset.sh

# View logs
./scripts/docker_logs.sh

# Follow specific service logs
./scripts/docker_logs.sh bot -f
./scripts/docker_logs.sh worker-sample -f

# Run diagnostics
./scripts/docker_logs.sh --debug
```

### Database Management
```bash
# View database contents
./scripts/db_view.sh

# Clear database
./scripts/db_clear.sh
```

### Local Development
```bash
# Run bot locally
./scripts/run_local.sh bot

# Run scheduler locally
./scripts/run_local.sh scheduler

# Run worker locally
./scripts/run_local.sh worker

# Run one-time worker
./scripts/run_local.sh worker-one
```

## 📊 Database Schema

### Core Tables
- **`monitors`** - Monitor configurations and status
- **`seen`** - Tracked show history to avoid duplicates
- **`theatres_index`** - Discovered theatres per monitor
- **`ui_sessions`** - Multi-step wizard data
- **`runs`** - Execution history and error tracking
- **`snapshots`** - Show data snapshots for comparison

### Key Fields
- **`owner_chat_id`** - Multi-tenant user isolation
- **`state`** - Monitor status (RUNNING/PAUSED/STOPPING)
- **`snooze_until`** - Temporary alert suspension
- **`heartbeat_minutes`** - Health check interval
- **`mode`** - Duration mode (FIXED/ROLLING/UNTIL)

## 🔧 Configuration

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Required |
| `TELEGRAM_CHAT_ID` | Default chat for notifications | Required |
| `STATE_DB` | SQLite database path | `./artifacts/bms.db` |
| `BMS_FORCE_UC` | Force undetected-chromedriver | `1` |
| `CHROME_BINARY` | Chrome/Chromium binary path | `/usr/bin/google-chrome` |
| `TZ` | Timezone for timestamps | `Asia/Kolkata` |

### Docker Configuration
- **Platform**: Supports both ARM64 (Apple Silicon) and x86_64
- **Chrome**: Uses Google Chrome with platform emulation
- **Memory**: 1GB shared memory for browser operations
- **Volumes**: Persistent database and artifacts storage

## 🚨 Troubleshooting

### Common Issues

**1. Chrome Driver Failures**
```bash
# Check Chrome installation
docker exec bms-worker-sample which google-chrome

# Verify driver compatibility
./scripts/docker_logs.sh worker-sample --debug
```

**2. Bot Not Responding**
```bash
# Check bot status
./scripts/docker_logs.sh bot --debug

# Verify environment variables
docker exec bms-bot env | grep TELEGRAM
```

**3. Database Issues**
```bash
# View database contents
./scripts/db_view.sh

# Reset database
./scripts/db_clear.sh
```

**4. Performance Issues**
```bash
# Check system health
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=/health"
```

### Debug Commands
```bash
# Full system diagnostics
./scripts/docker_logs.sh --debug

# Check container processes
docker exec bms-bot ps aux
docker exec bms-worker-sample ps aux

# Test Python imports
docker exec bms-bot python -c "import config; print('OK')"
docker exec bms-worker-sample python -c "from services.driver_manager import DriverManager; print('OK')"
```

## 🔒 Security & Privacy

### Data Protection
- **User Isolation**: Each user only sees their own monitors
- **Local Storage**: All data stored locally in SQLite
- **No External APIs**: Direct scraping without third-party dependencies
- **Secure Environment**: Docker containerization with minimal permissions

### Best Practices
- **Token Security**: Keep Telegram bot tokens secure
- **Regular Updates**: Update dependencies and base images
- **Monitoring**: Use health checks and logging
- **Backup**: Regular database backups for important configurations

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone <repository-url>
cd bms

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Format code
black .
isort .

# Type checking
mypy .
```

### Code Structure
```
bms/
├── bot/                 # Telegram bot implementation
│   ├── bot.py          # Main bot logic
│   ├── commands.py     # Command definitions
│   ├── keyboards.py    # Inline keyboards
│   └── telegram_api.py # Message handling
├── services/           # Core services
│   ├── driver_manager.py    # Browser automation
│   └── monitor_service.py   # Monitor utilities
├── scripts/            # Management scripts
├── store.py           # Database operations
├── scheduler.py       # Background monitoring
├── worker.py          # Individual monitor execution
└── scraper.py         # Web scraping logic
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **BookMyShow** for providing movie show data
- **Telegram** for the bot platform
- **Undetected ChromeDriver** for reliable web scraping
- **Docker** for containerization and deployment

---

**🎬 Never miss a movie again!** Set up your BMS Movie Show Notifier Bot today and get instant alerts for your favorite movies. 🎭🎪
