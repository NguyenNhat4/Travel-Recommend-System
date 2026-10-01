# Staging infra (DB replica VM)

Terraform root cho phần hạ tầng VM do Terraform quản lý. Hiện chỉ tạo VM `db-replica`; mạng dùng các firewall rule sẵn có của VPC `default` (`default-allow-internal`, `default-allow-ssh`). Hai VM tạo tay (app, db-primary) chỉ được đọc bằng `data`, Terraform không sửa chúng. Chi tiết vận hành: `docs/guide/van-hanh-db-replica.md`.

## Triển khai

Hạ tầng đi qua CI/CD, không chạy `terraform apply` từ máy cá nhân. Workflow `.github/workflows/infra-terraform-staging.yml`:

- Pull request: `fmt`, `validate`, test layout. Không chạm GCP.
- Push/merge vào `main`, `release-mvp-v1`, `release-mvp-v2`, `release-mvp-v3` (đổi `infra/terraform/**`): plan, chặn plan có xoá/thay thế, apply. Plan hiện trong Summary của run.
- Chạy tay (`workflow_dispatch`): cùng luồng; đặt `allow_destroy=true` chỉ khi đã xem plan và chấp nhận xoá/thay thế.

Mọi nhánh dùng chung một state (`infra/staging`), nên giữ `infra/terraform` giống nhau giữa các nhánh; nhánh có code cũ sẽ plan xoá resource và bị chặn.

## Kiểm tra cục bộ (không chạm GCP)

```bash
terraform -chdir=infra/terraform/environments/staging fmt -check -recursive
terraform -chdir=infra/terraform/environments/staging init -backend=false
terraform -chdir=infra/terraform/environments/staging validate
bash ops/tests/test_replica_scripts.sh
```

Không commit `staging.tfvars`, `backend.staging.hcl`, state hay plan.
