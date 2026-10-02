# Monitoring replica chỉ bật khi VM replica đã tồn tại

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude Sonnet 5.5
- Nhánh: khoa/db-replica-monitoring-optional
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng/CI)
- Thay thế: một phần `2026-10-01-db-replica-terraform.md` (giả định chỉ cần để biến rỗng đến khi có replica)

## Mục tiêu

Sau khi merge PR #69, run `Staging Monitoring Terraform` trên `release-mvp-v2` fail: `instances/vota-staging-db-replica not found`. Biến GitHub `GCE_DB_REPLICA_INSTANCE` đã được đặt trong khi VM replica chưa tạo, nên `data.google_compute_instance.db_replica[0]` tra một VM không có và làm hỏng plan.

## File thay đổi

- `.github/workflows/monitoring-terraform-staging.yml` — sửa: bước `setup-gcloud` và bước kiểm VM tồn tại; chỉ khi có mới đặt `TF_VAR_db_replica_vm_name`, ngược lại cảnh báo và bỏ qua monitoring replica.
- `infra/monitoring/variables.tf` — sửa: mô tả biến.
- `docs/guide/van-hanh-db-replica.md` — sửa: ghi hành vi mới.

## Quyết định

- Provider `hashicorp/google` không có data source số nhiều `google_compute_instances` (thử và validate báo lỗi), nên không thể tra "mềm" bằng Terraform. Kiểm bằng `gcloud compute instances describe` trong workflow, giữ Terraform đơn giản và không thêm provider.
- Zone lấy từ secret `GCE_ZONE`, mặc định `asia-southeast1-a`.
- Không gỡ biến GitHub: không cần nữa. Alert replica tự bật ở lần chạy sau khi VM xuất hiện.

## Kiểm tra

- Phân tích YAML workflow: pass. `terraform validate` cho `infra/monitoring` không đổi cấu trúc.
- Chưa kiểm được trên CI thật; cần chạy lại workflow trên `release-mvp-v2` sau khi merge: kỳ vọng plan thành công và có cảnh báo "Replica VM ... not found".

## Còn lại / rủi ro

- `google-github-actions/setup-gcloud` cần quyền `compute.instances.get` của service account CI; thiếu quyền thì `describe` thất bại và monitoring replica bị bỏ qua (kèm cảnh báo, plan không hỏng).
