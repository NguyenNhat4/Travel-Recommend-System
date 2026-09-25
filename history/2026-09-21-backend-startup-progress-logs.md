# Thêm log tiến trình khởi động Backend

- Ngày: 2026-09-21
- Tác giả: người yêu cầu / Codex
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Cho biết rõ Backend đang khởi tạo thành phần nào khi Uvicorn còn ở `Waiting for application startup`.

## File thay đổi

- `src/backend/app/main.py` — sửa: log từng bước dựng CDP adapter, event recorder, itinerary clients và RecSys.
- `src/backend/app/infrastructure/embeddings/sentence_transformers_embedder.py` — sửa: log trước/sau khi nạp model embedding.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: log truy vấn catalog, cache embedding và quá trình tính embedding.
- `history/2026-09-21-backend-startup-progress-logs.md` — thêm: ghi lại thay đổi và bằng chứng.

## Quyết định

- Dùng logger `uvicorn.error` để các tiến trình xuất hiện trong `docker compose logs`.
- Ghi tên model, chế độ itinerary, số sản phẩm/search unit và cache path; không ghi DSN, token hay credential.
- Không đổi thứ tự hay semantics khởi động; log `startup.ready` chỉ xuất hiện sau khi lifespan hoàn tất phần setup.

## Kiểm tra

- Python AST parse cho ba file Backend — PASS.
- `docker compose config -q` — PASS.
- `docker compose build backend` — PASS.
- `docker compose up -d --build backend` — PASS; Backend container được recreate, PostgreSQL vẫn healthy.
- `docker compose logs --tail=80 backend` — xác nhận log mới tới `startup.recsys.embedding_model.load.start model=intfloat/multilingual-e5-base`.
- Test tự động — chưa chạy.

## Còn lại / rủi ro

- Tại thời điểm kiểm tra, container vẫn `health: starting` và đang nạp/tải model embedding lần đầu; log `startup.recsys.embedding_model.load.ready` chưa xuất hiện.
- `/health` chưa sẵn sàng cho tới khi lifespan hoàn tất.
