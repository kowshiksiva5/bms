docker build -t bms-v4 .
docker run -d --name telegram-bot-service --restart unless-stopped \
  -e TZ=Asia/Kolkata \
  -e TELEGRAM_BOT_TOKEN="8435017096:AAGuyoNaHK6W0x2huypgBhgfV1BjQUQeqGk" \
  -e TELEGRAM_ALLOWED_CHAT_IDS="953590033" \
  -e TELEGRAM_CHAT_ID="953590033" \
  -e BMS_FORCE_UC=1 \
  -v /var/lib/bms/artifacts:/app/artifacts \
  --shm-size=1g \
  bms-v4 \
  python -m bot.bot
docker run -d --name telegram-worker-service-MONITOR_ID --restart unless-stopped \
  -e TZ=Asia/Kolkata \
  -e TELEGRAM_BOT_TOKEN="8435017096:AAGuyoNaHK6W0x2huypgBhgfV1BjQUQeqGk" \
  -e TELEGRAM_CHAT_ID="953590033" \
  -e BMS_FORCE_UC=1 \
  -v /var/lib/bms/artifacts:/app/artifacts \
  --shm-size=1g \
  bms-v3 \
  python worker.py --monitor-id MONITOR_ID --monitor --trace --artifacts-dir ./artifacts