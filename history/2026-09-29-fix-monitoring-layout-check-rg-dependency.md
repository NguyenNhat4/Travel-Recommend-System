# Sửa CI staging monitoring phụ thuộc ripgrep

- Ngày: 2026-09-29
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/monitoring-system`, `khoa/workflow-pr-push-triggers`
- Trạng thái: hoàn thành
- Phạm vi: DevOps, monitoring, CI/CD

## Mục tiêu

Sửa check layout Terraform thất bại trên GitHub Actions vì runner không cài `rg`.

## File thay đổi

- `infra/monitoring/tests/test_staging_layout.sh` — sửa: dùng `grep` có sẵn trên runner để quét cấu hình staging và xác minh resource.
- `history/2026-09-29-fix-monitoring-layout-check-rg-dependency.md` — thêm: ghi nguyên nhân, thay đổi và kiểm tra.

## Quyết định

- Không thêm cài đặt ripgrep vào workflow; script chỉ cần tìm chuỗi trong file nên dùng `grep`.
- Giữ nguyên tập file Terraform/YAML được rà soát và danh sách resource bắt buộc.

## Kiểm tra

- `PATH=/usr/bin:/bin bash infra/monitoring/tests/test_staging_layout.sh` trước sửa: FAIL do `rg: command not found`.
- `PATH=/usr/bin:/bin bash infra/monitoring/tests/test_staging_layout.sh` sau sửa: PASS; script chạy được khi `rg` không có trong `PATH`.
- `bash -n infra/monitoring/tests/test_staging_layout.sh`: PASS.
- `git diff --check`: PASS.

## Còn lại / rủi ro

- Xác nhận check GitHub Actions mới chạy trên cả hai PR.
