#!/usr/bin/env bash
# Dừng êm mọi tiến trình cào (Booking, Agoda, Trip, hàng đợi nền). Tiến độ đã lưu trong data/batches/<job>/state:
# chạy lại đúng lệnh cũ là tiếp tục từ chỗ dừng. Sau đó có thể chạy ./finalize_catalog.sh.
#
# Lưu ý: nếu bạn đang chạy các lệnh dạng `while pgrep ...; do sleep 60; done; batch.py ...` trong một tab terminal (vòng chờ tự bắt
# đầu nguồn khác khi nguồn trước xong), hãy Ctrl-C tab đó TRƯỚC khi chạy script này, nếu không nó sẽ bắt đầu ngay khi nguồn kia dừng.
set -u
echo "1. Hàng đợi nền (chạy bằng nohup nên bỏ qua SIGINT → dùng SIGTERM)"
pkill -TERM -f "run_extra_queue.sh" && echo "   đã dừng hàng đợi nền" || echo "   không có hàng đợi nền"
echo "2. batch.py / crawl.py (SIGINT: crawl.py lưu tiến độ rồi thoát, đóng trình duyệt)"
pkill -INT -f "python.*batch\.py run" && echo "   đã gửi SIGINT tới batch.py" || echo "   không có batch.py"
pkill -INT -f "python.*crawl\.py --data-dir" && echo "   đã gửi SIGINT tới crawl.py" || echo "   không có crawl.py"
for i in $(seq 1 30); do
  pgrep -f "python.*(batch\.py run|crawl\.py --data-dir)" >/dev/null || break
  sleep 2
done
if pgrep -fa "python.*(batch\.py run|crawl\.py --data-dir)" >/dev/null; then
  echo "Còn tiến trình chưa thoát:"; pgrep -fa "python.*(batch\.py run|crawl\.py --data-dir)" | cut -c1-150
else
  echo "Mọi tiến trình cào đã dừng."
fi
