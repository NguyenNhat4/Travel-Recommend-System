# Recommender Architecture Lab prototypes

- Ngày: 2026-09-22
- Tác giả: người yêu cầu / Codex
- Nhánh: codex/recsys-10-architectures
- Trạng thái: hoàn thành
- Phạm vi: evaluation, backend, cdp, docs

## Mục tiêu

Tạo workbench Streamlit để so sánh 10 kiến trúc recommender trên temporal holdout dùng chung và khám phá gợi ý theo user/persona. Dữ liệu đánh giá là lịch sử CDP seed tổng hợp.

## File thay đổi

- `src/backend/app/application/ports/recsys.py` — sửa: thêm `all_events()` vào read port CDP.
- `src/backend/app/infrastructure/cdp/local_cdp_client.py` — sửa: trả bản sao snapshot event local.
- `src/backend/app/infrastructure/cdp/postgres_cdp_reader.py` — sửa: đọc snapshot event đầy đủ, thứ tự ổn định, qua adapter CDP.
- `src/evaluation/README.md` — thêm: cài đặt, cấu hình đọc dữ liệu, chạy dashboard, metric và giới hạn.
- `src/evaluation/benchmark.py` — thêm: holdout theo thời gian, lọc leakage, metric và batch runner.
- `src/evaluation/data_source.py` — thêm: tải catalog và event qua adapter hiện có.
- `src/evaluation/recommender_prototypes.py` — thêm: interface chung và 10 prototype recommender.
- `src/evaluation/streamlit_app.py` — thêm: batch benchmark, persona explorer, tải báo cáo CSV/JSON và xóa kết quả cũ khi tải lại snapshot.
- `src/evaluation/tests/test_cdp_all_events.py` — thêm: kiểm tra adapter local trả snapshot event.
- `src/evaluation/tests/test_postgres_cdp_reader.py` — thêm: kiểm tra truy vấn snapshot ổn định qua adapter Postgres.
- `src/evaluation/tests/test_recommender_prototypes.py` — thêm: registry, eligibility, loại item đã xem, tính tái lập và personalization.
- `src/evaluation/tests/test_temporal.py` — thêm: split temporal, chống leakage và metric.
- `history/2026-09-22-recsys-10-architectures.md` — thêm: entry lịch sử task.

## Quyết định

- Dùng một split chung: purchase hợp lệ mới nhất mỗi user là target; train chỉ chứa event có timestamp sớm hơn target, loại cả event đồng thời để tránh temporal leakage.
- Giữ eligibility theo `catalog.product_meta.is_recommendable`; không lọc availability trước khi rank vì availability precision là metric cần đo.
- Đọc `cdp.events` chỉ qua `PostgresCdpReader` với biến cấu hình `CDP_DATABASE_URL`; README chỉ dẫn role CDP evaluation chỉ đọc. Catalog tiếp tục đọc qua `PostgresVectorStore`.
- Không đổi OpenAPI/DDL và không sửa itinerary-agent Streamlit hiện có. Kết quả, gồm ALS/graph/sequence, được gắn nhãn prototype trên dữ liệu seed tổng hợp.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/evaluation/tests` — PASS, 13 passed.
- `git diff --check` — PASS.
- Python `compile()` cho 7 module production backend/evaluation — PASS.
- Backend unit suite tổng thể không thu thập được trong môi trường Python hiện tại vì thiếu dependency backend (`fastapi`, `pydantic`, `psycopg`, `httpx`, `jsonschema`).
- Chưa smoke-test Streamlit hoặc DB seeded: môi trường hiện tại thiếu Streamlit, psycopg và cấu hình DSN.

## Còn lại / rủi ro

- Chạy dashboard với PostgreSQL đã seed và dependency trong `src/backend/requirements.txt` cùng `src/evaluation/requirements.txt` để xác minh tích hợp thực tế.
- Metric trên lịch sử synthetic không chứng minh chất lượng với khách thật; embedding cache/model có thể làm lần chạy đầu tải lâu.
