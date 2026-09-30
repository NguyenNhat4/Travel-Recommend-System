# Merge release-mvp-v2 vào test/newcrawl, dùng CD fresh của team

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: deploy, docs

## Mục tiêu

Người yêu cầu: "merge về đây trước? sau đó tôi tự push và tự pull rq". Nhánh `release-mvp-v2` đã có CD crawler fresh của team
(PR #47–#51) trùng với CD fresh viết local trong `2026-09-30-tu-dong-cao-fresh-sau-deploy.md`. Merge để mở PR vào `release-mvp-v2`
mà không ghi đè CD của team.

Thay thế quyết định CI/CD trong `2026-09-30-tu-dong-cao-fresh-sau-deploy.md` (image `${GAR_DAILY_IMAGE}-fresh`, secret `GCE_FRESH_*`,
`deploy-pending`, không restart monitor). Phần data/code crawl của các entry 30/09 giữ nguyên.

## File thay đổi

- Merge `origin/release-mvp-v2` (commit `04b3e41`): conflict duy nhất `.github/workflows/crawler-ci-cd.yml` — lấy bản của team.
- `scripts/deploy-crawler-vm.sh` — xoá: CD của team không gọi.
- `scripts/tests/test-crawler-deploy.sh` — xoá: test của helper trên.
- `src/data_collection/run_daily_docker.sh` — sửa: bỏ xử lý `deploy-pending`; comment monitor theo CD của team. Giữ `import-flights` và
  bỏ qua tick khi batch legacy đang chạy.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: mục deploy mô tả CD của team (`GAR_FRESH_IMAGE`, digest, cron fresh, restart
  monitor, không tự cào), điều kiện VM với secret `GCE_CRON_*`, đổi key Cohere sửa tay env VM, lệnh import vé thương gia.
- `docs/guide/ve-thuong-gia-va-index-cho.md` — sửa: CD không tự import/cào; lệnh import dùng image/env fresh.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — sửa: đoạn cập nhật 30/09 theo CD của team.
- `src/data_collection/README.md` — sửa: mô tả CI/CD theo CD của team.
- `history/2026-09-30-merge-release-mvp-v2-dung-cd-fresh-cua-team.md` — thêm: entry này.

## Quyết định

- Không lệch PRD; chỉ đổi cách deploy (FR-CAT-01/03, NFR-REL-01 như các entry 30/09).
- `.github/` và `scripts/` giống hệt `release-mvp-v2`. Không thêm bước tự cào sau deploy vào workflow của team; muốn cào ngay thì bấm
  `full` trên monitor. Tự cào qua CD cần thống nhất với người giữ workflow.
- Không tự import 43 vé thương gia khi deploy: DB VM đã có (entry `2026-09-30-sua-db-vm-migration-va-bo-sung-catalog.md`).

## Kiểm tra

- `bash -n` ba script CI kiểm: PASS. `bash scripts/tests/test-install-vota-cron.sh`: PASS.
- `git diff --cached origin/release-mvp-v2 -- .github scripts`: rỗng.
- `PYTHONPATH=src:src/data_collection python -m pytest -q src/data_collection/tests` (env vsf2): 435 passed, 6 skipped.
  Lần chạy trước merge có 1 fail `test_supervisor_reaps_hung_worker_and_child_releases_lock`, chạy riêng 3/3 PASS (chập chờn).
- `git diff --check`: PASS.
- Chưa build lại `Dockerfile.fresh-catalog` sau merge (Dockerfile không đổi; build PASS trong entry `2026-09-30-tu-dong-cao-fresh-sau-deploy.md`).

## Còn lại / rủi ro

- Chưa commit merge, chưa push, chưa mở PR (người yêu cầu tự làm).
- Key Cohere trên VM chưa đổi: người có quyền VM sửa `/etc/vota/fresh-catalog.env`. Không đổi key thì index chờ tới khi quota hồi.
- Sau deploy, code mới chạy từ lượt theo lịch kế tiếp; cào ngay thì bấm `full` trên monitor.
