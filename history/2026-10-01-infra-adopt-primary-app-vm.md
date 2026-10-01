# Đưa VM primary, VM app, địa chỉ và firewall vào Terraform

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude
- Nhánh: khoa/infra-adopt-vms
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng, CI/CD)

## Mục tiêu

Toàn bộ hạ tầng staging nằm trong code. Trước đó Terraform chỉ tạo VM replica, còn VM primary (`v-ota-db-dev`) và VM app đọc qua data source. PR này nhận hai VM đó vào state bằng `import` mà không dừng, không tạo lại, không đổi cấu hình thật. Là bước 1 trong 2 bước (bước 2: workflow nối replication).

## File thay đổi

- `infra/terraform/environments/staging/primary.tf` — thêm: VM primary, `prevent_destroy`, `deletion_protection`, `ignore_changes`.
- `infra/terraform/environments/staging/app.tf` — thêm: VM app, cùng quy tắc an toàn.
- `infra/terraform/environments/staging/addresses.tf` — thêm: giữ chỗ 3 IP nội bộ và IP ngoài của app (giá trị đang dùng).
- `infra/terraform/environments/staging/firewall.tf` — thêm: các rule `vota-*` sẵn có, nhận nguyên trạng.
- `infra/terraform/environments/staging/imports.tf` — thêm: `import` block cho 2 VM và 4 firewall rule.
- `infra/terraform/environments/staging/data.tf` — xóa: primary là resource, không còn data source.
- `infra/terraform/environments/staging/main.tf` — sửa: replica dùng IP static, bật OS Login, đọc SA từ primary.
- `infra/terraform/environments/staging/variables.tf` — sửa: thêm `app_vm_name`, `app_service_account_email`.
- `infra/terraform/environments/staging/outputs.tf` — sửa: thêm output app và primary.
- `infra/terraform/environments/staging/versions.tf` — sửa: Terraform `>= 1.9`.
- `infra/terraform/environments/staging/staging.tfvars.example` — sửa: thêm `app_vm_name`.
- `infra/terraform/environments/staging/README.md` — sửa: mô tả lại theo phạm vi mới.
- `.github/workflows/infra-terraform-staging.yml` — sửa: Terraform 1.9, biến `GCE_APP_INSTANCE`, bước chặn update VM primary/app (`allow_vm_update`), snapshot disk primary trước khi apply.
- `ops/tests/test_replica_scripts.sh` — đổi tên thành `ops/tests/test_infra_layout.sh` và mở rộng kiểm tra bảo vệ VM, địa chỉ static, file không được commit.

## Quyết định

- Nhận VM bằng `import`, không tạo lại: VM đang chạy DB và app thật.
- `ignore_changes` gồm `metadata`: chứa `ssh-keys` mà người và CI tự thêm; tunnel app→DB đang phụ thuộc SSH vào primary. Primary không bật OS Login vì sẽ làm tunnel đứt.
- Không đặt `allow_stopping_for_update` trên primary và app để thay đổi cần dừng VM bị lỗi thay vì tự tắt.
- Đặt IP static cho các IP đang dùng: tunnel, `pg_hba` và DNS phụ thuộc chúng; các IP hiện đều ephemeral.
- Không tạo snapshot policy mới: disk đã có `default-schedule-1` (hằng ngày, giữ 14 ngày).
- Firewall 8000 và 8765 đã giới hạn theo service account của VM app nên không mở trên VM DB; chỉ nhận nguyên trạng, không dọn rule trùng ở đợt này.
- Chặn `update` trên hai VM trừ khi chạy tay có `allow_vm_update=true`, vì lần apply đầu có cập nhật `deletion_protection` và cần người đọc plan.

## Kiểm tra

- `terraform validate`: Success.
- `terraform fmt -check -recursive`: pass.
- `bash ops/tests/test_infra_layout.sh`: PASS.
- `terraform plan` cục bộ với state thật (chỉ đọc): 6 to import, 4 to add, 3 to change, 0 to destroy. Ba thay đổi: `deletion_protection` của primary và app, metadata `enable-oslogin` của replica. Lần đầu thiếu `key_revocation_action_type` khiến plan đòi thay thế 2 VM; đã sửa.
- Chưa apply. Chưa chạy workflow trên GitHub.

## Còn lại / rủi ro

- Cấp `roles/compute.networkAdmin` cho service account CI (cần để giữ chỗ địa chỉ ngoài).
- Sau merge, lần push đầu sẽ bị chặn bởi bước update VM; đọc plan rồi chạy tay workflow với `allow_vm_update=true`.
- Bước 2: workflow nối replication primary/replica (`db-replication-staging.yml`).
- Dọn rule firewall trùng `vota-public-backend-8000` và `default-allow-rdp` để sau.
- `vota-db-tunnel.service` và `/etc/vota/backend.env` trên VM app vẫn dựng tay.
