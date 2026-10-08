# Merge origin/release-mvp-v2 vào feat/agent

- Ngày: 2026-10-06
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, search, tài liệu

## Mục tiêu

Đưa 80 commit mới của `origin/release-mvp-v2` (trước đó nhánh chỉ có bản local cũ) vào `feat/agent`. Không thêm hành vi mới;
không lệch PRD (nhận nguyên thay đổi FR-SRC-02 đã chốt 06/10/2026 ở release).

## File thay đổi

Toàn bộ thay đổi từ release (xem `git show -m --stat HEAD`). Riêng các file có conflict:

- `.env.example`, `src/backend/README.md`, `src/backend/app/core/config.py`, `src/backend/app/main.py` — lấy bản release (e5-small local, `VECTOR_COLLECTION`, bỏ biến `COHERE_*`).
- `src/backend/app/infrastructure/embeddings/cohere_embedder.py`, `src/backend/tests/unit/infrastructure/test_cohere_embedder.py` — xoá (release đã bỏ Cohere; bản của nhánh này đã sửa ở commit `70c096a7`).
- `src/backend/app/api/errors.py`, `src/backend/app/application/itinerary/engine_tools.py`, `src/backend/scripts/langgraph_studio.py`, `src/backend/README.md` — sửa chú thích/ghi chú còn nhắc Cohere.

## Quyết định

- Commit `70c096a7` (lỗi Cohere không im lặng) bị thay thế một phần: phần riêng Cohere (phân loại 429, `COHERE_QUERY_MAX_WAIT_SECONDS`) mất cùng adapter. Giữ `EmbeddingUnavailableError`, handler 503 `SEARCH_UNAVAILABLE`, `ToolError.reason` vì không phụ thuộc nhà cung cấp; hiện adapter e5 local chưa ném lỗi này.
- `src/evaluation/search_bench` và `src/data_collection` vẫn còn nhắc `COHERE_API_KEY` (bench/job cũ); không đụng vì ngoài phạm vi merge.

## Kiểm tra

- `.venv/bin/python -m pytest src/backend/tests/unit src/backend/tests/architecture -q`: 1610 passed, 2 skipped.
- Chưa chạy test integration/DB, chưa chạy lại contract validator, chưa chạy agent thật với e5 local.

## Còn lại / rủi ro

- Môi trường dev cần model e5 (~470 MB) và collection Weaviate `ProductE5Small` được index lại; `.env` cũ còn `COHERE_*`/`WEAVIATE_COLLECTION` sẽ bị bỏ qua.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §7.3 còn nhắc `embed:<lý do>`: kiểm tra lại với e5.
