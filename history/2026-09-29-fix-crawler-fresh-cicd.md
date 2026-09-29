# Chuyển crawler CD sang job fresh và image bất biến

- Ngày: 2026-09-29
- Tác giả: người dùng / Codex
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành phần source, chờ chạy GitHub Actions và VM
- Phạm vi: ci, data

## Mục tiêu

Đồng bộ CD với job crawler mới `fresh_catalog.py` và `Dockerfile.fresh-catalog`, tránh việc mỗi lần deploy lại cài cron legacy `daily.py`.

## File thay đổi

- `.github/workflows/crawler-ci-cd.yml` — trigger thêm Dockerfile fresh; build/publish fresh image; cài `--job fresh`; khởi động `fresh-monitor`; truyền image digest bất biến.
- `scripts/install-vota-cron.sh` — nhận image reference `@sha256:<digest>` bên cạnh `:latest` để cron giữ đúng artifact deploy.
- `scripts/tests/test-install-vota-cron.sh` — thêm regression test cho digest image.
- `history/2026-09-29-fix-crawler-fresh-cicd.md` — ghi lịch sử thay đổi.

## Quyết định

- CD dùng secret `GAR_FRESH_IMAGE` và mặc định các đường dẫn fresh: `/srv/vota/fresh-catalog-data`, `/etc/vota/fresh-catalog.env`, `/srv/vota/fresh-catalog-logs`.
- Publish vẫn tạo tag SHA và `latest`, nhưng deploy/cron/monitor dùng digest output của bước publish.
- Legacy monitor được dừng khi chuyển sang fresh để tránh xung đột cổng 8765; rollback thủ công vẫn được giữ qua `--job legacy` và image `:latest`.

## Kiểm tra

- `bash scripts/tests/test-install-vota-cron.sh` — PASS.
- `bash -n scripts/check-db-tunnel.sh scripts/install-vota-cron.sh src/data_collection/run_daily_docker.sh` — PASS.
- PyYAML parse `.github/workflows/crawler-ci-cd.yml` — PASS.
- `git diff --check` — PASS.
- GitHub Actions publish/deploy thật và VM runtime — chưa chạy trong phiên này.

## Còn lại / rủi ro

- Phải tạo `GAR_FRESH_IMAGE` trong GitHub Environment `staging` trước khi chạy CD.
- VM phải có `fresh-catalog.env`, volume fresh đúng UID/GID và runner có thể chạy bằng user OS Login.
- Cần kiểm tra thực tế `crontab`, container monitor, một lượt `fresh-run` và báo cáo crawler sau lần deploy đầu tiên.
