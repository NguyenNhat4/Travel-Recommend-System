# Đồng bộ release-mvp-v1 vào test/newcrawl, gỡ conflict monitor và job embed

- Ngày: 2026-09-28
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, backend

## Mục tiêu

Kéo `origin/release-mvp-v1` (46 commit mới) về `test/newcrawl` mà vẫn giữ phần đang làm dở ở local (monitor cào real-time, chi tiết lượt index, SQLite state song song). Nhánh local không có commit riêng nên fast-forward; phần local được stash rồi áp lại, và hai file bị conflict.

## File thay đổi

- `src/backend/jobs/embed_products.py` — sửa (gỡ conflict): giữ cả `backfill_lexical` + property BM25 (upstream) lẫn `detail_path`/`write_detail`/lý do re-embed (local); `desired` giờ là bộ ba `(text, hash, name)`.
- `src/backend/tests/unit/infrastructure/test_embed_products_job.py` — sửa: settings giả của test chi tiết index thêm `search_bm25_k1`/`search_bm25_b` (upstream dùng khi dựng `WeaviateClient`).
- `src/data_collection/monitor.py` — sửa (gỡ conflict): giữ monitor mới (`FreshMonitor`); ghép tuỳ chọn public của teammate (`host_allowed`, `--host`, `--allow-public-host`), `host_allowed` vẫn tách đúng Host IPv6.
- `src/data_collection/run_daily_docker.sh` — sửa: `monitor|fresh-monitor` quay lại `cmd_fresh_monitor`, nhận `MONITOR_HOST`/`MONITOR_PUBLIC`.
- `src/data_collection/tests/test_monitor_public.py` — sửa: chỉ thay `protego`/`rapidfuzz` bằng module giả khi máy thật sự không cài.

## Quyết định

- Bản `monitor.py` trên `release-mvp-v1` hỏng: một merge ở `dev` (696220d/4ad2acf) trộn `Handler`/`main()` của monitor cũ (`Monitor`, `DailyApi`, `--data-dir`) vào file monitor mới, nên `main()` gọi các lớp không còn tồn tại, và lệnh `monitor` của runner chạy lại monitor cũ bằng image daily. Giữ monitor mới, chỉ lấy lại phần opt-in public của commit f3f7795.
- `test_monitor_public.py` ghi đè `sys.modules["rapidfuzz"]` bằng `SimpleNamespace` khi test khác chưa import, làm 5 test chuẩn hoá chạy sau đó hỏng (`token_sort_ratio`). Sửa thành chỉ stub khi `ImportError`.

## Kiểm tra

- `pytest src/backend/tests/unit/infrastructure/test_embed_products_job.py` (env `vsf`): 2 passed.
- `PYTHONPATH=.:.. pytest tests` trong `src/data_collection` (env `vsf`): 361 passed, 3 skipped. Trước khi sửa: 6 failed; cùng bộ test trên a68bfd4 + stash (trước merge): 359 passed.
- `bash -n run_daily_docker.sh`: sạch. `python monitor.py --help`: có `--host`, `--allow-public-host`, `--state-dir`, `--run-root`, `--log-dir`.
- Chưa chạy toàn bộ `src/backend/tests`.

## Còn lại / rủi ro

- Workflow CD `.github/workflows/backend-ci-cd.yml` (bước "Restart crawler monitor") gọi `run_daily_docker.sh monitor` với `IMAGE=<crawler image>` và `CONTAINER_NAME=vota-daily`, rồi chờ container `vota-daily-monitor`. `cmd_fresh_monitor` dùng `FRESH_IMAGE` và tên `$FRESH_NAME-monitor` (`vota-fresh-catalog-monitor`), nên bước này sẽ báo lỗi dù monitor chạy. Cần thống nhất với người viết CD trước khi sửa workflow.
- Stash `wip-before-mvpv1-ff-2026-09-28` vẫn còn làm bản dự phòng; xoá bằng `git stash drop` khi đã chắc.
