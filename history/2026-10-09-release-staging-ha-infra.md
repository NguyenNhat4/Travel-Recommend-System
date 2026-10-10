# Đưa hạ tầng staging-HA vào release-mvp-v2

- Ngày: 2026-10-09
- Tác giả: Khoa15 / Claude Code (Haiku 5.5)
- Nhánh: pr/release-staging-ha-infra
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

`release-mvp-v2` thiếu cấu hình Terraform staging-HA (không có `backend "gcs"`, không có crawler). Workflow CD trên release truyền `-backend-config` nhưng Terraform bỏ qua vì không có khối backend, nên state không đọc từ bucket. PR này đưa thư mục `infra/terraform/environments/staging-ha` từ `khoa/ha-runtime-bootstrap-fix` (commit `HEAD` tại thời điểm tạo PR) vào release. Workflow `staging-ha-*-cd.yml` và `scripts/deploy-staging-ha-app.sh` của release giữ nguyên.

## File thay đổi

- `infra/terraform/environments/staging-ha/*` — sửa: lấy từ nhánh khoa (backend.tf, crawler, Patroni, startup, tests, variables, tfvars.example).
- `infra/terraform/environments/staging-ha/crawler.tf` — sửa: `lifecycle.ignore_changes = [metadata["ssh-keys"]]`, vì key SSH của runner CD nằm ngoài Terraform.
- `scripts/deploy-staging-ha-app.sh` — sửa: thêm `google_compute_region_autoscaler.app|update` vào `allowed_changes` (cooldown 300 → 360).
- `history/2026-10-09-release-staging-ha-infra.md` — thêm: entry này.

## Quyết định

- Chỉ lấy hạ tầng từ nhánh khoa, không đưa 17 commit còn lại và 42 thay đổi chưa commit. Lý do: state trên bucket `infra/staging-ha` (serial 53) được tạo từ cấu hình khoa.
- Không mở rộng `allowed_changes` trong script ở PR này. Sẽ quyết định sau khi có plan đọc state thật.

## Kiểm tra

- `terraform init` + `terraform plan` read-only (`-lock=false`, không apply, không ghi state) với state `gs://vinpearl-508801-staging-tfstate/infra/staging-ha`, tfvars local, digest backend `c34c8fe8…` và frontend `95e1adce…`.
- Kết quả: `Plan: 1 to add, 2 to change, 1 to destroy`. Thay đổi: `google_compute_instance_template.app` (replace), `google_compute_region_instance_group_manager.app` (update), `google_compute_region_autoscaler.app` (update). Đều nằm trong `allowed_changes`.
- Trước khi sửa, plan còn muốn xóa crawler, monitor, LB origin HTTPS và xóa `ssh-keys` của crawler; đã xử lý bằng cách đồng bộ cấu hình với cây làm việc và `ignore_changes`.

## Còn lại / rủi ro

- Chưa merge PR. Workflow CD đọc cấu hình từ `release-mvp-v2`, nên phải merge trước khi dispatch backend/frontend/crawler.
- Dispatch backend (`staging-ha-app`) và frontend chỉ sau khi merge. Migration `0009` đã áp lên staging ngày 2026-10-09.
- Chưa được review. Không merge khi chưa có plan đã kiểm tra.
