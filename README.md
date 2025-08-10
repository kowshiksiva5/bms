# BMS Telegram Monitor

## Local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
source env.sh

# Start bot (inline /new wizard)
python bot/bot.py

# After /new prints a monitor id (e.g., mabc123), start worker:
python worker.py --monitor-id mabc123 --monitor --trace --artifacts-dir ./artifacts
```
