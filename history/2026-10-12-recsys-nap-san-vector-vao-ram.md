# Gợi ý: nạp sẵn vector sản phẩm vào RAM ở nền (ANN vẫn qua Weaviate)

- Ngày: 2026-10-12
- Tác giả: tqanh123 (đồng ý 2026-10-12) / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành (đo latency trên cloud chưa làm, xem "Còn lại")
- Phạm vi: backend, docs
- Liên quan: `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (giai đoạn 2, bước 3); đổi thiết kế ghi ở `docs/prd/update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md` mục 4

## Mục tiêu

Mỗi request gợi ý đi qua Weaviate Cloud khác vùng cho cả những việc không phải truy vấn tương đồng:

- lấy vector của sản phẩm trong lịch sử (`vectors()`, nằm trên đường găng, không chạy song song được);
- lấy vector của món phổ biến;
- tải vector đính kèm 200 hit của mỗi lượt ANN.

Vector sản phẩm không đổi giữa hai lần index, chỉ khoảng 4.000 × 384 float32 (cỡ 6 MB). Giữ chúng trong RAM thì bỏ được các lượt và phần payload đó. Phục vụ NFR-PERF-01. Người dùng đồng ý ngày 2026-10-12. Lần 24/09 bỏ cách tải toàn bộ vì mất 453 s (Cohere 1024 chiều, JSON qua REST); lần này là e5 384 chiều qua gRPC, tải ở nền.

## File thay đổi

- `src/backend/app/infrastructure/vectors/preloaded_vector_search.py` — thêm: `PreloadedVectorSearch`, decorator cài `VectorSearchPort` quanh `WeaviateVectorSearch`.
  - `vectors()` và vector đính kèm hit lấy từ RAM; ANN vẫn gọi Weaviate (với `with_vectors=False` khi bảng đã đủ).
  - `expect(desired, stored)` bỏ mục đã đổi `modelVersion`/`textHash`.
  - `preload(stop)` lấy phần còn thiếu theo khối, chỉ giữ mục có metadata khớp, và dừng được giữa hai khối.
  - Bảng là snapshot bất biến, thay dưới khoá ghi; người đọc không cần khoá; vector chỉ đọc.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa:
  - thêm `WeaviateVectorSearch.vectors_with_metadata(ids)` (cùng đường gRPC với `vectors()`);
  - `WeaviateVectorStore.load()` gọi `search.expect(...)` sau bước kiểm (lần nạp lỗi không đổi bảng);
  - sửa docstring.
- `src/backend/app/main.py` — sửa:
  - `build_recsys` bọc `WeaviateVectorSearch` một lần khi `RECOMMEND_PRELOAD_VECTORS` bật;
  - `RecsysRefresher` lên lịch `_run_preload` ở nền sau mỗi lần publish (không chạy chồng), log `recsys.vectors.preload`;
  - `wait_prewarm` chờ cả task này khi shutdown;
  - sửa docstring module.
- `src/backend/app/core/config.py` — sửa: `recommend_preload_vectors` (mặc định `True`).
- `src/backend/app/core/logging_config.py` — sửa: allowlist `recsys.vectors.preload`.
- `src/backend/app/application/ports/vector_search.py` — sửa: docstring (adapter được giữ bảng vector theo id; ANN vẫn qua index; engine không quét tuần tự).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: thêm đoạn "Cập nhật 12/10/2026" sau phần chốt 24/09 (nạp sẵn theo id, gọi song song).
- `docs/spec/logging-schema.md` — sửa: sự kiện `recsys.vectors.preload`.
- `.env.example` — sửa: dòng chú thích `RECOMMEND_PRELOAD_VECTORS`.
- `src/backend/tests/unit/infrastructure/test_preloaded_vector_search.py` — thêm, 8 test:
  - trước khi nạp thì chuyển thẳng xuống Weaviate;
  - sau khi nạp thì lấy từ RAM, vector chỉ đọc, id không có object thì không hỏi;
  - `near_vector` gọi Weaviate với `with_vectors=False` rồi đính vector;
  - `textHash` đổi thì bỏ mục đó, lần nạp sau chỉ lấy lại mục đó;
  - metadata lệch trong lúc nạp thì không lưu;
  - `stop`;
  - chuyển tiếp `bm25`, `metadata`, `close`, `dimension`;
  - đọc đồng thời trong lúc nạp.
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — sửa: thêm test `vectors_with_metadata` và test `expect` chỉ chạy sau bước kiểm. Test cũ "`load()` chỉ một lượt `fetch_objects`" giữ nguyên.
- `src/backend/tests/unit/api/test_recsys_refresher.py` — sửa: thêm test nạp nền sau mỗi lần publish và được chờ khi shutdown, không chạy chồng, lỗi chỉ ghi WARNING.
- `history/2026-10-12-recsys-nap-san-vector-vao-ram.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD:** tra vector theo id không phải truy vấn tương đồng; ANN vẫn qua Weaviate (NFR-PERF-03). Chỉ đổi spec và docstring port.
- **Nạp ở nền, không chặn khởi động** (giữ ý của quyết định 24/09). Chưa nạp xong thì mọi lời gọi chuyển thẳng xuống Weaviate như trước.
- **Lấy qua gRPC `fetch_objects`,** không qua REST `fetch` (JSON), để vector float32 giống hệt vector Weaviate trả kèm ANN.
- **Khoá của mỗi mục là metadata Weaviate** (`modelVersion`, `textHash`) lúc nạp, không phải text hash của catalog. RAM khớp đúng thứ Weaviate đang giữ, kể cả khi object còn text cũ.
- **Bọc một lần trong `build_recsys`:** `RecsysRefresher` truyền lại store ở các lần nạp sau, nên bảng sống qua reload.

## Kiểm tra

- `pytest -q -p no:cacheprovider src/backend/tests src/evaluation/recsys_bench/tests`: 3073 passed, 42 skipped.
- Kiểm thật chỉ đọc trên Weaviate local của bench (`sbench-weaviate-1`, collection `ProductBench`, 300 id; script trong scratchpad, không commit):
  - `preload` 300 vector trong 0,138 s;
  - `vectors()` từ RAM bằng từng bit với Weaviate;
  - `near_vector` qua decorator cùng id, cùng vector, cùng điểm với `near_vector(with_vectors=True)` gốc.

## Còn lại / rủi ro

- Parity HTTP 60/60 và đo latency trước/sau trên prodcopy chưa chạy được: Postgres prodcopy và collection `ProductE5SmallProdcopy` đều không còn trên máy. Số thật đọc từ `stage_ms` và `recsys.vectors.preload` trên staging sau khi deploy.
- **Lượt nạp đầu trên staging:** khoảng 4 khối × 1.000 vector qua Weaviate Cloud khác vùng, mỗi tiến trình. Rollback không cần redeploy bằng `RECOMMEND_PRELOAD_VECTORS=false`.
- RAM có thể trễ so với Weaviate tối đa một chu kỳ nạp (900 s) khi job index ghi lại object.
