# Rút ngắn CD: chấp nhận downtime khi thay VM staging-HA, song song hoá Docker test frontend

- Ngày: 2026-10-09
- Tác giả: người dùng (chỉ đạo: rút ngắn CI/CD nhanh nhất, chấp nhận service downtime) / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: docs (PRD deployment-plan §6.1, đề xuất update-archive); infra/CI (Terraform staging-ha, script deploy, workflow)

## Mục tiêu

Rút ngắn thời gian CI/CD. Số đo từ GitHub Actions (2026-10-09):

- Staging-HA Backend CD (run 37915686042): job Verify chờ `wait-until --stable` 937 giây. Toàn run 45 phút, khoảng 25 phút xếp hàng sau run Frontend CD giữ concurrency group `staging-ha-cd`.
- Staging-HA Frontend CD (run 37915676125): chờ MIG ổn định 8 phút rồi lỗi `Internal error` của Google, rollback thêm 1,5 phút.
- Nguyên nhân: `max_surge_fixed = 3` và `min_ready_sec = var.boot_to_ready_seconds` (mặc định 360 giây). Boot-to-ready đo ~230 giây.
- Frontend CI (PR): job `quality` chạy tuần tự, trong đó Docker test 253 giây; `Frontend quality checks` mất 9,5 phút.

Đề xuất PRD đã chốt: `docs/prd/update-archive/2026-10-09-rut-ngan-cd-chap-nhan-downtime.md`. Chốt dựa trên chỉ đạo của người dùng trong phiên.

## File thay đổi

Đã commit (chỉ các hunk do tác vụ này tạo; các thay đổi chưa commit khác của người dùng không đưa vào):

- `docs/prd/deployment-plan.md` — sửa: §6.1 bước 3 (bỏ "hỗ trợ Zero-downtime rolling update", ghi quyết định downtime cho staging-HA).
- `docs/prd/update-archive/2026-10-09-rut-ngan-cd-chap-nhan-downtime.md` — thêm: đề xuất đã áp dụng (trước ở `docs/prd/update/`).
- `infra/terraform/environments/staging-ha/main.tf` — sửa: block `update_policy` có `max_surge_fixed = 0`, `max_unavailable_fixed = 3`, `min_ready_sec = 0` (trước: 3 / 0 / boot_to_ready_seconds).
- `infra/terraform/environments/staging-ha/variables.tf` — sửa: mô tả `boot_to_ready_seconds` (không còn là min_ready_sec).
- `.github/workflows/frontend-ci-cd.yml` — thêm: job `docker_test` (không `needs`, chạy song song với `quality`); `build_vm` có `needs: [e2e, docker_test]`. Runner của job này là `ubuntu-latest` như các job khác trong HEAD; đổi runner là phần của thay đổi runner chưa commit.
- `history/2026-10-09-cd-nhanh-chap-nhan-downtime.md` — thêm: entry này.

Đã sửa trong working tree nhưng **chưa commit**, vì thuộc bundle CD staging-HA (`docs/prd/update/2026-10-09-cd-staging-ha.md` còn `chờ chốt`; `history/2026-10-09-staging-ha-cd-tu-dong.md` ghi "không tạo đề xuất PRD"):

- `scripts/deploy-staging-ha-app.sh` (untracked) — `APP_SURGE` mặc định `0` (trước: `3`).
- `.github/workflows/staging-ha-backend-cd.yml`, `.github/workflows/staging-ha-frontend-cd.yml` (untracked) — bước Verify chờ LB HEALTHY tối đa 10 phút.

## Quyết định

