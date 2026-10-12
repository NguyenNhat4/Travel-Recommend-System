# Đồng bộ nhánh HA với remote trước khi commit phần thay đổi local

- Ngày: 2026-10-10
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành (bước đồng bộ và commit). Merge `origin/release-mvp-v2` và PR để ở entry riêng.
- Phạm vi: docs (infra staging-ha, CI, ops, PRD Weaviate). Không đổi `src/`.

## Mục tiêu

Nhánh local đứng sau `origin/khoa/ha-runtime-bootstrap-fix` 68 commit, còn 19 file sửa và 22 file mới chưa commit. Nếu commit ngay trên HEAD cũ thì sẽ tạo nhánh song song với remote và không push được. Mục tiêu: đưa nhánh local lên remote trước, rồi mới commit phần còn lại.

## Cách làm

1. Sao lưu toàn bộ phần chưa commit: `git stash push --include-untracked -m "wip-ha-pre-sync-2026-10-10"`, commit stash `a60c6415`. Phục hồi từng file khi cần: `git checkout a60c6415 -- <đường dẫn>` (tracked) hoặc `git checkout a60c6415^3 -- <đường dẫn>` (untracked).
2. `git merge --ff-only origin/khoa/ha-runtime-bootstrap-fix`: `5df7f29b` → `5bfc014f`, không có commit lệch.
3. Khôi phục có chọn lọc từ stash, theo so sánh với remote:
   - Giữ bản local vì remote không đổi file này: `.gitignore`, `README.md`, `docs/plan/2026-10-08-hoan-thanh-todo-ha.md`, `infra/terraform/environments/staging-ha/monitoring.tf`, `ops/loadtest/ha-rolling-update-drill.sh`.
   - Giữ bản local cho file chưa track: 10 entry `history/`, 2 đề xuất PRD (`update/2026-10-09-cd-staging-ha.md` chờ chốt, `update-archive/2026-10-09-weaviate-staging-cloud.md` đã áp dụng), `ops/loadtest/k6-ha-1vm.js`.
   - Áp lại hai dòng Weaviate Cloud trong `docs/prd/deployment-plan.md` (§1 cột Staging và §2 `WEAVIATE_URL`). Bản remote chưa có thay đổi này, và đề xuất tương ứng đã áp dụng.
   - Bỏ bản local, dùng bản remote: 6 workflow CI/CD, `crawler.tf`, `main.tf`, `staging-ha.tfvars.example`, 3 workflow `staging-ha-*-cd.yml`, `scripts/deploy-staging-ha-app.sh`. Remote đã đổi cùng các file này và là bản mới hơn. Bản local còn trong stash `a60c6415`.
   - Không khôi phục: `alert_mute.tf`, `bastion.tf`, `scheduler.tf`, `crawler-startup.sh`, `crawler_monitor.tf`, `patroni.tf`, `secrets.tf`, `startup.sh.tftpl`, `variables.tf`. Các file này giống hệt remote hoặc release, nên không cần khôi phục.
4. `infra/monitoring/backend.staging.hcl` là file state trên máy, không được commit. Dòng ignore nằm trong `.gitignore` của phần local, nên đã được đưa lại cùng bước khôi phục.

## File thay đổi (commit này)

- `.gitignore` — thêm `infra/monitoring/backend.staging.hcl` và `.claude/worktrees/` (worktree lồng của Claude Code, có file `.git`, không commit).
- `README.md` — Weaviate: chỉ Redis là local; staging dùng Weaviate Cloud; cảnh báo không embed lại khi `.env` trỏ Weaviate Cloud dùng chung.
- `docs/prd/deployment-plan.md` — §1 và §2: Weaviate staging là Weaviate Cloud (theo đề xuất đã áp dụng).
- `docs/plan/2026-10-08-hoan-thanh-todo-ha.md` — bổ sung kế hoạch HA.
- `infra/terraform/environments/staging-ha/monitoring.tf` — kênh email bỏ theo dõi `enabled` (mute ban đêm).
- `ops/loadtest/ha-rolling-update-drill.sh` — bỏ `--min-ready` khi rolling update, theo chính sách chấp nhận downtime đã có trên remote.
- `ops/loadtest/k6-ha-1vm.js` — thêm kịch bản k6 20 VU cho 1 VM.
- `docs/prd/update/2026-10-09-cd-staging-ha.md` — đề xuất CD staging-ha, trạng thái `chờ chốt`.
- `docs/prd/update-archive/2026-10-09-weaviate-staging-cloud.md` — đề xuất đã áp dụng.
- 10 entry `history/2026-10-08-*.md` và `history/2026-10-09-*.md` còn thiếu trên remote.

## Quyết định

- Khi local và remote cùng đổi một file, lấy bản remote. Remote là bản mới và đã push.
- Chính sách CD staging-ha đã có trên remote từ trước và đang lệch `docs/prd/deployment-plan.md` §1.1 và §6.1. Theo [history/2026-10-09-staging-ha-cd-tu-dong.md](history/2026-10-09-staging-ha-cd-tu-dong.md), người vận hành chọn không lập đề xuất đã chốt. Commit này không thêm lệch PRD mới. Đề xuất CD vẫn `chờ chốt`, cần người vận hành quyết định trước khi merge vào `main` hoặc release.

## Kiểm tra

- `git rev-list --left-right --count HEAD...origin/khoa/ha-runtime-bootstrap-fix` → `0 0` sau fast-forward.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider infra/terraform/environments/staging-ha/tests` → 51 passed.
- `terraform fmt -check -recursive infra/terraform/environments/staging-ha` → exit 0.
- `bash -n ops/loadtest/ha-rolling-update-drill.sh` → không lỗi cú pháp.
- Chưa chạy: `terraform validate` (cần init và tải provider), `actionlint` (không có trên máy), chạy thật `ha-rolling-update-drill.sh` và k6 (cần GCP và hạ tầng thật).

## Còn lại / rủi ro

- Merge `origin/release-mvp-v2` (có commit mới `c6a90946`, đĩa boot crawler 15 GB) vào nhánh. Dự kiến xung đột ở `frontend-ci-cd.yml`, `crawler.tf`, `crawler_monitor.tf`, `main.tf`, `staging-ha.tfvars.example`, `startup.sh.tftpl`, `test_resilience.py`, `variables.tf`. Xử lý ở entry riêng.
- PR #147 (vào `main`) đang mở từ nhánh này và sẽ được cập nhật theo commit mới.
- Bản local bị bỏ ở bước 3 còn trong stash `a60c6415`. Chỉ xoá stash sau khi người vận hành xác nhận không cần.
