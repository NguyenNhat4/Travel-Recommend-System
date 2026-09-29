# Đồng bộ regression test cron với chế độ pull của CD

- Ngày: 2026-09-29
- Tác giả: người dùng / Codex
- Nhánh: khoa/cd-for-new-crawler
- Trạng thái: hoàn thành
- Phạm vi: ci

## Mục tiêu

Sửa lỗi GitHub Actions ở bước `test-install-vota-cron.sh`: test kỳ vọng `PULL=1` nhưng script hiện hành pin image digest trước khi cài cron và ghi `PULL=0`.

## File thay đổi

- `scripts/tests/test-install-vota-cron.sh` — cập nhật expected line cho legacy, fresh và digest image từ `PULL=1` thành `PULL=0`.
- `scripts/tests/test-backend-vm-cd-sync.sh` — cập nhật assertion theo biến trung gian `crawler_ref` của workflow.
- `history/2026-09-29-fix-crawler-cron-test-pull-mode.md` — ghi lịch sử regression fix.

## Quyết định

Giữ `PULL=0`: bước deploy đã `docker pull` image digest trước khi cài cron; cron không tự pull lại bằng credential có thể hết hạn.

## Kiểm tra

- `bash scripts/tests/test-install-vota-cron.sh` — PASS.
- `bash -n scripts/check-db-tunnel.sh scripts/install-vota-cron.sh src/data_collection/run_daily_docker.sh` — PASS.
- `bash scripts/tests/test-backend-vm-cd-sync.sh` — PASS.

## Còn lại / rủi ro

- Chưa chạy lại GitHub Actions thật trong phiên này.
