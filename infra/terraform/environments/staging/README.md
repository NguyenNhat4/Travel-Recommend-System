# Staging infra (DB replica VM)

Terraform root cho phần hạ tầng VM do Terraform quản lý. Hiện chỉ tạo VM `db-replica` và 2 firewall rule. Hai VM tạo tay (app, db-primary) chỉ được đọc bằng `data`, Terraform không sửa chúng. Chi tiết vận hành: `docs/guide/van-hanh-db-replica.md`.

```bash
cp staging.tfvars.example staging.tfvars            # điền project, tên VM
cp backend.staging.hcl.example backend.staging.hcl  # điền bucket state
terraform init -backend-config=backend.staging.hcl
terraform plan -var-file=staging.tfvars
terraform apply -var-file=staging.tfvars
```

Không commit `staging.tfvars`, `backend.staging.hcl`, state hay plan. State dùng prefix `infra/staging`, tách khỏi `infra/monitoring`.

Kiểm tra cục bộ: `terraform fmt -check -recursive && terraform init -backend=false && terraform validate` và `bash ops/tests/test_replica_scripts.sh` từ gốc repo.
