# --- Telegram ---
export TELEGRAM_BOT_TOKEN="8435017096:AAGuyoNaHK6W0x2huypgBhgfV1BjQUQeqGk"
export TELEGRAM_ALLOWED_CHAT_IDS="953590033"

# --- Runtime / paths ---
export TZ=Asia/Kolkata
mkdir -p ./artifacts
export STATE_DB=./artifacts/state.db
export BOT_OFFSET_FILE=./artifacts/bot_offset.txt
export DEFAULT_DAILY_TIME="09:00"

# --- Chrome (optional) ---
# export CHROME_BINARY="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# export BMS_FORCE_UC=1
# export BMS_CHROME_VERSION_MAIN=138

# fallback chat (optional)
export TELEGRAM_CHAT_ID="953590033"
