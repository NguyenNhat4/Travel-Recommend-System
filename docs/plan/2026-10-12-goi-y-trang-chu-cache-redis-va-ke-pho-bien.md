# Gợi ý trang chủ: làm nhanh, cache Redis, và kệ "Phổ biến" trộn loại

- Ngày: 2026-10-12
- Phục vụ:
  - NFR-PERF-01 (p95 ≤ 250 ms cho gợi ý cá nhân hoá).
  - FR-REC-01 (phổ biến theo điểm đến).
  - FR-REC-02 và AC-REC-01–03 phải giữ nguyên.
  - Chỉ số Diversity ở `docs/prd/test-plan.md` §2.5 ("kết hợp hài hòa khách sạn, vé máy bay, tour").
- Phạm vi: backend (recommendation, catalog), contract, frontend (trang chủ), infra (biến môi trường Redis), docs
- Nhánh: `fix/recommendation` (tạo từ `origin/release-mvp-v2` bab57fa5)
- Đề xuất PRD liên quan: `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md` (đã chốt, tqanh123, 2026-10-12; đã áp dụng vào PRD)
- Trạng thái: hoàn thành phần code, test và tài liệu (2026-10-12); còn phần đo (mục "Còn lại" cuối file)
  - Xong:
    - đề xuất áp dụng vào PRD; contract 1.25.0;
    - giai đoạn 1: `/products` trộn theo nhóm loại, kệ Phổ biến ở trang chủ, spec kệ Phổ biến và timeout, cold-start tối đa 2 mỗi taxonomy;
    - giai đoạn 2: thời gian từng bước, 500 event, gọi Weaviate song song, nạp sẵn vector vào RAM;
    - giai đoạn 3: cache gợi ý trên Redis, làm ấm sau đăng nhập, spec.
  - Mỗi bước có entry `history/2026-10-12-*.md` riêng.

## Bối cảnh

Đã kiểm trên code `origin/release-mvp-v2` và trên prod (praxis.io.vn, GET chỉ đọc) ngày 2026-10-12.

**Gợi ý trang chủ chậm**
- Mỗi lần vào trang chủ khi đã đăng nhập, `GET /recommendations` tính lại từ đầu (`application/recommendation/use_cases.py:163-274`):
  - đọc toàn bộ `cdp.events` của khách, không có LIMIT;
  - gọi Weaviate Cloud (eu-central-1) 3–5 lượt nối tiếp từ VM ở asia-southeast1: `vectors()` cho lịch sử, `near_vector` cho u_short và u_long (200 hit kèm vector), `vectors()` cho 50 món phổ biến, và `near_vector` của ô khám phá.
- Không có cache hay tính trước nào; engine chỉ được dựng lại mỗi 900 giây.
- Cùng code đó chạy với Weaviate local cho p95 khoảng 80–95 ms. Trên cloud: p95 1.057 ms (05/10); log backend 3,2–9,6 s (09/10).
- Bundle frontend đang chạy trên prod dùng timeout 10 s, không phải 3 s. Dòng 136 của `docs/spec/hop-dong-tich-hop-frontend.md` còn sót "3 giây".

**Kệ "Phổ biến tại các điểm đến Việt Nam", tab "Tất cả"**
- Trên prod, hạng 1–10 đều là vé máy bay. Món đầu tiên của các loại khác: khách sạn #11, vé tham quan #12, golf #19, combo #28.
- Nguyên nhân:
  - `sort=popular` đếm lượt mua 90 ngày theo search unit, chia cho max toàn cục (`domain/recommendation/popularity.py:65-70`).
  - Mọi chuyến bay con dồn về tuyến (113 tuyến), còn lượt mua khách sạn tản ra khoảng 2.400 property.
  - `sort_items` không có bước trộn theo loại (`domain/catalog/listing.py:58-76`).
- Cùng lệch này có ở cold-start `/recommendations`: `_top_products` (`use_cases.py:311-317`) không có trần theo taxonomy, nên 2 món đầu ở Phú Quốc, Đà Nẵng, Nha Trang, Đà Lạt đều là tuyến bay.

