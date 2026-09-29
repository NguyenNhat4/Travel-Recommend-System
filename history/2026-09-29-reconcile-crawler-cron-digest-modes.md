# Giữ chế độ crawler khi pin cron theo image digest

- Ngày: 2026-09-29
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/workflow-pr-push-triggers`
- Trạng thái: hoàn thành phần source và kiểm tra local; chờ GitHub Actions xác nhận
- Phạm vi: DevOps, CI/CD

## Mục tiêu

Đồng bộ PR với thay đổi mới trong `release-mvp-v2` mà không làm mất chế độ lên lịch crawler `legacy`/`fresh`, đồng thời giữ cron dùng image digest đã pull trong lúc credential còn hạn.

## File thay đổi

- `scripts/install-vota-cron.sh` — sửa: hợp nhất `--job legacy|fresh` với image digest và `PULL=0` cho cả hai job.
- `scripts/tests/test-backend-vm-cd-sync.sh` — sửa: kiểm tra cron fresh được giữ và dùng image digest đã có.
- `history/2026-09-29-reconcile-crawler-cron-digest-modes.md` — thêm: ghi nhận cách giải quyết và kiểm tra.

## Quyết định

- Giữ cả hai chế độ crawler từ base; mặc định CI tiếp tục dùng legacy khi không truyền `--job`.
- Không để cron kéo lại image: deploy pull digest trước; cron legacy/fresh đều dùng đúng image đã có trên VM.

## Kiểm tra

- Regression check mới trước khi hợp nhất script: FAIL tại assertion fresh cron như dự kiến.
- `bash -n infra/monitoring/tests/test_staging_layout.sh scripts/install-vota-cron.sh scripts/tests/test-backend-vm-cd-sync.sh` — PASS.
- `PATH=/usr/bin:/bin bash infra/monitoring/tests/test_staging_layout.sh` — PASS, không cần `rg`.
- `bash scripts/tests/test-backend-vm-cd-sync.sh` — PASS.
- Chạy script với fixture `/dev/null` ở chế độ dry-run cho legacy và fresh: PASS, cả hai đều ghi `PULL=0`.
- `git diff --check` — PASS.

## Còn lại / rủi ro

- Chờ workflow `Validate monitoring Terraform` chạy lại trên PR #43; chưa có runtime deploy crawler.
