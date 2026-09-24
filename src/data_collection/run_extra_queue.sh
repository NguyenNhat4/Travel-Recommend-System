#!/usr/bin/env bash
# Hàng đợi cào thêm trên Booking: chạy NỐI TIẾP (không thêm cửa sổ Chromium) và chỉ trong khung giờ có người ngồi máy.
#
#   ./run_extra_queue.sh                       # khung 07:00–23:00
#   FROM=08:00 UNTIL=22:00 ./run_extra_queue.sh
#
# Thứ tự (mọi bước cùng host www.booking.com, chung nhịp rate-limit nên không chạy song song):
#   0. chờ các lượt khách sạn Booking đang chạy (terminal `batch.py run booking-hotels`) xong
#   1. vé/tour/hoạt động Booking: tối đa 2.500 trang, mỗi đợt 500 (dừng sớm khi hết URL)
#   2. 20 điểm đến nhỏ (@extra) × 40 khách sạn
#   3. đào sâu 8 thành phố lớn (@deep) 100 → 200 khách sạn, KHÔNG cào lại trang đã có (deepen_jobs.py)
# Ngoài khung giờ thì chỉ chờ, không cào. Hết giờ giữa chừng: trang đang mở được cào xong rồi dừng nhận việc mới.
# Dừng hẳn: pkill -INT -f run_extra_queue.sh; pkill -INT -f "batch.py run". Chạy lại cùng lệnh để tiếp tục từ chỗ dừng.
set -u
cd "$(dirname "$0")"
PY="${PYTHON:-$HOME/miniconda3/envs/vsf/bin/python}"
FROM="${FROM:-07:00}"
UNTIL="${UNTIL:-23:00}"
DATES="${DATES:-2026-10-15}"
export DISPLAY="${DISPLAY:-:0}"

log() { echo "[$(date '+%F %T')] $*"; }
in_window() {
  local now=$((10#$(date +%H%M))) from=$((10#${FROM//:/})) until=$((10#${UNTIL//:/}))
  [ "$now" -ge "$from" ] && [ "$now" -lt "$until" ]
}
wait_window() { while ! in_window; do log "ngoài khung giờ $FROM–$UNTIL: chờ (không cào)"; sleep 300; done; }
wait_idle() { while pgrep -f "batch.py run booking-hotels" >/dev/null; do sleep 60; done; }
names() { "$PY" -c "from collectors.plan import select_destinations as s; print('\n'.join(d.name for d in s('$1')))"; }
pending_attractions() {
  "$PY" - <<'PY'
import glob, json, sqlite3
n = 0
for f in glob.glob("data/batches/*/job.json"):
    if json.load(open(f))["source"] == "booking-attractions":
        c = sqlite3.connect(f.replace("job.json", "state/crawl_state.sqlite"))
        n += c.execute("select count(*) from items where status='pending' or (status='failed' and attempts<3)").fetchone()[0]
print(n)
PY
}
hotels() {  # $1 = thành phố, $2 = số khách sạn tối đa
  wait_window
  log "khách sạn Booking: $1 (tối đa $2)"
  "$PY" batch.py run booking-hotels --cities "$1" --per-destination "$2" --dates "$DATES" --fast --concurrency 2 || log "mã thoát $? ($1)"
}

log "hàng đợi cào thêm: khung giờ $FROM–$UNTIL"
wait_idle; sleep 45; wait_idle   # hai lần: khoảng trống ngắn giữa hai lệnh batch.py nối tiếp nhau
log "khách sạn Booking đang chạy đã xong"

for i in 1 2 3 4 5; do
  wait_window
  if [ "$i" -gt 1 ] && [ "$(pending_attractions)" -eq 0 ]; then log "hết URL vé/tour"; break; fi
  log "vé/tour Booking, đợt $i/5 (500 trang)"
  "$PY" batch.py run booking-attractions --limit 500 --fast --concurrency 2 || log "mã thoát $? (vé/tour)"
done

while IFS= read -r city; do hotels "$city" 40; done < <(names @extra)

wait_window
log "đào sâu 8 thành phố lớn: tạo job 200 từ job 100 (không cào lại trang đã có)"
"$PY" deepen_jobs.py --cities @deep --to 200 --dates "$DATES" --apply
while IFS= read -r city; do hotels "$city" 200; done < <(names @deep)

log "hàng đợi cào thêm đã xong. Kiểm tra bằng monitor rồi bấm 'Tạo bản xem trước'."
