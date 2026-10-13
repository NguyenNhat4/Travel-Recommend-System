# CD tự động lên staging-ha (MIG) song song với staging cũ

- Ngày: 2026-10-09
- Người đề xuất: người dùng / Claude (agent)
- Trạng thái: từ chối
- Chốt bởi / ngày: hp09.com@gmail.com, 2026-10-13 — bị thay thế bởi `update-archive/2026-10-13-ngung-ci-cd-staging-cu.md` (CD staging-ha đã làm theo hướng khác; CD staging cũ bị gỡ, không giữ song song)
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §1.1 (câu "các workflow CI/CD ứng dụng và crawler cũng không bị sửa trong phạm vi này"), §6.1 (quy trình phát hành chỉ mô tả một VM)
- Mã FR/NFR: NFR-REL-02 (kế thừa), NFR-PERF-01; mới — cần cấp mã nếu muốn ghi quy trình phát hành HA vào `requirements.md`

## Lý do

Hiện mọi workflow CD (`backend-ci-cd.yml`, `frontend-ci-cd.yml`) chỉ deploy lên một VM staging cũ qua secret `GCE_INSTANCE`, và chạy `deploy-backend-vm.sh` / `deploy-frontend-vm.sh` tại chỗ. Cụm `staging-ha` (MIG 1–2 VM app, LB HTTPS, Patroni) không nhận bản build nào từ CI: image của nó đang ghim bằng biến Terraform `backend_image` / `frontend_image`, phải sửa tay rồi chạy rolling update. Vì vậy mỗi lần merge không đưa code mới lên HA, và rủi ro lệch phiên bản giữa hai môi trường tăng dần.

Đề xuất bổ sung một luồng CD riêng cho `staging-ha`, không thay thế luồng staging cũ.

## Nội dung đề xuất

Đoạn hiện tại (`deployment-plan.md` §1.1):

> `staging-ha` là Terraform root và state riêng (`infra/staging-ha`), tách khỏi root/state `infra/staging`. Vì hai root có state khác nhau, thay đổi Patroni không làm thay đổi tài nguyên do workflow `infra-terraform-staging.yml` quản lý; các workflow CI/CD ứng dụng và crawler cũng không bị sửa trong phạm vi này.

Đoạn thay thế đề xuất:

> `staging-ha` có một workflow CD riêng (`staging-ha-cd.yml`). Workflow dùng digest image do job publish của Backend và Frontend tạo ra, đưa digest vào Terraform root `staging-ha` (`backend_image`, `frontend_image`), chạy plan rồi apply sau khi environment `staging-ha` được duyệt. MIG thay VM theo rolling update (`max_surge` 3, `max_unavailable` 0, `min_ready_sec` = `boot_to_ready_seconds`). Sau apply, workflow kiểm `/health/ready` qua load balancer và số VM tối thiểu. Workflow CD staging cũ giữ nguyên; hai luồng không dùng chung concurrency group. Migration DB không chạy từ luồng này cho tới khi có quyết định cutover DB riêng (`docs/guide/van-hanh-db-patroni.md` §3).

Thay đổi thứ hai (`deployment-plan.md` §6.1): thêm nhánh "Deploy staging-ha" song song với "Deploy Backend/Frontend" cho tới khi staging cũ được ngừng.

## Thay đổi source sau khi chốt

- `.github/workflows/staging-ha-cd.yml` — thêm: job `validate` (fmt, validate, test `staging-ha/tests/*.py`), `plan`, `apply` (environment `staging-ha`, có reviewer), `smoke`, và `rollback` bằng `workflow_dispatch` với digest cũ.
- `infra/terraform/environments/staging-ha/variables.tf` — sửa: `backend_image` / `frontend_image` nhận digest `@sha256:...` (validation regex), không chỉ tag.
- `infra/terraform/environments/staging-ha/` — cân nhắc: lưu digest đã deploy làm output để rollback.
- GitHub Environment `staging-ha` (cấu hình tay, không commit): secret `STAGING_HA_TFVARS` (nội dung `staging-ha.tfvars`, vì file này không commit), biến `STAGING_HA_LAST_GOOD_DIGEST`, reviewer bắt buộc.
- `docs/plan/2026-10-09-cd-staging-ha.md` — kế hoạch thực hiện.
- `history/` — entry tương ứng khi thực hiện.

Không đổi: workflow `backend-ci-cd.yml`, `frontend-ci-cd.yml`, `crawler-ci-cd.yml` ngoài việc tách concurrency group nếu cần; không đổi `infra-terraform-staging.yml`.
