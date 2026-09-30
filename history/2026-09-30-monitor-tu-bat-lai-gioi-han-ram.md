# Monitor chạy nền, tự bật lại, giới hạn RAM

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu: "link http://34.142.132.251:8765/ bị fail, khả năng có ngừoi push code mới ?"; "monitor có 2cpu và 4gm ram";
đồng ý ("ok") làm cách 1: monitor tự bật lại. `docs/prd/deployment-plan.md` §5 (monitor job cào); không lệch PRD.

## File thay đổi

- `src/data_collection/run_daily_docker.sh` — sửa: `fresh-monitor` mặc định `docker run -d --restart unless-stopped
  --memory 1g`, xoay log (10 MB × 3), xoá container cũ cùng tên trước khi chạy; `MONITOR_RESTART` (no | on-failure | always |
  unless-stopped; `no` = tiền cảnh `--rm` như cũ), `MONITOR_MEMORY`.
- `src/data_collection/tests/test_runner_fresh_monitor.py` — thêm: 3 test (docker giả).
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: mục Monitor (chạy nền / tự bật lại), cách chẩn đoán cổng 8765 từ chối,
  swap, chạy lại CD.
- `src/data_collection/README.md` — sửa: mô tả `fresh-monitor`.
- `history/2026-09-30-monitor-tu-bat-lai-gioi-han-ram.md` — thêm: entry này.

## Quyết định

- Chẩn đoán 30/09 ~15:45–15:55 (giờ VN): cổng 8765 từ chối kết nối ngay (không phải firewall hết giờ); cổng 80/443 mở. Monitor
  đã tắt trước khi CD của PR #56 (`feat/booking`, merge 15:42) tới bước deploy; CD deploy thành công nhưng monitor lại tắt
  sau đó. Code monitor của `release-mvp-v2` chạy bình thường ở local (HTTP 200). Deploy backend không đụng container monitor.
  Nghi hết RAM (VM 2 CPU / 4 GB; backend PR #55 deploy 15:16, PR #56 deploy backend + crawler cùng lúc) — chưa xác nhận vì
  không có quyền VM; lệnh kiểm ghi trong guide.
- Sửa trong runner (phần data), CD của team gọi đúng lệnh `fresh-monitor` nên không sửa workflow. Bước chờ "running" 30 giây
  của CD vẫn đúng vì `docker run -d` trả về ngay.

## Kiểm tra

- `test_runner_fresh_monitor.py`: 3 passed.
- Docker thật, image local `vota-fresh-catalog:simbiz-check`: runner tạo container `restart=unless-stopped`,
  `memory=1073741824`, HTTP 200; giết tiến trình `monitor.py` trong container → `restartCount=1`, HTTP 200 trở lại. Container thử
  đã xoá.
- `bash -n run_daily_docker.sh`: ok.

## Còn lại / rủi ro

- Monitor trên VM hiện vẫn tắt: có hiệu lực sau khi merge vào nhánh CD (CD tự khởi động lại bằng runner mới) hoặc chạy lại
  workflow. Nên thêm swap / nâng RAM (cần quyền VM). Chưa commit.