## Quyết định đã chốt (người dùng, 2026-10-12)

1. Không đưa Weaviate về cùng vùng, không quét vector trong RAM (phương án B bị loại).
2. Cache gợi ý đặt trên **Redis dùng chung**, không đặt trong tiến trình. Đây là lệch PRD; đề xuất đã chốt và áp dụng ngày 2026-10-12.
3. Không hiện bản cũ ở frontend: chưa có kết quả thì chưa hiện khối gợi ý. Timeout frontend **giữ 10 s**; chỉ sửa dòng spec cũ (`hop-dong-tich-hop-frontend.md:136`).
4. Kệ Phổ biến sửa theo phương án 1: thêm tham số tuỳ chọn `diversify=taxonomy` cho `GET /products` (sửa contract trước).
5. Không thêm tab Golf. Golf gộp với vé tham quan: tab "Vé tham quan" ở trang chủ lấy cả `attraction` và `golf`, và khi trộn tab "Tất cả" thì golf chung nhóm với attraction.
6. Lệch tương tự ở cold-start `_top_products` sửa cùng đợt.
7. Thứ tự trộn tab "Tất cả": khách sạn → vé tham quan và golf → combo → vé máy bay (2 ô mỗi nhóm trong 8 ô).
8. Nhãn loại trên thẻ **chỉ ở tab "Tất cả"** của kệ này (nhãn golf là "Golf", theo `TaxonomyBadge`). Nơi khác giữ quyết định bỏ nhãn ngày 2026-10-01.
9. Được nạp sẵn vector sản phẩm vào RAM ở nền; ANN vẫn qua Weaviate.
10. Làm ấm cache sau đăng nhập cho `(k=4, không destination)`. Persona demo P1–P3 gửi `destination='Nha Trang'` nên không được làm ấm; chấp nhận.

## Giai đoạn 1 — Kệ Phổ biến, cold-start, timeout frontend (không lệch PRD)

### 1a. Contract (làm trước), lên 1.25.0

Sửa `src/shared/contracts/paths/catalog.yaml` và `openapi.yaml`:
- **`taxonomy`:** nhận nhiều giá trị, cách nhau bằng dấu phẩy (`style: form`, `explode: false`, mảng `Taxonomy`), ví dụ `taxonomy=attraction,golf`. Một giá trị như cũ vẫn hợp lệ, nên đây là thay đổi tương thích ngược.
- **`diversify`:** tham số tuỳ chọn mới, enum `[taxonomy]`. Không gửi thì giữ nguyên hành vi hiện tại.
  - Khi gửi, backend trộn danh sách đã xếp theo kiểu round-robin giữa các nhóm loại. Đây là một hoán vị của danh sách, nên `total` không đổi và phân trang nối tiếp.
  - Thứ tự nhóm cố định: khách sạn → vé tham quan và golf → combo → vé máy bay.
  - Chỉ áp dụng với `sort=popular`. Đi cùng `sort` giá, hoặc cùng `parentProductId`, thì trả 400 `VALIDATION_ERROR`.
- Mock nếu cần: `src/shared/mocks/catalog/`, `src/shared/mocks/index.json`.
- Chạy `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`.

Ngoài lề: mô tả `ProductSort.popular` ở `schemas/common.yaml:44-46` (cột `popularity_score` không tồn tại, [C7]) giữ nguyên. [C7] để người dùng chốt riêng.

### 1b. Backend

- `domain/catalog/listing.py`:
  - `filter_items` nhận tập taxonomy.
  - Thêm hàm thuần `interleave_by_taxonomy(items, groups)` và bảng nhóm loại (`golf` thuộc nhóm vé tham quan).
- `application/catalog/use_cases.py` (`ListProducts`):
  - kiểm `diversify` và tập `taxonomy`;
  - trộn **trước** khi cắt `offset`/`limit`.
