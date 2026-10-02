# Sửa lỗi plan monitoring: output db_replica_alert_policy_ids

- Ngày: 2026-10-01
- Tác giả: người dùng / Claude
- Nhánh: khoa/fix-monitoring-replica-output
- Trạng thái: hoàn thành; chờ merge để workflow apply
- Phạm vi: monitoring

## Mục tiêu

Run `Staging Monitoring Terraform` trên release-mvp-v2 (sau PR #82) dừng ở bước Plan: `Inconsistent conditional result types` tại `outputs.tf`. Apply không bị guard hay quyền chặn — plan lỗi trước khi tới apply.

## File thay đổi

- `infra/monitoring/outputs.tf` — sửa: `db_replica_alert_policy_ids` dùng `merge` của các `for` thay cho `cond ? {object} : {}`.

## Quyết định

- Khi replica VM tồn tại, nhánh true là object 4 key còn nhánh false là `{}` nên Terraform không hợp nhất được kiểu. `merge` của các `for` luôn ra map(string), không cần điều kiện.
- Key `vm` (map lồng) thành các key phẳng `vm_<tên>`; output này chỉ để xem, không có module nào đọc.
- Không động tới guard của workflow infra (`infra-terraform-staging.yml`): nó không liên quan tới lỗi này.

## Kiểm tra

- `terraform fmt -check`, `init -backend=false`, `validate` — PASS.
- `bash infra/monitoring/tests/test_staging_layout.sh` — PASS.
- Chưa chạy plan thật; run workflow sau merge sẽ xác nhận.

## Còn lại / rủi ro

- Plan của run lỗi báo 9 add, 1 change, 0 destroy (metric/alert/widget container disk + replica probe); kiểm tra lại số này ở run mới.
