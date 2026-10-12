# Merge release-mvp-v2 vào nhánh HA để PR vào release mergeable

- Ngày: 2026-10-10
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành (merge và kiểm tra cục bộ). PR vào `release-mvp-v2` mở ở bước sau.
- Phạm vi: infra (staging-ha), CI frontend, và merge phần còn lại của release (backend, frontend, agent, contract, data). Phần release không đổi thêm.

## Mục tiêu

Nhánh HA đã đồng bộ với remote (entry `2026-10-10-dong-bo-nhanh-ha-voi-remote.md`), nhưng `origin/release-mvp-v2` đã có thêm commit `c6a90946` (đĩa boot VM crawler 15 GB, khớp VM đang chạy) và các thay đổi trước đó. Merge trực tiếp cho 9 file xung đột. Mục tiêu: merge release vào nhánh, resolve xung đột, để PR vào release không còn xung đột.

## Xung đột và cách giải quyết

| File | Bên chọn | Lý do |
|---|---|---|
| `infra/terraform/environments/staging-ha/crawler.tf` | release | Release là bản đầy đủ: lịch VM crawler (tắt 23:59, bật 08:30), `resource_policies`, `ignore_changes` cho khoá SSH runner. Nhánh không có nội dung riêng. |
| `infra/terraform/environments/staging-ha/startup.sh.tftpl` | release | Release đã chuyển boot sang Debian 12 (Ops Agent, `docker login`). Nhánh còn bản COS đã lỗi thời. |
| `infra/terraform/environments/staging-ha/variables.tf` | release | Mô tả `boot_to_ready_seconds` đã có số đo (~230 giây, Debian 12), validation `>= 240`. |
| `infra/terraform/environments/staging-ha/tests/test_resilience.py` | release | Test theo chốt 2026-10-09 (chấp nhận downtime, không surge), khớp với `main.tf` và `variables.tf` của release. |
| `.github/workflows/frontend-ci-cd.yml` (build_vm, docker_test) | release | Build image frontend một lần ở `staging-ha-frontend-build.yml`, job build trùng bị tắt. |
| `.github/workflows/frontend-ci-cd.yml` (Playwright) | nhánh | Commit `e8d58667` (00:27) đặt `PLAYWRIGHT_BROWSERS_PATH` vào `runner.temp`, mới hơn bản `tool_cache` của release (22:09). |
| `infra/terraform/environments/staging-ha/crawler_monitor.tf` | nhánh | Dashboard đủ chức năng, theo `history/2026-10-09-monitor-staging-du-chuc-nang.md`. Release còn bản chỉ đọc. |
| `infra/terraform/environments/staging-ha/main.tf` (comment) | nhánh | Đồng bộ với `crawler_monitor.tf` ở trên. |
| `infra/terraform/environments/staging-ha/monitoring.tf` | nhánh | Hai bên giống nhau, chỉ khác dòng trống. |
| `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` | cả hai | Giữ `create_crawler_vm = false` (release) và `crawler_monitor_public = false` (nhánh). |

Các file không xung đột vẫn được git tự gộp.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider infra/terraform/environments/staging-ha/tests` → 52 passed.
- `terraform fmt -check -recursive infra/terraform/environments/staging-ha` → exit 0.
- `terraform init -backend=false` rồi `terraform validate` → `Success! The configuration is valid.` `.terraform.lock.hcl` không đổi.
- Parse YAML toàn bộ `.github/workflows/*.yml` → 0 lỗi.
- `python3 src/shared/contracts/tests/validate_contract.py` (chạy trong venv tạm ngoài repo, có `jsonschema`) → PASS: 120 schemas, 50 grounded products, 94 fixtures, CDP clone 12 schemas.
- Unit test backend `src/backend/tests/unit` (venv tạm, cài các gói cần cho test, không cài torch/transformers) → 2503 passed, 2 skipped, 0 lỗi.
- `src/data_collection/tests/test_monitor_backend_calls.py` → 3 passed. Chưa chạy toàn bộ `src/data_collection/tests`.
- Frontend (`src/frontend`, `node_modules` có sẵn): `npx vitest run tests/unit` → 752 passed (70 file); `npm run lint` → exit 0; `tsc --noEmit` với tsconfig tạm loại trừ `.next` → exit 0.
- Chưa chạy: `ha-rolling-update-drill.sh` và k6 (cần hạ tầng thật), e2e Playwright, `terraform plan` (cần state và tfvars thật).

## Quyết định

- Khi release và nhánh cùng sửa một đoạn, lấy bản mới hơn theo thời gian commit, trừ phần đã có quyết định rõ (dashboard monitor và boot image).
- Dashboard monitor trong PR này là đủ chức năng và chỉ mở khi `crawler_monitor_public = true`. So với release hiện tại, đây là thay đổi hành vi, cần người vận hành xác nhận khi review.

## Còn lại / rủi ro

- Đề xuất CD `docs/prd/update/2026-10-09-cd-staging-ha.md` vẫn `chờ chốt`. Lệch PRD `deployment-plan.md` §1.1 và §6.1 (đã ghi ở entry trước) sẽ vào `release-mvp-v2` khi PR được merge.
- Merge commit này cũng kéo các thay đổi backend, frontend và agent của release vào nhánh. Các thay đổi đó đã được review trên release, không được sửa ở đây.
- PR #147 (vào `main`) đang mở từ nhánh này và sẽ cập nhật theo commit mới.
- `src/frontend/.next/` trên máy còn types của bản build cũ, nên `npm run typecheck` báo 3 lỗi trong `.next/`. Thư mục này đã được ignore và không nằm trong commit. Xoá hoặc build lại để typecheck sạch.