- `api/v1/routes/catalog.py`: thêm query `diversify` và tách `taxonomy` theo dấu phẩy.
- Cold-start (`application/recommendation/use_cases.py`, `_top_products`): áp trần `MAX_PER_VERTICAL` (2 món mỗi taxonomy) khi xếp. Trần này tính theo taxonomy của engine, golf vẫn là một taxonomy riêng như ở nhánh cá nhân hoá. Spec §4.8 đã ghi "tối đa 2 mỗi taxonomy" cho trường hợp toàn hệ thống; sửa câu chữ để áp cho cả trường hợp có điểm đến.
- Agent không bị ảnh hưởng, vì mọi lời gọi `list_products` của agent đều có `taxonomy` hoặc `parentProductId` (`application/itinerary/flights.py:60-69`).

### 1c. Frontend

- `src/frontend/src/types/api.gen.ts`: sinh lại.
- `services/catalog.ts` (`ListProductsParams`): thêm `diversify`; `taxonomy` nhận một giá trị hoặc mảng.
- `components/home/HomeView.tsx`:
  - tab "Tất cả" gửi `diversify: 'taxonomy'`;
  - tab "Vé tham quan" gửi `taxonomy: ['attraction', 'golf']`;
  - vẫn 1 request cho khối này (đúng ngân sách trang chủ và e2e "Home loads one catalog request").
- `RECOMMENDATION_TIMEOUT_MS` giữ 10 000 (quyết định 3). Chưa có kết quả thì không hiện khối; không lưu bản cũ ở sessionStorage.
- Nhãn loại trên thẻ `ProductCard` dạng tile, chỉ khi kệ trộn loại (tab "Tất cả"; prop `showTaxonomy`), dùng `TaxonomyBadge` có sẵn. Lý do: hai combo đứng đầu có tên bắt đầu bằng "Vé máy bay khứ hồi … + phòng", nên dù đã trộn, kệ vẫn dễ trông như toàn vé bay.
- Test: `tests/unit/homeView.test.tsx` (tham số request), test `ProductCard`, và e2e `navigation.spec.ts` vẫn 1 request.
- Trang `/experiences` giữ tab golf riêng như hiện tại; quyết định 5 chỉ áp cho trang chủ.

### 1d. Docs

- `docs/spec/hop-dong-tich-hop-backend.md` §4.1: bảng tham số `GET /products` và đoạn `sort=popular`.
- `docs/spec/hop-dong-tich-hop-frontend.md`:
  - dòng 136 (3 giây → 10 giây, `k=5` → `k=4`);
  - hàng ④ (tham số của tab "Tất cả" và tab "Vé tham quan").
- `docs/spec/product.md` §4.1.2 ④: tab "Vé tham quan" gồm golf, thứ tự trộn, nhãn loại trên thẻ.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.8: trần theo taxonomy cho cold-start.

### 1e. Kiểm tra

- Unit test cho `interleave_by_taxonomy`:
  - kết quả là hoán vị, `total` bất biến, các trang nối tiếp nhau;
  - có taxonomy thì không đổi thứ tự;
  - golf vào nhóm vé tham quan;
  - trả 400 khi `diversify` đi cùng sort giá.
- Contract test cho catalog.
- Unit test cho `_top_products`: tối đa 2 món mỗi taxonomy.
- Bench cold-start: chạy lại theo mốc `src/evaluation/reports/eval-2026-10-09-recsys-coldstart-ac-rec-baseline-v2.md`, ghi report mới vào `src/evaluation/reports/`. Output cold-start đổi có chủ đích; nhánh cá nhân hoá phải giữ nguyên.
- Kiểm thủ công trên local: top 8 của "Tất cả" có 2 món mỗi nhóm khi đủ hàng.

## Giai đoạn 2 — Làm nhanh lượt tính khi trượt cache (không lệch PRD)

Phải làm trước hoặc cùng giai đoạn 3. Cache không giúp được các lượt sau một event mới (xem chi tiết, mua), mà đó lại là phần lớn lượt vào trang chủ trong luồng demo.

1. **Đo.**
   - Thêm thời gian từng bước vào log `recsys.recommend`: đọc CDP, vector lịch sử, ANN ngắn hạn, ANN dài hạn, vector phổ biến, ô khám phá, chấm điểm. Chỉ ghi log, không đổi contract.
   - Lấy p50/p95 theo nhánh trước và sau khi sửa. Nguồn số:
     - Cloud Logging, khi log backend của VM HA đã lên (đang làm ở `history/2026-10-12-monitor-ha-log-va-nhan-nhom.md`);
     - hoặc log load balancer cho đường `/api/v1/recommendations`.
   - Đếm số event của các tài khoản persona và test (chỉ đọc, qua bastion; người dùng chạy).
