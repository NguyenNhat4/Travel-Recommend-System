# Gộp text builder giàu ngữ nghĩa vào nhánh đồng bộ catalog

- Ngày: 2026-09-23
- Tác giả: người yêu cầu / Codex
- Nhánh: feat/catalog-sync-cohere
- Trạng thái: hoàn thành
- Phạm vi: backend, search/recommendation

## Mục tiêu

Cherry-pick thay đổi text builder từ `feat/recsys-cohere-embedding` vào nhánh dựng trên
`release-mvp-v1`, đồng thời giải quyết conflict trong PostgreSQL vector store mà không làm mất
startup logging đã có trên release.

## File thay đổi

- `src/backend/app/domain/catalog/__init__.py` — sửa: export thêm API làm giàu text catalog.
- `src/backend/app/domain/catalog/text_builder.py` — sửa: xây text theo taxonomy, rollup biến thể và lọc nội dung biến động.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: đọc thành phần combo, truyền vào text builder và giữ nguyên startup logging của release.
- `src/backend/tests/unit/fixtures/embed_text_cases.json` — thêm: fixture cho các trường hợp text embedding theo taxonomy.
- `src/backend/tests/unit/test_text_builder.py` — sửa: kiểm tra fixture, tính tất định, rollup, lọc nhiễu và combo.
- `history/2026-09-23-gop-text-builder-vao-catalog-sync.md` — thêm: ghi lại quyết định gộp và kết quả kiểm tra.

## Quyết định

- Giữ cả `logger = logging.getLogger("uvicorn.error")` từ `release-mvp-v1` và `_COMBO_QUERY` từ nhánh catalog vì hai thay đổi độc lập và đều cần thiết.
- Tiếp tục dùng `catalog.product_meta` làm nguồn duy nhất cho vai trò sản phẩm; chỉ đọc `catalog.combo_items` để bổ sung nội dung combo, không tự suy lại metadata trong Python.
- Không đổi API contract, schema database, model embedding hoặc cơ chế cache `.npy` trong lần giải quyết conflict này.

## Kiểm tra

- `conda run -n vsf env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider src/backend/tests/unit/test_text_builder.py` — PASS, 21 test.
- `conda run -n vsf env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider src/backend/tests/unit/test_text_builder.py src/backend/tests/unit/test_engines.py src/backend/tests/unit/test_recommendation_history.py` — PASS, 28 test.
- `git diff --check` — PASS trước khi tạo entry này.
- Toàn bộ `src/backend/tests/unit` — chưa chạy được: conda `vsf` dùng Python 3.10, trong khi các test Agent import `enum.StrEnum` cần Python 3.11 trở lên; collection dừng với 7 lỗi import.

## Còn lại / rủi ro

- Chưa chạy integration test PostgreSQL; thay đổi query combo cần database đã seed để kiểm tra end-to-end.
- Cần chạy toàn bộ Backend suite trong Python 3.11+ hoặc môi trường đúng với yêu cầu của release.
