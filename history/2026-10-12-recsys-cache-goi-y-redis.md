# Cache gợi ý trên Redis: adapter, cấu hình, phiên bản catalog, nối dây

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành (làm ấm sau đăng nhập ở entry sau)
- Phạm vi: backend, cấu hình dev
- Liên quan: `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md` (đã chốt, đã áp dụng vào PRD architecture §4, deployment-plan §2), `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (giai đoạn 3), `history/2026-10-12-recsys-cache-goi-y-loi.md`

## Mục tiêu

Nối cache gợi ý ở `2026-10-12-recsys-cache-goi-y-loi.md` vào Redis dùng chung. Khi đó mọi worker và mọi VM đọc cùng kết quả: gọi lặp lại và bấm "Thử lại" sau timeout đều trúng cache.

Phục vụ NFR-PERF-01; giữ nguyên FR-REC-02, AC-REC-02 và AC-REC-03.

## File thay đổi

- `src/backend/app/infrastructure/persistence/redis_recommendation_cache.py` — thêm `RedisRecommendationCacheStore`, cài port `RecommendationCacheStore`:
  - client `redis` **đồng bộ** (route `/recommendations` là `def` chạy trong threadpool); `socket_timeout` và `socket_connect_timeout` 100 ms; không retry;
  - `put` = `SET … EX`; `try_lock` = `SET NX PX`; `unlock` = Lua chỉ xoá khi đúng token;
  - mọi `RedisError`/`OSError` đổi thành `RecommendationCacheUnavailable`; ngắt mạch 5 s;
  - WARNING `recsys.cache.error` tối đa một lần mỗi 60 s mỗi worker, chỉ ghi `op`, tên kiểu lỗi và số lần bị nén; không ghi URL, mật khẩu hay nội dung lỗi.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: thêm property `PostgresCatalogReader.fingerprint`, là mã băm catalog của lần nạp gần nhất.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa: `WeaviateVectorStore.version` = sha256(mã băm catalog + `productId`/`modelVersion`/`textHash` của từng object), đặt sau bước kiểm của `load()`.
  - Đổi khi catalog đổi hoặc job index ghi lại object.
  - Giống nhau ở mọi tiến trình cùng dữ liệu, nên các worker dùng chung khoá.
  - `None` khi không hỏi được mã băm.
- `src/backend/app/main.py` — sửa:
  - `build_recsys(..., recommend_cache=None)` truyền `cache` và `catalog_version` vào `RecommendForUser`. Có cache mà không có phiên bản thì log `recsys.cache.disabled reason=no_catalog_version` và không cache lần nạp đó.
  - Hàm mới `build_recommendation_cache(settings, stack)`:
    - URL trống thì trả `None`; production ghi WARNING `reason=no_redis_url`;
    - có URL thì dựng store, `stack.callback(store.close)`, namespace = `source_digest` của các module quyết định output.
  - Lifespan truyền cache vào `RecsysRefresher` qua `functools.partial`.
- `src/backend/app/core/config.py` — sửa: `recommend_cache_redis_url` (trống = tắt; **không** thuộc `shared_backend_violations`, vì thiếu thì chỉ chậm) và `recommend_cache_ttl_seconds` (900, trong 60–86400).
- `src/backend/app/core/logging_config.py` — sửa: allowlist cho `recsys.cache.error`, `recsys.cache.disabled`, `recsys.cache.warm`.
- `.env.example` — sửa: `RECOMMEND_CACHE_REDIS_URL=redis://:devpass@localhost:6379/4`; dòng TTL để comment. Dev đang dùng DB 1–3.
- `docker-compose.yml` — sửa: backend nhận `RECOMMEND_CACHE_REDIS_URL` (mặc định `redis://:devpass@redis:6379/4`, ghi đè bằng `BACKEND_RECOMMEND_CACHE_REDIS_URL`).
- `src/backend/tests/guard.py` — sửa: `CONNECTION_VARS` thêm `RECOMMEND_CACHE_REDIS_URL`, nên test chặn được Redis từ xa.
- `src/backend/README.md` — sửa: đoạn mô tả `/recommendations` gồm gọi song song, vector trong RAM, 500 event, cache Redis và các trường log.
- `src/backend/tests/unit/infrastructure/test_redis_recommendation_cache.py` — thêm, client giả. Kiểm:
  - tham số lệnh (`ex`, `nx`/`px`, mở khoá theo token);
  - ánh xạ lỗi `ConnectionError`/`TimeoutError`/`OSError`;
  - ngắt mạch 5 s rồi thử lại;
  - WARNING có giới hạn tần suất và không lộ URL/mật khẩu;
  - tham số `from_url`.