2. **Chạy song song các lượt Weaviate độc lập.**
   - Gồm u_short, u_long, vector phổ biến, và truy vấn của ô khám phá (chỉ phụ thuộc u_long, điểm đến và tập đã mua).
   - Ghép kết quả theo đúng thứ tự cũ, nên output giống hệt.
   - Thread pool tạo trong `main.py` rồi tiêm vào.
   - Thời gian từng bước phải gom ở luồng cha, vì `ContextVar` không đi theo sang thread con.
3. **Nạp sẵn vector sản phẩm vào RAM, ở nền.**
   - Khoảng 4.000 × 384 float32, cỡ 6 MB mỗi worker. Nạp lại khi `textHash` hoặc `modelVersion` đổi lúc reload.
   - Sau đó `vectors()` tra trong RAM, và `near_vector` gọi với `with_vectors=False`.
   - Chưa nạp xong thì gọi Weaviate như cũ.
   - Không lệch NFR-PERF-03, vì tra vector theo id không phải truy vấn tương đồng; ANN vẫn qua Weaviate.
   - Phải sửa câu "Backend không còn tải toàn bộ vector vào RAM lúc khởi động" (`hop-dong-tich-hop-search-recommendation.md:321`) và docstring `application/ports/vector_search.py:3`.
   - Cách này đổi thiết kế đã ghi trong `update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md` mục 4 (lấy vector lịch sử theo id mỗi request). Lần đó bỏ tải toàn bộ vì 453 s với Cohere 1024 chiều; nay là e5 384 chiều và tải ở nền. Người dùng đồng ý ngày 2026-10-12.
4. **Giới hạn 500 event** cho `events_for_user`, theo `hop-dong-tich-hop-cdp.md` §6 (code đang thiếu). Output đổi với tài khoản có hơn 500 event, nên phải chạy qua bench.
5. **Cổng.**
   - Parity offline == HTTP của `src/evaluation/recsys_bench` cho bước 2 và 3 (output y hệt).
   - Bench AC cho bước 4.
   - Đo latency trước và sau, ghi report vào `src/evaluation/reports/eval-YYYY-MM-DD-recsys-latency-*.md`.

## Giai đoạn 3 — Cache Redis (đề xuất đã chốt 2026-10-12)

Quy tắc chi tiết nằm trong đề xuất (khoá theo dấu vân tay event, TTL 900 s, giới hạn 64 KB, bỏ qua khi Redis lỗi, chống tính trùng, làm ấm sau đăng nhập). Thứ tự làm:

