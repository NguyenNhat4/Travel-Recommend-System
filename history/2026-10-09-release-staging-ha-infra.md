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
- `history/2026-10-09-release-staging-ha-infra.md` — thêm: entry này.

## Quyết định

- Chỉ lấy hạ tầng từ nhánh khoa, không đưa 17 commit còn lại và 42 thay đổi chưa commit. Lý do: state trên bucket `infra/staging-ha` (serial 53) được tạo từ cấu hình khoa.
- Không mở rộng `allowed_changes` trong script ở PR này. Sẽ quyết định sau khi có plan đọc state thật.

## Kiểm tra

- Chưa chạy. Sẽ chạy `terraform plan` read-only với state bucket, cấu hình PR, và image digest từ lượt build gần nhất.

## Còn lại / rủi ro

- Chưa biết plan thật. Nguy cơ cần kiểm tra: cập nhật crawler (metadata ssh-keys), autoscaler (cooldown), và Patroni.
- Chưa được review. Không merge khi chưa có plan đã kiểm tra.
