# Merge release-mvp-v2 vào test/newcrawl và kiểm CI/CD

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, backend, frontend, contract, ci

## Mục tiêu

Người yêu cầu: xem nhánh release mvp2 có gì mới, "check thử CI CD đạt chưa để tự pull vào", chọn "commit rồi merge v2". Người
yêu cầu tự push `test/newcrawl` và tự mở PR vào `release-mvp-v2`.

## File thay đổi

- Merge `origin/release-mvp-v2` (51 commit: agent gọi engine trong tiến trình / contract 1.8.0, tách workflow crawler,
  bỏ deploy Vercel, gold/bench) vào `test/newcrawl`. Tự gộp: `.env.example`, `docs/prd/requirements.md`,
  `src/backend/README.md`, `src/backend/app/core/config.py`, `src/frontend/src/types/api.gen.ts`,
  `src/shared/contracts/schemas/catalog.yaml`.
- `src/data_collection/monitor.py` — sửa (giải xung đột `main()`):
  - giữ tham số mới (`--host`, `--allow-public-host`, `--state-dir`, `--run-root`, `--log-dir`);
  - thêm `--data-dir` và đọc `VOTA_DATA_DIR` như bản v2 (<dữ liệu>/state, /fresh_runs, /logs);
  - thứ tự: tham số > `CATALOG_*` > data-dir > `data/`.
- `src/data_collection/run_daily_docker.sh` — sửa: `monitor` trở lại chạy trong image daily (container `$NAME-monitor`,
  tức `vota-daily-monitor`), đúng lệnh bước "Restart crawler monitor" của CD v2 gọi và chờ; `fresh-monitor` giữ cho image
  job mới. Trước đó `monitor` là bí danh của `fresh-monitor` (image / container khác), CD sẽ báo lỗi sau merge.
- `src/data_collection/README.md` — sửa: ghi chú hai lệnh monitor.
- `src/data_collection/tests/test_fresh_monitor.py` — sửa: thêm 2 test:
  - `monitor` = image daily + container `vota-daily-monitor`;
  - `main()` chọn thư mục theo tham số / env / data-dir.
- `history/2026-09-29-merge-release-mvp-v2-vao-newcrawl.md` — thêm: entry này.

## Quyết định

- CI/CD v2 chỉ build / publish / triển khai `Dockerfile.daily` (job cũ `daily.py`) và khởi động lại monitor. Image job mới
  `Dockerfile.fresh-catalog` (P1–P5, vé máy bay) **không** được CI build nên VM không tự kéo job mới. Người yêu cầu để đội
  deploy làm phần này.
- CI crawler chỉ compile + `bash -n` + build image, không chạy test `data_collection`; đã chạy riêng.

## Kiểm tra

Trên cây đã merge, trước khi commit, theo đúng các bước của workflow v2:

- Contract: `validate_contract.py`: PASS (88 schema, 64 fixture, CDP clone).
- Crawler CI: `compileall src/backend src/data_collection` OK; `bash -n` (`check-db-tunnel.sh`, `install-vota-cron.sh`,
  `run_daily_docker.sh`) OK; `scripts/tests/test-backend-vm-cd-sync.sh`: passed.
- Backend CI: `pytest src/backend/tests` (vsf2): **664 passed, 19 skipped**.
- Frontend CI (node 24 bundled; máy không cài node / npm riêng):
  - `generate:api-types`: file sinh ra trùng file đã gộp;
  - lint: 0 lỗi, 4 cảnh báo có từ trước;
  - `tsc --noEmit`: ok;
  - vitest: **128/128**;
  - `next build` + esbuild API: ok;
  - Playwright e2e: **13 passed, 1 skipped** (webServer chạy qua npm giả trong scratchpad, không sửa repo).
- Docker (như job build của CI): `Dockerfile.backend`, `src/frontend/Dockerfile.web`, `Dockerfile.daily`,
  `Dockerfile.fresh-catalog` đều build được. Image fresh import được `fresh_catalog`, `pipeline_graph`,
  `pipeline_runtime`, `monitor`; có Chromium.
- `data_collection` `pytest tests` (vsf2): **411 passed, 3 skipped**.

## Còn lại / rủi ro

- Chưa push; người yêu cầu tự push và mở PR vào `release-mvp-v2`.
- CD chạy thật trên VM (secret, IAP, cron) chưa kiểm được ở local.
- Job mới chưa có trong CI/CD (đội deploy).
