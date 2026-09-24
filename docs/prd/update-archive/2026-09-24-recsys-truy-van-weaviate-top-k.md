# RecSys truy vấn Weaviate lấy top-K mỗi request, không tải toàn bộ vector vào RAM

- Ngày: 2026-09-24
- Người đề xuất: nhatnm / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: nhatnm (duyệt plan triển khai), 2026-09-24
- PRD bị ảnh hưởng: không đổi nội dung PRD — thay đổi đưa code **về đúng** `docs/prd/architecture.md` §5 mục 5 và `docs/prd/requirements.md` NFR-PERF-03. Phần phải đổi là spec và mô tả contract: `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.2–2.4 và rủi ro S8, `src/shared/contracts/schemas/common.yaml` (`SearchMode`), `src/shared/contracts/schemas/recommendations.yaml` (ghi chú `[C4]`).
- Mã FR/NFR: FR-SRC-02, FR-REC, NFR-PERF-03

## Lý do

- **Khởi động quá chậm.** Backend hiện tải toàn bộ 3.183 vector (1024 chiều, ~42 MB JSON) từ Weaviate vào RAM lúc khởi động. Đo ngày 2026-09-24 trên Weaviate Cloud: mất 453 giây, vượt ngưỡng chờ 300 giây của `make web`, nên RecSys không lên được. Catalog càng lớn thì càng chậm.
- **Code đang lệch PRD.** PRD `architecture.md` §5 ghi rằng use case search "đưa vector sang Weaviate để lấy top-K", và NFR-PERF-03 ghi "đi qua chỉ mục HNSW của Weaviate, không quét tuần tự". Code hiện lại quét tuần tự trên RAM (`EXACT_FILTER_SCORE`).
- **Spec đã tự đánh dấu cần duyệt lại.** Rủi ro S8 và ghi chú ở §2.4 của spec nói rằng tiền đề của exact scan ("vector nằm trong `shared_buffers` của Postgres") đã hết đúng từ khi chuyển sang Weaviate.

## Nội dung đề xuất

Cả ba engine chuyển sang `ANN_CANDIDATE_SCORE`. Giá trị này **đã có sẵn** trong enum `SearchMode`, nên không đổi schema hay tên field nào.

1. **Lọc trước bằng `productId`.** Metadata (taxonomy, destination, available, recommendable, parent) vẫn nạp từ Postgres lúc khởi động; bước này nhanh, 11.387 dòng đọc trong vài giây. Mỗi request tính tập `productId` hợp lệ trên metadata, rồi gửi `nearVector` kèm filter `productId ContainsAny [...]`. Nhờ đó vẫn giữ được "lọc trước rồi chấm điểm" (lý do `[C4]` của recommendations) mà **không** thêm property nào vào Weaviate. Collection vẫn chỉ giữ vector và `productId`, đúng `data-model.md`.
2. **Search.** Embed query bằng `search_query`, gọi `nearVector` với filter, lấy tối đa `candidateK` kết quả (mặc định 200), bỏ các kết quả dưới `cutoff`. `total` và `facets` tính trên tập ứng viên này, nên `approximate = true`, `totalExact = false`, `facetsExact = false`, đúng như contract bắt buộc khi đổi mode. Bất biến §2.3 vẫn giữ nhưng hiểu là trên tập ứng viên.
3. **Similar.** Lấy vector của sản phẩm gốc rồi gọi `nearVector` với filter: cùng taxonomy, loại chính nó và các sản phẩm anh em cùng cha.
4. **Recommendations.** Lấy vector của các sản phẩm trong lịch sử người dùng theo id (vài chục vector). Dựng `u_short`/`u_long` như hiện tại, rồi gọi hai `nearVector` có filter (candidate mask hiện hành), mỗi lần `candidateK` kết quả, kèm vector. Sau đó chấm điểm kết hợp popularity, MMR và `explain` chạy trên tập hợp của hai kết quả này như cũ. Cold start không cần vector nên không đổi.
5. **Giao thức.** Weaviate Cloud của nhóm **tắt GraphQL** (`graphql api is disabled`), nên truy vấn `nearVector` đi qua gRPC bằng thư viện `weaviate-client` v4. Docker compose đã mở cổng 50051 cho gRPC. Job `embed_products` giữ REST như hiện tại.
6. **Spec §2.4.** Bỏ ngưỡng lật "số vector > 50.000 hoặc p95 > 50 ms", ghi rằng mode mặc định là `ANN_CANDIDATE_SCORE`. S8 chốt theo hướng (b): đổi cam kết `facets` thành xấp xỉ, có khai báo qua `facetsExact = false`.

**Hệ quả cần chấp nhận:**

- `total` và `facets` của `/search` là xấp xỉ, vì chỉ đếm trong tối đa `candidateK` ứng viên.
- `/recommendations` chỉ trộn popularity trong tập ứng viên gần profile. Sản phẩm rất phổ biến nhưng xa profile sẽ không còn lọt vào.
- Mỗi request tốn thêm một lượt gọi mạng tới Weaviate. Trên đường mạng hiện tại, một round-trip đo được khoảng 1,8 giây, cao hơn ngân sách p95 250 ms của NFR-PERF-01. Chạy Weaviate local, như `deployment-plan.md` §1 ghi cho môi trường dev, thì không gặp vấn đề này.

## Thay đổi source sau khi chốt

- `src/shared/contracts/schemas/common.yaml`: sửa mô tả `SearchMode`. `schemas/recommendations.yaml`: sửa ghi chú `[C4]`. Không đổi field. Chạy `validate_contract.py`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md`: §2.2–2.4 và S8.
- `src/backend/app/application/ports/`: thêm port `VectorSearchPort` (`near(vector, allowed_ids, limit, with_vectors)`, `vectors(ids)`). `UnitIndex` bỏ ma trận `E`, chỉ giữ metadata.
- `src/backend/app/infrastructure/vectors/weaviate_store.py`: adapter gRPC hiện thực `VectorSearchPort`, bỏ hàm tải toàn bộ vector lúc khởi động.
- `src/backend/app/application/search/use_cases.py`, `application/recommendation/use_cases.py`, `domain/search/scoring.py`, `domain/recommendation/profile.py`: chấm điểm trên tập ứng viên thay vì toàn bộ `E`.
- `src/backend/app/main.py`: `build_recsys` chỉ nạp metadata.
- `src/backend/requirements.txt`: thêm `weaviate-client>=4`.
- `src/backend/tests/fakes/`: fake `VectorSearchPort` chạy offline. Thêm và sửa unit test cho search, similar và recommendations.
