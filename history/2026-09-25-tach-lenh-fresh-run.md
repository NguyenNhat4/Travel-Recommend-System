# Giữ `run` là job daily.py, job cào mới chuyển sang `fresh-run`

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, deployment

## Mục tiêu

CI/CD của team deploy trên `release-mvp-v1` (`.github/workflows/backend-ci-cd.yml`, `scripts/deploy-backend-vm.sh`,
`scripts/install-vota-cron.sh`, thiết kế `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md`) build image từ
`Dockerfile.daily`, chép `run_daily_docker.sh` từ nhánh được deploy lên `/opt/vota/bin/` và cài cron
`IMAGE=… DATA_DIR=/srv/vota/daily-data ENV_FILE=/etc/vota/daily.env … run_daily_docker.sh run`. Trên nhánh này `run` đã là
job cào mới nên khi nhánh lên release, cron đó sẽ gọi job mới bằng cấu hình của job cũ và dừng ngay. Người dùng chọn
cách (b): giữ `run` là job cũ, job mới chuyển sang lệnh riêng, team đổi cron khi sẵn sàng.

## File thay đổi

- `src/data_collection/run_daily_docker.sh` — sửa: `run` gọi lại `cmd_legacy_run` (giống hệt `cmd_run` trên release);
  `legacy-run` giữ làm tên khác; job mới ở `fresh-run [auto|full|daily|index|status]` (`cmd_fresh_run`); phần hướng dẫn
  đầu file.
- `src/data_collection/run_fresh_catalog_vm.sh` — sửa: wrapper chuyển tới `fresh-run` (kéo theo `cron_hotels_daily.sh`).
- `src/data_collection/README.md` — sửa: lệnh của job mới dùng `fresh-run`; ghi rõ `run` là job daily.py của cron CI/CD,
  chuyển VM sang job mới là thay dòng cron đó bằng `fresh-run auto`.
- `src/data_collection/.env.example` — sửa: ghi chú bước index của job mới dùng `fresh-run`.
- `history/2026-09-25-tach-lenh-fresh-run.md` — thêm: entry này.

## Quyết định

- `run` không nhận tham số, như trên release, để dòng cron hiện có của CI/CD chạy y như cũ.
- Không lên lịch hai job cho cùng DB: cả hai cùng ghi `cdp.products` và đè giá của nhau. Muốn chạy job mới trên VM, team
  phải build/push `Dockerfile.fresh-catalog`, tạo `/srv/vota/fresh-catalog-data` (UID 10001) và
  `/etc/vota/fresh-catalog.env`, rồi thay dòng cron do `install-vota-cron.sh` quản lý (hiện gắn cứng `run`).

## Kiểm tra

- So `cmd_run` của `origin/release-mvp-v1` với `cmd_legacy_run`: giống hệt.
- `run` với `DATA_DIR` chưa init: log ghi đúng lỗi của job cũ ("chưa có …/interim — chạy trước: … init"), mã 1.
- `fresh-run status`: in lượt gần nhất và `Next run … parallel sites (full): 2`, mã 0; `fresh-run weekly`: báo mode hợp lệ,
  mã 1; `run_fresh_catalog_vm.sh status` chuyển đúng tới `fresh-run`. `bash -n` hai script: sạch.

## Còn lại / rủi ro

- Job mới chưa chạy trên VM cho tới khi team làm các bước ở mục Quyết định.
