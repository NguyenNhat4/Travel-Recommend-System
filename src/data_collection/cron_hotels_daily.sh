#!/usr/bin/env bash
# Job hằng ngày MỚI (tách khỏi cron_run.sh — nguồn ở đây gồm trip_hotels/trip_combos, nguồn mới, robots.txt
# cấm, chỉ dùng nội bộ theo quyết định người dùng đã xác nhận; không nên trộn với cron_run.sh vốn "chỉ gồm
# nguồn đã verify + miễn phí"). Crontab gợi ý: 0 2 * * * <đường dẫn file này> (2 giờ sáng, ít cạnh tranh mạng).
#
# Gồm: booking-hotels + agoda-hotels (đã kiểm chứng, chạy full 67 điểm đến) + trip-hotels (nguồn mới, MẶC ĐỊNH
# chỉ @deep — xem README/plan trước khi đổi TRIP_HOTELS_DESTINATIONS) + trip-combos (bay+ở thật). KHÔNG chạy
# lại trip_flights/trip_attractions — cron_run.sh đã làm mỗi 3 tiếng, trip_combos đọc thẳng
# data/interim/trip_flights.jsonl đã tươi sẵn.
#
# Ghi vào ./data thật (data/interim/*.jsonl không phải catalog đông băng — cào thêm vào đây vô hại), rồi
# normalise ra thư mục staging riêng (KHÔNG đụng data/products.jsonl/data/catalog/ thật) + kiểm sha256 của
# products.jsonl trước/sau để đảm bảo thật sự không đổi. Gộp staging vào catalog thật là quyết định thủ công
# của người dùng sau khi xem data/staging/hotels-<ngày>/stats.md — script này không tự làm.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON="${PYTHON:-python}"
LOCK=data/state/cron_hotels_daily.lock          # riêng với cron_pipeline.lock: 2 lịch không chặn nhau
mkdir -p data/state data/logs data/staging

# Chạy trình duyệt không màn hình qua Xvfb nếu có (VPS/cron không có X server thật); nếu không có xvfb-run,
# chạy thẳng (--headless) — mất giá booking.com (đã ghi rõ trong crawl.py --headless), chấp nhận cho lượt này
# thay vì fail cứng, nhưng LOG cảnh báo để người xem log biết.
if command -v xvfb-run >/dev/null 2>&1; then
  RUN="xvfb-run -a $PYTHON"
  HEADLESS_FLAG=""
else
  RUN="$PYTHON"
  HEADLESS_FLAG="--headless"
  echo "$(date -Is) CẢNH BÁO: không có xvfb-run – chạy --headless, booking.com sẽ THIẾU GIÁ" >> data/logs/cron-hotels-errors.log
fi

# Nhóm điểm đến cho trip_hotels — mặc định @deep (8 điểm đến lớn, budget 15/điểm đến, xem Budget.trip_hotels
# trong collectors/plan.py). Mở rộng dần bằng cách sửa biến này (vd "@deep,Huế,Quy Nhơn") SAU KHI xác nhận
# @deep chạy vài ngày không bị chặn liên tục — không tự ý đổi thành @all.
TRIP_HOTELS_DESTINATIONS="${TRIP_HOTELS_DESTINATIONS:-@deep}"

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date -Is) SKIP: lượt chạy trước vẫn chưa xong (khoá $LOCK)" >> data/logs/cron-hotels-errors.log
  exit 0
fi

find data/logs -maxdepth 1 -name 'cron-hotels-*.log' -mtime +14 -delete 2>/dev/null || true

CATALOG_BEFORE=""
if [ -f data/products.jsonl ]; then
  CATALOG_BEFORE=$(sha256sum data/products.jsonl | cut -d' ' -f1)
fi

LOG="data/logs/cron-hotels-$(date +%Y%m%d-%H%M%S).log"
{
  echo "=== $(date -Is) start ==="

  echo "--- booking-hotels (67 điểm đến) ---"
  $RUN crawl.py booking-hotels $HEADLESS_FLAG --checkin-offset-days 30 || echo "booking-hotels: lỗi/bị chặn một phần, tiếp tục"

  echo "--- agoda-hotels (67 điểm đến) ---"
  $RUN crawl.py agoda-hotels $HEADLESS_FLAG --checkin-offset-days 30 || echo "agoda-hotels: lỗi/bị chặn một phần, tiếp tục"

  echo "--- trip-hotels ($TRIP_HOTELS_DESTINATIONS) ---"
  $RUN crawl.py trip-hotels $HEADLESS_FLAG --destinations "$TRIP_HOTELS_DESTINATIONS" --checkin-offset-days 30 || echo "trip-hotels: lỗi/bị chặn một phần, tiếp tục"

  echo "--- trip-combos ---"
  $RUN crawl.py trip-combos $HEADLESS_FLAG --checkin-offset-days 21 || echo "trip-combos: lỗi/bị chặn một phần, tiếp tục"

  echo "--- normalise (staging, không đụng catalog thật) ---"
  STAGE="data/staging/hotels-$(date +%Y%m%d)"
  rm -rf "$STAGE"
  mkdir -p "$STAGE/interim"
  cp data/interim/*.jsonl "$STAGE/interim/" 2>/dev/null || true
  $PYTHON normalise.py --data-dir "$STAGE"
  echo "Kết quả staging: $STAGE/stats.md"

  if [ -n "$CATALOG_BEFORE" ]; then
    CATALOG_AFTER=$(sha256sum data/products.jsonl | cut -d' ' -f1)
    if [ "$CATALOG_BEFORE" != "$CATALOG_AFTER" ]; then
      echo "LỖI: data/products.jsonl (catalog đông băng) đã bị đổi trong lúc chạy — không được tự sửa!" >&2
      exit 1
    fi
    echo "Xác nhận: data/products.jsonl (catalog đông băng) không đổi."
  fi

  echo "=== $(date -Is) done (exit 0) ==="
} >> "$LOG" 2>&1 || {
  status=$?
  echo "$(date -Is) FAIL exit=$status — xem $LOG" >> data/logs/cron-hotels-errors.log
  exit "$status"
}
