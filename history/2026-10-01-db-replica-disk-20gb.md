# Giảm disk mặc định của DB replica xuống 20 GB

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude Sonnet 5.5
- Nhánh: khoa/db-replica-terraform
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng)

## Mục tiêu

Dữ liệu primary chỉ khoảng 156 MB (disk dùng 6.4/49 GB) và WAL của slot bị chặn 2 GB, nên disk replica 50 GB là thừa.

## File thay đổi

- `infra/terraform/environments/staging/variables.tf` — sửa: `disk_size_gb` mặc định 20, mô tả lý do.
- `infra/terraform/environments/staging/staging.tfvars.example` — sửa: ví dụ 20.
- `docs/plan/2026-10-01-db-replica-terraform.md` — sửa: cấu hình và chi phí theo disk 20 GB.

## Quyết định

- Theo yêu cầu của chủ dự án. Biến vẫn có validation tối thiểu 20 GB và có thể tăng trong `staging.tfvars` khi dữ liệu lớn lên.

## Kiểm tra

- `terraform fmt -check` và `terraform validate` cho root staging; `bash ops/tests/test_replica_scripts.sh`.

## Còn lại / rủi ro

- Theo dõi alert disk 90% của replica khi catalog tăng.
