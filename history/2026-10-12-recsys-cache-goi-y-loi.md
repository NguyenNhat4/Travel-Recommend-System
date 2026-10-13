# Cache kết quả gợi ý: port, lõi trong application, gắn vào engine

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành (chưa nối Redis; adapter và nối dây ở `2026-10-12-recsys-cache-goi-y-redis.md`)
- Phạm vi: backend
- Liên quan: `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md` (đã chốt, đã áp dụng vào PRD), `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (giai đoạn 3)

## Mục tiêu

Hiện thực phần application của cache kết quả gợi ý đã chốt:

- khoá theo dấu vân tay event, nên không bao giờ trả kết quả tính từ lịch sử cũ;
- TTL bắt buộc; không ghi giá trị lớn hơn 64 KB;
- chống tính trùng bằng khoá tính;
- kho lỗi thì tính trực tiếp;
- khi CDP lỗi, kết quả lui không được ghi.

Phục vụ NFR-PERF-01; giữ nguyên FR-REC-02, AC-REC-02 và AC-REC-03 (K1).

## File thay đổi

- `src/backend/app/application/ports/recommendation_cache.py` — thêm: port `RecommendationCacheStore` (`get`, `put` có TTL, `try_lock` với token, `unlock` có kiểm token) và lỗi `RecommendationCacheUnavailable`.
- `src/backend/app/application/ports/__init__.py` — sửa: export hai tên mới.
- `src/backend/app/application/recommendation/cache.py` — thêm:
  - `CachePolicy` (TTL 900 s, 64 KB, khoá tính 30 s, chờ tối đa 10 s, poll 25 → 250 ms);
  - `events_fingerprint`, `popularity_digest` (không gồm `now`), `engine_version` (catalog, model, `ENGINE_RULES_VERSION`, bảng phổ biến, mọi knob kiểu đơn giản của engine), `source_digest`;
  - `RecommendationCache.key` (id người dùng chỉ nằm trong mã băm);
  - `get_or_compute`: trúng, chờ trúng, trượt, chờ quá hạn, quá lớn, không mã hoá được, kho lỗi.
- `src/backend/app/application/recommendation/__init__.py` — sửa: export `CachePolicy`, `RecommendationCache`, `source_digest`.
- `src/backend/app/application/recommendation/use_cases.py` — sửa:
  - thêm field `cache`, `catalog_version`; `__post_init__` tính `_engine_version` một lần mỗi engine; thêm `cache_enabled`;
  - `__call__` đi qua cache khi có cache, có người dùng và đọc từ CDP;
  - đặt `diagnostics.userVectorCacheHit` (contract) và `cacheOutcome` (chỉ ghi log).
- `src/backend/tests/fakes/recommendation_cache.py` — thêm: kho giả trong bộ nhớ (TTL theo đồng hồ tiêm, NX theo token, công tắc `down`, an toàn đa luồng).
- `src/backend/tests/unit/application/test_recommendation_cache.py` — thêm, 14 test:
  - trượt rồi trúng: tính một lần, payload giống, có TTL, id không lộ trong khoá;
  - purchase mới thì khoá đổi và kết quả mới (K1);
  - khoá phụ thuộc k, destination, ngày VN (mốc 17:00 UTC), engine, event, người dùng, namespace;
  - phiên bản engine ổn định giữa hai instance và đổi theo catalog, knob, popularity;
  - kho lỗi; CDP lỗi không chạm kho; khách vãng lai và `events=` không cache;
  - quá 64 KB; sửa kết quả trúng không ảnh hưởng lần sau;
  - payload hợp lệ theo contract; giá trị hỏng coi như trượt;
  - chống tính trùng (2 thread, 1 lần tính); người giữ khoá lỗi thì nhả khoá; chờ quá hạn thì tự tính và ghi.
- `history/2026-10-12-recsys-cache-goi-y-loi.md` — thêm: entry này.

## Quyết định

- **Cache đặt trong engine,** không làm lớp bọc riêng như phần "thay đổi source" của đề xuất. Lý do:
  - Đường lui khi CDP lỗi trả cùng dạng với cold-start; trong engine, nhánh lỗi trả trước khi đụng cache, nên không bao giờ ghi kết quả lui.
  - Engine đã đọc event thô một lần.
  - Route và trợ lý dùng chung một engine.
  - Harness bench không có cache nên không đổi gì.
- **Khoá theo nội dung, không cần xoá khoá khi mua hay huỷ.** Mỗi request vẫn đọc CDP (cùng vùng, vài ms) để dựng dấu vân tay. Cancel xoá dòng event nên dấu vân tay cũng đổi.
- **Phiên bản engine không gồm `Popularity.now`:** mỗi worker dựng bảng phổ biến vào lúc khác nhau, gồm vào thì các worker không bao giờ dùng chung khoá. Độ trôi trong ngày nằm trong TTL 15 phút; ngày VN đã có trong khoá.
- **Không cache khi không biết phiên bản catalog** (`catalog_version=None`).
- **Hằng đặt trong `cache.py`,** không trong `profile.py` (bench băm hằng chữ hoa của `profile.py`).

## Kiểm tra

- `pytest -q -p no:cacheprovider src/backend/tests/unit/application/test_recommendation_cache.py`: 14 passed.
- `pytest -q -p no:cacheprovider src/backend/tests src/evaluation/recsys_bench/tests`: 3087 passed, 42 skipped (gồm test kiến trúc).

## Còn lại / rủi ro

- Adapter Redis, cấu hình, nối dây trong `main.py`, phiên bản catalog từ `WeaviateVectorStore`: bước kế tiếp.
- Làm ấm sau đăng nhập: bước sau đó.
