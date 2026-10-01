# Hạ tầng Terraform apply tự động qua CI/CD

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude Sonnet 5.5
- Nhánh: khoa/infra-terraform-auto-apply
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng/CI)
- Thay thế: một phần `2026-10-01-db-replica-terraform.md` (apply chỉ chạy tay, `apply=false` mặc định)

## Mục tiêu

Chủ dự án chuyển toàn bộ hạ tầng sang code và triển khai tự động qua CI/CD, không chạy tay nữa. VM `vota-staging-db-replica` đã được tạo bằng apply tay lần đầu (state `infra/staging`).

## File thay đổi

- `.github/workflows/infra-terraform-staging.yml` — sửa: push/merge vào nhánh release tự plan, in plan vào Summary, chặn plan có delete/replace, rồi apply; dispatch chỉ còn input `allow_destroy`.
- `ops/tests/test_replica_scripts.sh` — sửa: kiểm có guard và bước apply.
- `infra/terraform/environments/staging/README.md`, `docs/guide/van-hanh-db-replica.md`, `docs/plan/2026-10-01-db-replica-terraform.md` — sửa: CI/CD là đường triển khai duy nhất.

## Quyết định

- Chốt chặn thay cho review tay: plan có `delete` (gồm replace) bị chặn, vì VM replica giữ dữ liệu trên boot disk; muốn xoá/thay thế phải dispatch tay với `allow_destroy=true`. Guard kiểm bằng `terraform show -json` và `jq`.
- PR chỉ validate (giống workflow monitoring) để không phụ thuộc điều kiện WIF cho plan trên PR.
- Mọi nhánh dùng chung một state; nhánh có code cũ sẽ plan xoá và bị guard chặn.
- Không thêm `prevent_destroy` để thay đổi có chủ đích vẫn đi qua CI.

## Kiểm tra

- Phân tích YAML, `bash ops/tests/test_replica_scripts.sh`: pass. Guard `jq` thử với plan giả: bắt đúng `delete,create`, bỏ qua `create`.
- Chưa chạy trên CI thật.

## Còn lại / rủi ro

- Service account CI `github-ci-cd-v-ota-backend` hiện KHÔNG có `roles/compute.instanceAdmin.v1` và không có `roles/iam.serviceAccountUser` trên service account của VM, nên apply có thay đổi VM sẽ bị `403`. Run đầu sau merge là no-op nên vẫn xanh; thay đổi đầu tiên mới lộ lỗi. Cần cấp quyền trước.
- Nên bật Required reviewers cho Environment `staging` nếu muốn có người duyệt trước apply.