1. ~~Cập nhật PRD theo đề xuất (`architecture.md` §1/§4, `deployment-plan.md` §2), đổi trạng thái đề xuất và `git mv` sang `docs/prd/update-archive/`.~~ Xong 2026-10-12.
2. Contract: mô tả `diagnostics.userVectorCacheHit`, bỏ `[CHỜ DUYỆT: P3]`; làm cùng lần nâng 1.25.0 của giai đoạn 1.
3. Backend:
   - **Port:** `application/ports/recommendation_cache.py` (`get`, `put`, `try_lock`/`unlock` khoá tính kèm token; lỗi `RecommendationCacheUnavailable`).
   - **Cache nằm trong engine** (`application/recommendation/cache.py` + field `RecommendForUser.cache`), không phải lớp bọc riêng: engine đã đọc event thô, và đường CDP lỗi trả trước khi đụng cache nên kết quả lui không bao giờ được ghi.
     - Khoá: phiên bản engine (fingerprint catalog + metadata vector, fingerprint tập purchase dựng Popularity, `modelVersion`, `ENGINE_RULES_VERSION`, các knob của engine), namespace theo mã nguồn, user, k, destination, ngày VN, dấu vân tay event.
     - Lưu và trả JSON, nên mỗi request nhận bản riêng (`hit()` dùng chung dict `attributes`).
     - Đánh dấu `userVectorCacheHit`.
   - **Adapter:** `infrastructure/persistence/redis_recommendation_cache.py`, dùng client `redis` đồng bộ với `socket_timeout` 100 ms. Lỗi thì bỏ qua cache và ghi WARNING có giới hạn tần suất.
   - **Nối dây:** `core/config.py` (`recommend_cache_redis_url`, `recommend_cache_ttl_seconds`); `main.py` dựng `RecommendationCache` rồi truyền vào `build_recsys`. Cache nằm trong engine nên route và trợ lý dùng chung, không cần bọc `recommend`. Engine chỉ cache khi biết phiên bản catalog (`WeaviateVectorStore.version`).
   - **Làm ấm sau đăng nhập:** sau `/auth/session` và `/auth/login` thành công, chạy trên pool riêng 2 thread (không dùng `BackgroundTasks`, vì middleware log sẽ tính cả thời gian làm ấm vào request đăng nhập) cho `(cdpUserId, k=4, destination=None)`.
   - **Test:** bản giả trong `tests/fakes/`, unit test cho cache (hit, miss, event mới ra khoá mới, Redis lỗi, CDP lỗi không ghi, chống tính trùng), integration test với Redis tạm, và test kiến trúc.
4. Hạ tầng:
   - `.env.example` và `docker-compose.yml` (DB index chưa dùng; dev hiện dùng 1, 2, 3).
   - Không cần sửa `infra/terraform/environments/staging-ha/compose.ha.yml`: container backend đọc mọi biến từ `env_file` (`/etc/vota/backend.env`, chép từ secret).
   - Secret `vota-ha-backend-env`: người vận hành cập nhật; kiểm DB index đang dùng trên prod trước.
5. Spec: `hop-dong-tich-hop-search-recommendation.md` §5, §7.1, §10 S5; mục Recommendation của `hop-dong-tich-hop-backend.md`.
6. Đo tỷ lệ trúng cache và bộ nhớ Redis sau khi deploy. Cảnh báo bộ nhớ trên 80% đã có.

## Definition of Done

- Mỗi giai đoạn có entry `history/` riêng, test theo tầng (unit, contract, integration), test kiến trúc pass, và `validate_contract.py` pass khi đổi contract.
- Bench và report lưu ở `src/evaluation/reports/` cho giai đoạn 1 (cold-start) và giai đoạn 2 (parity, latency).
- Không đổi kết quả của nhánh cá nhân hoá, trừ bước giới hạn 500 event đã báo trước.

## Còn chờ người dùng

Không còn (mọi điểm đã chốt ngày 2026-10-12, xem "Quyết định đã chốt").

## Còn lại (sau khi code xong, 2026-10-12)

- **Bench và report của Definition of Done chưa chạy.** Môi trường bench prodcopy không còn: Postgres `127.0.0.1:55433` và collection `ProductE5SmallProdcopy` đã bị gỡ. Theo quy ước của plan, không tự dựng lại. Thay vào đó:
  - giai đoạn 1 và 2: test tương đương trong tiến trình (có pool và không có pool cho output giống hệt; vector nạp sẵn bằng bit với Weaviate local `ProductBench`);
  - giai đoạn 3: test tích hợp trên Redis tạm.

  Chi tiết trong các entry `history/2026-10-12-*.md`.
- **Đo sau deploy:** tỷ lệ trúng (`cache` trong log `recsys.recommend`), `stage_ms`, `events_read`, p95 theo route, bộ nhớ Memorystore.
- **Vận hành:** thêm `RECOMMEND_CACHE_REDIS_URL` (DB index chưa dùng) vào secret `vota-ha-backend-env`. Chưa có biến thì cache tắt, production ghi WARNING `recsys.cache.disabled`.
- **Hai điểm hiện thực khác phần "thay đổi source" của đề xuất:**
  - cache nằm trong engine (`application/recommendation/cache.py`), không phải lớp bọc riêng;
  - không sửa `compose.ha.yml`, vì biến lấy từ `env_file`.