- Thay VM một lượt (`max_surge = 0`) thay vì surge: boot-to-ready là thời gian chờ không thể bỏ, surge chỉ thêm 3 VM tạo song song và vẫn chờ min_ready. Với downtime được chấp nhận, không cần surge.
- `min_ready_sec = 0`. Vì vậy MIG có thể báo stable trước khi VM nạp xong RecSys, nên bước Verify phải chờ LB HEALTHY (đã sửa ở cả hai workflow CD). Nếu không, bước kiểm một lần sẽ thất bại và rollback nhầm.
- `max_unavailable_fixed = 3`: MIG regional ba zone chỉ nhận fixed 0 hoặc ≥ 3 (ghi trong comment main.tf từ trước). Giá trị 3 vượt targetSize tối đa 2, nên cả hai VM có thể được thay cùng lúc.
- Docker test frontend tách sang job song song vì `src/frontend/Dockerfile.web` tự `npm ci` và build trong container, không cần artifact của `quality`. `build_vm` vẫn đợi `docker_test` để image lỗi không được publish.
- Không đổi `backend-ci-cd.yml`: job `build` đang đợi `quality`, và `publish` đợi `build`, nên đổi thứ tự sẽ làm publish chạy trước khi test xong.
- Không đổi concurrency group `staging-ha-cd`: vẫn cần để hai CD không ghi chồng lên `last-good`.

## Kiểm tra

- YAML parse (PyYAML) của `frontend-ci-cd.yml`, `staging-ha-backend-cd.yml`, `staging-ha-frontend-cd.yml`: OK. Đồ thị job: `docker_test` không có `needs`; `build_vm` needs `[e2e, docker_test]`; `e2e` needs `quality`.
- `bash -n` mọi khối `run:` của ba workflow trên: 0 lỗi. `bash -n scripts/deploy-staging-ha-app.sh`: OK.
- `terraform fmt -check` cho `main.tf` và `variables.tf`: OK.
- `terraform init -backend=false` + `terraform validate` trên bản sao của `infra/terraform/environments/staging-ha` (copy `infra/` và `ops/` vào thư mục scratch): `Success! The configuration is valid.`
- Chưa chạy: `terraform plan` thật trên staging-HA (cần state và tfvars từ secret), chưa chạy workflow CD và CI trên GitHub, chưa commit/push. Chưa đo lại thời gian sau thay đổi.

## Còn lại / rủi ro

- Commit này đưa `main.tf` sang `min_ready_sec = 0` nhưng chưa đưa bước Verify chờ LB HEALTHY vào HEAD, vì bước đó nằm trong bundle CD chưa commit. Ai apply `main.tf` từ HEAD trước khi bundle được chốt và commit sẽ không có cổng chờ LB tự động. Cần chốt đề xuất CD staging-HA rồi commit bundle, hoặc chấp nhận rủi ro này.
- Bundle CD staging-HA (script, hai workflow CD) chưa commit: cần chốt `docs/prd/update/2026-10-09-cd-staging-ha.md` rồi mới commit, theo AGENTS.md mục 8.
- Push, rồi chạy `staging-ha-backend-cd` hoặc `staging-ha-frontend-cd` (workflow_dispatch) để đo thời gian rollout thật. Kỳ vọng: rollout ~5 phút thay vì ~15,6 phút (chưa kiểm).
- Kiểm `terraform plan` trên staging-HA: GCP có chấp nhận `max_unavailable_fixed = 3` với size 2 không. Nếu không, chọn giá trị khác ≥ 3.
- Downtime thật mỗi lần triển khai: toàn bộ app ngừng nhận traffic từ lúc VM cũ bị xoá tới khi VM mới đạt `/health/ready` (ước vài phút). Đã được chấp nhận cho staging-HA, chưa có quyết định cho production.
- Rút ngắn tiếp: boot-to-ready ~230 giây là sàn của rolling update. `startup.sh.tftpl` cài Ops Agent và apt trước `docker pull`; chuyển Ops Agent xuống sau `compose up` có thể giảm vài chục giây. Chưa làm: cần đo lại `startup.recsys.ready` và cập nhật ràng buộc `boot_to_ready_seconds >= 240`.
- `docker_test` chỉ thật sự song song khi có ít nhất hai runner tự host đang rảnh. Chưa xác minh được số runner (`gh api .../actions/runners` trả 404: tài khoản không có quyền admin trên repo).
- `ops/loadtest/ha-rolling-update-drill.sh` mô tả kịch bản rolling update; chưa rà soát xem nó có giả định không có downtime không.
- Run Frontend CD 37915676125 thất bại ở `wait-until` với lỗi nội bộ của Google (`Internal error`), chưa có nguyên nhân gốc. Run Frontend E2E smoke tests 37916289091 thất bại sau ~1 phút; chưa điều tra.
