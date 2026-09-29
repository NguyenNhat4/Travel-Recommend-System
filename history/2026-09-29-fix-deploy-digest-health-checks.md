# Sửa kiểm tra và lịch chạy deploy theo image digest

- Ngày: 2026-09-29
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/workflow-pr-push-triggers`
- Trạng thái: hoàn thành phần source và kiểm tra local; chưa chạy GitHub Actions hoặc deploy VM thật
- Phạm vi: DevOps, CI/CD

## Mục tiêu

Khắc phục ba điểm trong thay đổi CI/CD hiện tại: cron crawler phụ thuộc credential Artifact Registry ngắn hạn, Frontend probe Backend bằng liveness thay vì readiness, và test đồng bộ chưa kiểm tra mô hình deploy image digest qua Compose override.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — giữ nguyên thay đổi sẵn có của task trước: deploy Backend theo digest.
- `.github/workflows/crawler-ci-cd.yml` — dùng digest cho pull, monitor và cron; cron không pull lại sau khi credential ngắn hạn hết hạn.
- `.github/workflows/frontend-ci-cd.yml` — giữ nguyên thay đổi sẵn có của task trước: truyền digest cho deploy Frontend.
- `scripts/deploy-backend-vm.sh` — giữ nguyên thay đổi sẵn có của task trước: validate digest và readiness URL.
- `scripts/deploy-frontend-vm.sh` — probe Backend tại `/health/ready`, sửa usage và chấp nhận reference Artifact Registry theo digest.
- `scripts/install-vota-cron.sh` — cron dùng digest đã pull trong deploy và đặt `PULL=0`.
- `scripts/tests/test-backend-vm-cd-sync.sh` — kiểm tra Backend/Crawler/Frontend truyền digest, cron không pull lại, readiness Frontend và Compose template vẫn là cấu hình mặc định được override khi deploy.
- `history/2026-09-29-fix-deploy-digest-health-checks.md` — ghi nhận thay đổi và kết quả kiểm tra.

## Quyết định

- Job deploy crawler pull image digest trong lúc access token còn hiệu lực, rồi cài cron với cùng digest và `PULL=0`; cron hằng ngày dùng image đã có trên VM, không phụ thuộc đăng nhập registry lâu dài.
- Compose template vẫn giữ tag mặc định. Script deploy ghi image digest qua Compose override, nên kiểm tra phải xác nhận cả cấu hình nền lẫn đường truyền digest, không bắt template đổi sang digest.
- Frontend chỉ được xem Backend sẵn sàng khi `/health/ready` thành công.
- Không đổi PRD, API, DDL hoặc hành vi sản phẩm. Quy chiếu vận hành: `docs/prd/deployment-plan.md` §5–6 và tự động hóa ở `docs/prd/test-plan.md` §4; không có mã FR/NFR sản phẩm riêng cho thay đổi này.

## Kiểm tra

- `bash -n scripts/install-vota-cron.sh scripts/deploy-frontend-vm.sh scripts/tests/test-backend-vm-cd-sync.sh` — PASS.
- `bash scripts/tests/test-backend-vm-cd-sync.sh` — PASS.
- Chạy `install-vota-cron.sh` với crontab fixture — PASS; dòng không liên quan được giữ và managed entry ghi image digest với `PULL=0`.
- PyYAML parse ba workflow Backend, Crawler, Frontend — PASS.
- `git diff --check` — PASS.
- Chưa chạy GitHub Actions hoặc xác minh cron/image/runtime trên VM thật.

## Còn lại / rủi ro

- Cần một lần chạy workflow thật để xác nhận WIF, quyền Artifact Registry/IAP, và deploy/runtime trên App VM.
- Cron chỉ chạy được nếu image digest đã được pull thành công trong job deploy; workflow hiện pull trước khi cài cron và dừng khi pull thất bại.
