# Merge release-mvp-v2 (HA, log JSON, agent) vào test/newcrawl trước khi mở PR

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend, data, docs

## Mục tiêu

Người dùng muốn kiểm tra `release-mvp-v2` có gì mới rồi mở PR `test/newcrawl` → `release-mvp-v2`. `release-mvp-v2` có 50 commit mới (06/10): nhóm VM HA (failover DB, pgbouncer, Cloud NAT, nối DB trực tiếp, readiness), log JSON có cấu trúc cho backend/crawler/frontend + Cloud Logging, agent/widget/form chuyến đi và bộ test agent.

## Xử lý conflict (2 file)

- `src/backend/app/api/v1/routes/search.py` — import: giữ `uuid`, `current_request_id` (nhánh search) và `log_event` (log JSON của release-mvp-v2); dùng `logger = logging.getLogger(__name__)` của release-mvp-v2.
- `src/data_collection/run_daily_docker.sh` — container monitor: giữ quyết định 30/09 không giới hạn RAM mặc định (lượt Cào lớn chạy trong container monitor, giới hạn 1 GB đã giết lượt full), `MONITOR_MEMORY` đặt giới hạn khi cần; giới hạn log của chế độ chạy nền (`--log-opt max-size=10m`) đã có sẵn.

## File thay đổi thêm

- `src/data_collection/local_crawl.sh` — bỏ cảnh báo thiếu `COHERE_API_KEY` (bước index dùng e5-small).
- `src/data_collection/fresh-catalog.env.example` (mới từ release-mvp-v2) — bỏ `COHERE_*`, ghi chú không cần khoá.

## Kiểm tra

- Backend `pytest --ignore=tests/integration`: 1.694 passed, 2 skipped. `pytest src/data_collection/tests`: 502 passed, 21 skipped. `validate_contract.py`: PASS.
- Frontend `tsc --noEmit` (container node:20, node_modules của repo chính): chỉ báo thiếu `pino` — package mới của release-mvp-v2 chưa cài ở máy local; CI cài đủ.

## Còn lại / rủi ro

- `READY_REQUIRES_RECSYS` (mới, mặc định false): nếu env HA đặt true, `/health/ready` trả 503 trong lúc RecSys chưa có collection `ProductE5Small` (vài phút sau deploy, trước khi chạy `rebuild_product_e5.py --apply --delete-cohere`).
- `src/data_collection/daily.py` (job cũ) còn kiểm `COHERE_API_KEY`; job mới (`fresh_catalog.py`) không dùng.
