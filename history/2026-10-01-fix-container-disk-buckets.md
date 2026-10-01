# Sửa metric container disk: giới hạn bucket và race tạo alert

- Ngày: 2026-10-01
- Tác giả: người dùng / Claude
- Nhánh: khoa/fix-container-disk-buckets
- Trạng thái: hoàn thành; chờ merge để workflow apply lại
- Phạm vi: monitoring

## Mục tiêu

Apply staging monitoring lỗi: (1) `Number of buckets exceeds 200` khi tạo `staging_container_disk_bytes`; (2) alert policy 404 vì metric log vừa tạo chưa dùng được.

## File thay đổi

- `infra/monitoring/main.tf` — sửa: `num_finite_buckets` 240 → 200 (giới hạn của Cloud Logging); thêm `terraform_data.container_disk_metric_ready` (sleep 180s) làm `depends_on` cho alert `staging_container_disk`.

## Quyết định

- 200 bucket × tăng 10% vẫn phủ tới hàng trăm TB, độ chính xác không đổi.
- Chờ bằng `terraform_data` + local-exec (có sẵn trong Terraform, không thêm provider/lock file).
- Hai alert replica 404 trong run lỗi không cần sửa code: metric của chúng đã tạo xong, run kế tiếp sẽ qua.

## Kiểm tra

- `terraform fmt -check`, `validate` — PASS; layout test — PASS.
- Chưa plan/apply thật; xác nhận qua run workflow sau merge.

## Còn lại / rủi ro

- Nếu alert vẫn 404 (metric chậm hơn 180s), chạy lại job.
