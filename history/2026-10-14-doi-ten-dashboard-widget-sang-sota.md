# Đổi tên dashboard và widget monitoring sang SOTA

- Ngày: 2026-10-14
- Tác giả: người yêu cầu / [CC]
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: infra

## Mục tiêu

Đổi tên hiển thị của các dashboard monitoring staging-ha từ tiền tố `vota` sang `sota`, không đổi resource ID, metric, filter log hay cấu hình cảnh báo.

## File thay đổi

- `infra/terraform/environments/staging-ha/dashboard.tf` — dùng tiền tố hiển thị `sota HA` cho tên dashboard và các liên kết/mô tả liên quan.
- `infra/terraform/environments/staging-ha/tests/test_dashboard.py` — thêm kiểm tra tiền tố hiển thị SOTA.

## Quyết định

- Chỉ đổi tên hiển thị; giữ `var.name_prefix` cho tên hạ tầng, resource Terraform và metric để tránh tạo lại tài nguyên hoặc làm mất dữ liệu monitoring.

## Kiểm tra

- `python3 infra/terraform/environments/staging-ha/tests/test_dashboard.py` — chưa chạy sau thay đổi.

## Còn lại / rủi ro

- Cần chạy workflow `Staging-HA Infra CD` để áp dụng tên mới lên GCP staging-ha.
