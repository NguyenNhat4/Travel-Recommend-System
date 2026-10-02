# Staging infra (VM, địa chỉ, firewall)

Terraform root cho hạ tầng VM của staging. Quản lý:

| File | Nội dung |
|---|---|
| `primary.tf` | VM DB primary `v-ota-db-dev` (nhận từ VM dựng tay bằng `import`) |
| `app.tf` | VM Docker `vota-backend-crawler-recsys` (nhận từ VM dựng tay) |
| `main.tf` | VM `db-replica` (do Terraform tạo) |
| `addresses.tf` | IP nội bộ và IP ngoài của app, đặt thành static, giữ nguyên giá trị đang dùng |
| `firewall.tf` | Các rule `vota-*` sẵn có (nhận nguyên trạng) |
| `imports.tf` | `import` block cho các resource dựng tay |

Chi tiết vận hành replica: `docs/guide/van-hanh-db-replica.md`.

## Quy tắc an toàn cho VM primary và app

Hai VM này đang chạy thật, nên Terraform chỉ được đổi chúng theo cách không dừng và không tạo lại:

- `prevent_destroy` và `deletion_protection = true`: không xoá được cả từ Terraform lẫn GCP.
- Không đặt `allow_stopping_for_update`: thay đổi nào cần dừng VM sẽ lỗi lúc apply thay vì tự tắt DB.
- `ignore_changes` gồm `metadata` (chứa `ssh-keys` mà người và CI tự thêm), `labels` và `boot_disk`.
- `key_revocation_action_type = "NONE"` khớp giá trị thật; bỏ dòng này Terraform sẽ đòi tạo lại VM.
- IP nội bộ của primary (`10.148.0.2`) và app (`10.148.0.3`) bị tunnel `vota-db-tunnel.service`, `pg_hba` của primary và `known_hosts` phụ thuộc; IP ngoài của app được DuckDNS trỏ vào. Vì vậy chúng được đặt static.
- Disk của primary đã có lịch snapshot hằng ngày `default-schedule-1` (giữ 14 ngày), nằm ngoài Terraform.

## Triển khai

Hạ tầng đi qua CI/CD, không chạy `terraform apply` từ máy cá nhân. Workflow `.github/workflows/infra-terraform-staging.yml`:

- Pull request: `fmt`, `validate`, test layout. Không chạm GCP.
- Push/merge vào `main`, `release-mvp-v1`, `release-mvp-v2`, `release-mvp-v3` (đổi `infra/terraform/**`): plan, hai bước chặn, apply. Plan hiện trong Summary của run.
  - Chặn plan có xoá hoặc thay thế (trừ khi chạy tay với `allow_destroy=true`).
  - Chặn plan có cập nhật tại chỗ VM primary hoặc app (trừ khi chạy tay với `allow_vm_update=true`). Khi cho qua, CI chụp snapshot disk primary (`pre-apply-<run>`) trước khi apply.
- Cho qua một plan bị chặn, sau khi đã đọc plan: đặt biến Environment `staging` `INFRA_ALLOW_VM_UPDATE=true` (hoặc `INFRA_ALLOW_DESTROY=true`) rồi **Re-run** run bị chặn trên GitHub (Actions → run → Re-run failed jobs); xong xoá biến. Re-run dùng file workflow của đúng nhánh. Dispatch (`workflow_dispatch`, input `allow_vm_update`/`allow_destroy`) chỉ dùng được khi file workflow đã có trên nhánh mặc định `main`.

Mọi nhánh dùng chung một state (`infra/staging`), nên giữ `infra/terraform` giống nhau giữa các nhánh; nhánh có code cũ sẽ plan xoá resource và bị chặn.

Biến cần có ở GitHub Environment `staging`: `GCE_DB_INSTANCE`, `GCE_APP_INSTANCE`. Secrets: `GCP_PROJECT_ID`, `GCE_ZONE`, `TF_STATE_BUCKET`, `GCP_WIF_PROVIDER`, `GCP_CI_SERVICE_ACCOUNT`. Service account của CI cần thêm `roles/compute.networkAdmin` để giữ chỗ địa chỉ ngoài.

## Kiểm tra cục bộ

```bash
terraform -chdir=infra/terraform/environments/staging fmt -check -recursive
terraform -chdir=infra/terraform/environments/staging init -backend=false
terraform -chdir=infra/terraform/environments/staging validate
bash ops/tests/test_infra_layout.sh
```

Xem trước plan với state thật (chỉ đọc), cần `backend.staging.hcl` và `staging.tfvars` cục bộ:

```bash
terraform -chdir=infra/terraform/environments/staging init -backend-config=backend.staging.hcl
terraform -chdir=infra/terraform/environments/staging plan -var-file=staging.tfvars
```

Plan đúng phải có `0 to destroy` và không có dòng `-/+`.

Không commit `staging.tfvars`, `backend.staging.hcl`, state hay plan.
