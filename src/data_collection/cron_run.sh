#!/usr/bin/env bash
# Chạy pipeline mỗi 3 tiếng qua cron (crontab: 0 */3 * * * <đường dẫn file này>).
# Chỉ gồm 2 nguồn đã verify thật + miễn phí: Vinpearl (hotel+phòng) và Trip.com (bay+điểm tham quan).
# Agoda/Booking CHƯA nằm trong đây — xem ghi chú trong hội thoại lúc thêm file này.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON="${PYTHON:-python}"
REPO_ROOT="$(cd ../.. && pwd)"
LOCK=data/state/cron_pipeline.lock
mkdir -p data/state data/logs

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date -Is) SKIP: lượt chạy trước vẫn chưa xong (khoá $LOCK)" >> data/logs/cron-errors.log
  exit 0
fi

# dọn log cũ hơn 14 ngày để khỏi phình data/logs/
find data/logs -maxdepth 1 -name 'cron-*.log' -mtime +14 -delete 2>/dev/null || true

LOG="data/logs/cron-$(date +%Y%m%d-%H%M%S).log"
{
  echo "=== $(date -Is) start ==="
  docker compose -f "$REPO_ROOT/docker-compose.yml" up -d --wait postgres
  "$PYTHON" pipeline_demo.py run --live-vinpearl --calendar-days 30 --live-trip --replay-delay-ms 0
  echo "=== $(date -Is) done (exit 0) ==="
} >> "$LOG" 2>&1 || {
  status=$?
  echo "$(date -Is) FAIL exit=$status — xem $LOG" >> data/logs/cron-errors.log
  exit "$status"
}
