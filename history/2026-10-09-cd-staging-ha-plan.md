# Kế hoạch CD lên staging-ha (chỉ tài liệu)

- Ngày: 2026-10-09
- Tác giả: người dùng / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng hỏi CI/CD hiện có deploy lên staging-ha không (câu trả lời: không, chỉ deploy lên VM staging cũ) và yêu cầu viết plan đưa CD lên staging-ha.

## File thay đổi

- `docs/prd/update/2026-10-09-cd-staging-ha.md` — thêm: đề xuất lệch PRD (`deployment-plan.md` §1.1, §6.1), trạng thái chờ chốt.
- `docs/plan/2026-10-09-cd-staging-ha.md` — thêm: kế hoạch 0–4, quyết định Q1–Q5 cần chốt, rủi ro.
- `history/2026-10-09-cd-staging-ha-plan.md` — thêm: entry này.

## Quyết định

- Viết plan và đề xuất PRD trước, không sửa workflow hay Terraform. Lý do: AGENTS.md mục 8 — thay đổi quy trình CD lệch khẳng định "không bị sửa trong phạm vi này" của `deployment-plan.md` §1.1 phải được người dùng chốt trước.
- Đề xuất Terraform apply trong CI (Q1) thay vì rollout tay bằng gcloud, để state không lệch với tfvars.
- Không đưa migration vào luồng staging-ha cho tới khi có quyết định cutover DB (`history/2026-10-08-bao-cao-staging-ha.md`).
- Giữ CD staging cũ song song; không dùng chung concurrency group `vota-application-vm-deploy`.

## Kiểm tra

- Đọc: `.github/workflows/{backend-ci-cd,frontend-ci-cd,crawler-ci-cd,ha-checks,infra-terraform-staging}.yml`; `scripts/deploy-backend-vm.sh` (đầu file, tham số); `docs/prd/deployment-plan.md` §1, §2, §6; `docs/prd/requirements.md` (NFR-REL, NFR-PERF); `docs/plan/2026-10-08-hoan-thanh-todo-ha.md`; `docs/prd/update-archive/2026-10-08-staging-ha-patroni.md` (mẫu đề xuất); `infra/terraform/environments/staging-ha/{main.tf,variables.tf,startup.sh.tftpl,backend.tf,dns.tf,outputs.tf}`; `ops/loadtest/ha-rolling-update-drill.sh`.
- Chưa chạy `terraform plan`, chưa gọi GCP, chưa chạy workflow. Không có kiểm tra tự động cho tài liệu.
- Lưu ý: các file khác đang sửa trong nhánh (`.gitignore`, `README.md`, `deployment-plan.md`, `infra/terraform/environments/staging-ha/*`, `ops/loadtest/*`) không được đụng trong thay đổi này.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất `docs/prd/update/2026-10-09-cd-staging-ha.md` và Q1–Q5 trong plan. Khi đã chốt: cập nhật `docs/prd/deployment-plan.md`, chuyển đề xuất sang `update-archive/`, rồi mới làm workflow theo plan.
- Chưa xác minh: `DATABASE_URL` trong secret `vota-ha-backend-env`; quyền service account CI với root staging-ha; giá trị secret `GCE_INSTANCE` của staging cũ.
- Plan được ghi là dang dở cho tới khi thực hiện các bước.
