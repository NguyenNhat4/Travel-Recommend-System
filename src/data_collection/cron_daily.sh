#!/usr/bin/env bash
# Job hằng ngày trên VPS (console, không trình duyệt): cào HTTP → chuẩn hoá → gate → promote → nạp DB local/cloud → embed.
# Crontab gợi ý (02:00 giờ máy): 0 2 * * * /đường/dẫn/src/data_collection/cron_daily.sh
# Kết nối DB/Weaviate/Cohere đọc từ src/data_collection/.env (xem .env.example). Khoá chống chồng lượt nằm trong daily.py.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON="${PYTHON:-python}"
MAX_HOURS="${DAILY_MAX_HOURS:-20}"   # quá hạn thì dừng êm phần cào còn chạy rồi vẫn publish phần đã có
mkdir -p data/logs
find data/logs -maxdepth 1 -name 'daily-*.log' -mtime +30 -delete 2>/dev/null || true

LOG="data/logs/daily-$(date +%Y%m%d-%H%M%S).log"
"$PYTHON" daily.py run --max-hours "$MAX_HOURS" >> "$LOG" 2>&1
status=$?
if [ "$status" -ne 0 ]; then
  echo "$(date -Is) daily.py thoát mã $status — xem $LOG" >> data/logs/daily-errors.log
fi
exit "$status"
