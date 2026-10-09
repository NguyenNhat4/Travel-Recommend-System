# Đưa chính sách rolling downtime staging-HA lên release-mvp-v2 (nhánh riêng)

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude (agent)
- Nhánh: khoa/cd-rut-ngan-downtime (tạo từ origin/release-mvp-v2)
- Trạng thái: dang dở
- Phạm vi: infra (staging-ha), CI/CD

## Mục tiêu

Commit `fc19c865` (trên `khoa/ha-runtime-bootstrap-fix`) đổi chính sách rolling update staging-HA sang chấp nhận downtime. Nhánh đó lệch 70 commit so với `release-mvp-v2` và có xung đột ở 5 file, nên không mở PR trực tiếp. Entry này ghi các thay đổi trên nhánh mới để đưa cùng thay đổi lên release.

## Cherry-pick và xung đột

Commit đầu tiên của nhánh là `fc19c865` cherry-pick lên `origin/release-mvp-v2` (message được sửa: bỏ đoạn "chưa commit"). Ba file xung đột:

- `infra/terraform/environments/staging-ha/main.tf`: lấy policy mới (`max_surge_fixed = 0`, `max_unavailable_fixed = 3`, `min_ready_sec = 0`). Release trước đó dùng surge 3 và `min_ready_sec = var.boot_to_ready_seconds`.
- `infra/terraform/environments/staging-ha/variables.tf`: giữ mô tả của release (đã có "Debian 12", "CHƯA đo" đã đổi), chỉ thay đoạn về `min_ready_sec`.
- `.github/workflows/frontend-ci-cd.yml`: giữ `runs-on: [self-hosted, vota-staging-ha]` như release và `needs: [e2e, docker_test]`. Job `docker_test` (tự merge vào còn `ubuntu-latest`) được đổi sang runner tự host cho khớp các job khác. Job chưa có guard chặn PR từ fork, giống `quality` và `e2e` của release.

## Thay đổi bổ sung (commit thứ hai)

Đã có trong release nhưng không nằm trong `fc19c865`, nếu bỏ qua thì CD trên release hỏng:

- `.github/workflows/staging-ha-backend-cd.yml`, `.github/workflows/staging-ha-frontend-cd.yml`: bước Verify chờ LB báo đủ HEALTHY tối đa 10 phút (60 × 10 giây). Với `min_ready_sec = 0`, MIG báo stable trước khi VM mới nạp xong RecSys, nên kiểm một lần sẽ rollback nhầm. Dùng jq đã sửa lỗi mảng của `f9543eba`.
- `scripts/deploy-staging-ha-app.sh`: `APP_SURGE` mặc định `0` (trước `3`). Với `3`, preflight quota vẫn đòi thêm 6 vCPU dù không còn surge.
- `infra/terraform/environments/staging-ha/tests/test_resilience.py`: cập nhật hợp đồng rolling update theo chính sách đã chốt. Test cũ khóa `min_ready_sec = var.boot_to_ready_seconds` và `max_unavailable_fixed = 0`, nên `ha-checks` sẽ fail nếu không sửa. Thêm test kiểm bước Verify có vòng chờ LB HEALTHY.

## Quyết định

- Chính sách downtime đã được chốt (`docs/prd/update-archive/2026-10-09-rut-ngan-cd-chap-nhan-downtime.md`). Entry này không chốt thêm gì.
- Không đưa vào PR này: 17 commit khác của `khoa/ha-runtime-bootstrap-fix` (HA Patroni, runner tự host, DB resilience, lịch sử). Các commit đó có thể cần PR riêng.
- Không đưa vào: bundle CD staging-HA chưa chốt (`docs/prd/update/2026-10-09-cd-staging-ha.md`), các thay đổi chưa commit của monitor, origin HTTPS, Debian 12 trên nhánh cũ.

## File thay đổi

Commit 1 (cherry-pick `fc19c865`):

- `infra/terraform/environments/staging-ha/main.tf` — sửa: `update_policy`.
- `infra/terraform/environments/staging-ha/variables.tf` — sửa: mô tả `boot_to_ready_seconds`.
- `.github/workflows/frontend-ci-cd.yml` — thêm: job `docker_test`; `build_vm` `needs`.
- `docs/prd/deployment-plan.md` — sửa: §6.1 bước 3.
- `docs/prd/update-archive/2026-10-09-rut-ngan-cd-chap-nhan-downtime.md` — thêm.
- `history/2026-10-09-cd-nhanh-chap-nhan-downtime.md` — thêm.

Commit 2 (entry này):

- `.github/workflows/staging-ha-backend-cd.yml` — sửa: Verify chờ LB HEALTHY.
- `.github/workflows/staging-ha-frontend-cd.yml` — sửa: Verify chờ LB HEALTHY.
- `scripts/deploy-staging-ha-app.sh` — sửa: `APP_SURGE` mặc định 0.
- `infra/terraform/environments/staging-ha/tests/test_resilience.py` — sửa: test rolling update.
- `history/2026-10-09-cd-downtime-tren-release-mvp-v2.md` — thêm.

## Kiểm tra

- `python3 infra/terraform/environments/staging-ha/tests/test_resilience.py`: `Ran 23 tests ... OK`.
- YAML parse của `frontend-ci-cd.yml`, `staging-ha-backend-cd.yml`, `staging-ha-frontend-cd.yml`: OK. `build_vm` needs `['e2e', 'docker_test']`. `bash -n` mọi khối `run:`: 0 lỗi.
- `bash -n scripts/deploy-staging-ha-app.sh`: OK. `terraform fmt -check` cho `main.tf`, `variables.tf`: OK.
- `terraform init -backend=false` + `terraform validate` trên bản sao của `infra/terraform/environments/staging-ha` của nhánh này (copy `infra/` và `ops/` vào thư mục scratch): `Success! The configuration is valid.`
- Chưa chạy: `terraform plan` trên staging-HA thật, workflow CD và CI trên GitHub.

## Còn lại / rủi ro

- `max_unavailable_fixed = 3` với targetSize tối đa 2: cần `terraform plan` thật để xác nhận GCP chấp nhận.
- Downtime mỗi lần triển khai đã chấp nhận cho staging-HA, chưa có quyết định cho production.
- `docker_test` không có guard chặn PR từ fork, giống `quality` và `e2e` của release. Cần xem xét khi có quyết định về runner tự host cho PR từ fork.
- Chưa đo thời gian rollout thật sau thay đổi (kỳ vọng ~5 phút, thay vì ~15,6 phút).