- `src/backend/tests/integration/test_recommendation_cache_redis.py` — thêm, chạy khi `RUN_REDIS_INTEGRATION=1`, URL lấy từ `RECOMMEND_CACHE_REDIS_URL`. Ca kiểm:
  - ghi rồi đọc, TTL trong (0, 900];
  - khoá NX; sai token không mở được khoá;
  - chống tính trùng giữa ba thread;
  - cổng không ai nghe thì lỗi dưới 0,5 s.

  Chỉ ghi khoá có hậu tố riêng và tự dọn. Không dùng lệnh ảnh hưởng cả server.
- `src/backend/tests/unit/api/test_recommend_settings_wiring.py` — sửa, thêm test:
  - cache chỉ bật khi store có `version`; store không có `version` thì log `recsys.cache.disabled`;
  - mặc định của cấu hình;
  - URL trống thì không có cache, production có WARNING;
  - có URL thì dựng cache Redis với TTL đúng, và client được đóng khi app tắt.
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — sửa: thêm test `version` (ổn định với cùng dữ liệu; đổi khi đổi catalog hoặc `textHash`; `None` khi thiếu mã băm).
- `history/2026-10-12-recsys-cache-goi-y-redis.md` — thêm: entry này.

## Quyết định

- **Client đồng bộ, không dùng `redis.asyncio`.** Engine chạy trong thread của threadpool; client async cần event loop.
- **Timeout 100 ms, không retry, ngắt mạch 5 s.** Redis chậm hay mất không được làm gợi ý chậm thêm quá 100 ms. Sau lần lỗi đầu, các request trong 5 s tiếp theo bỏ qua Redis (0 ms).
- **Phiên bản catalog gồm metadata vector Weaviate,** không chỉ mã băm Postgres. Job index ghi lại vector mà catalog không đổi thì kết quả ANN có thể đổi.
- **Không bắt buộc URL ở `REQUIRE_SHARED_BACKENDS`.** Thiếu cache thì gợi ý chỉ chậm như trước, không sai. Production chỉ ghi WARNING.
- **Không sửa `compose.ha.yml`.** Backend HA đọc biến từ `env_file` (secret `vota-ha-backend-env`).
- **Test tích hợp không dùng `CLIENT PAUSE`,** vì Redis dev là của chung. Ca Redis treo chỉ kiểm thủ công trên Redis tạm (mục Kiểm tra).

## Kiểm tra

- `pytest -q -p no:cacheprovider` trên `test_redis_recommendation_cache.py`, `test_recommend_settings_wiring.py`, `test_weaviate_store.py`, `test_recommendation_cache.py` và test tích hợp: 47 passed, 4 skipped (test tích hợp, khi không đặt `RUN_REDIS_INTEGRATION`).
- Redis tạm `docker run -d --rm --name recsys-cache-test-redis -p 127.0.0.1:56380:6379 redis:7-alpine`, không dùng Redis 6379 của checkout khác:
  - `RUN_REDIS_INTEGRATION=1 RECOMMEND_CACHE_REDIS_URL=redis://127.0.0.1:56380/4 pytest … test_recommendation_cache_redis.py`: 4 passed; `DBSIZE` của DB 4 sau test = 0.
  - Script thủ công `CLIENT PAUSE 3000 ALL` (Redis treo, vẫn nhận kết nối):
    - `get` lỗi `TimeoutError` sau 109 ms;
    - lần gọi kế tiếp lỗi `breaker_open` sau 0,0 ms;
    - `get_or_compute` tính thẳng, outcome `error`, 0,0 ms;
    - sau 5,2 s đọc lại được giá trị, mất 8,2 ms.
  - Đã dừng container.
- `pytest -q -p no:cacheprovider src/backend/tests src/evaluation/recsys_bench/tests`: 3099 passed, 46 skipped (gồm test kiến trúc).

## Còn lại / rủi ro

- **Vận hành:** thêm `RECOMMEND_CACHE_REDIS_URL` vào secret `vota-ha-backend-env`, dùng một DB index chưa dùng trên Memorystore (kiểm index của AUTH, ITINERARY và BOOKING trước). VM nhận biến ở lần thay template kế tiếp. Chưa có biến thì cache tắt và production ghi WARNING.
- **Làm ấm sau đăng nhập:** bước kế tiếp.
- **Chưa đo latency HTTP và parity khi bật cache:** môi trường bench prodcopy không còn. Số thật lấy từ log `recsys.recommend` (`cache`, `stage_ms`) trên staging sau khi deploy.
