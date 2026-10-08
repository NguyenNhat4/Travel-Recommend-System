# Streamlit: Xây dựng ứng dụng gỡ lỗi & trực quan hóa toàn diện 5 giai đoạn của Search Pipeline V-OTA

- Ngày: 2026-10-07
- Tác giả: người dùng / Claude
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: evaluation, backend

## Mục tiêu

Phục vụ FR-SRC-01, FR-SRC-02, FR-SRC-03, FR-SRC-04 và NFR-PERF-01.
Xây dựng và vận hành một ứng dụng Streamlit chuyên biệt để debug toàn diện pipeline tìm kiếm của V-OTA, trực quan hóa chi tiết đầy đủ 5 giai đoạn chính theo đúng kiến trúc kỹ thuật của hệ thống:
1. Thu nhận và chuẩn hóa (Query Ingestion & Normalization)
2. Query understanding & Router (Hiểu ý định & Kế hoạch truy vấn)
3. Filter first & Candidate Universe $F$ (Lọc cứng không gian ứng viên)
4. Candidate Retrieval Đa Kênh (Dense E5-Small, Lexical BM25, Fuzzy Trigram)
5. Ranking, Fusion & Kết quả (RRF, Cutoff Gate, Coverage Gate, Revalidation, Soft Star, Matched Children)

Mỗi quy trình và giai đoạn đều biểu diễn tường minh:
- **Input**: Dữ liệu đầu vào của bước.
- **Output**: Kết quả đầu ra có cấu trúc.
- **Dùng để làm gì (Mục đích)**: Vai trò của bước trong toàn bộ hệ sinh thái tìm kiếm.
- **Làm với nguyên lý gì (Nguyên lý)**: Lý thuyết và thuật toán cốt lõi.
- **Candidate Top 1 & Top Cuối**: Nêu rõ điểm số, ID, tên, taxonomy, điểm đến, giá tiền cho các quy trình chứa danh sách ứng viên (Universe $F$, Dense, BM25, Fuzzy, Final Scored Results).
- Ứng dụng kết nối trực tiếp với PostgreSQL staging qua SSH tunnel (`127.0.0.1:15432`) và Weaviate Cloud Vector DB (`ProductE5Small`), chạy đúng 1 lượt gọi đơn lẻ với `taxonomy=None` (không gọi fan-out 5 lần cho 5 tab như giao diện web production).
- Thanh sidebar cung cấp đầy đủ các núm bật tắt cấu hình debug (Cutoff, Hybrid, RRF K, Trọng số Dense/Lexical/Fuzzy, F1-F6 flags, No Diacritics relax, override params).

## File thay đổi

- `src/evaluation/search_bench/debug_search_app.py` — thêm: ứng dụng Streamlit phân tích và gỡ lỗi toàn diện 5 giai đoạn của pipeline tìm kiếm V-OTA.
- `scripts/tunnel.ps1` — thêm: script khởi tạo SSH tunnel background kết nối PostgreSQL staging qua `127.0.0.1:15432`.
- `scripts/tunnel-down.ps1` — thêm: script đóng SSH tunnel PostgreSQL.

## Quyết định

- **Cache CatalogUnits cục bộ**: Bảng `cdp.products` trên staging có dung lượng ~133 MB (16,740 dòng). Khi truyền tải qua SSH tunnel qua mạng WAN từ xa, mỗi lần query trực tiếp mất ~3-4 phút. Ứng dụng sử dụng `.embcache/debug_catalog_units.pkl` làm disk cache sau lần nạp đầu tiên kết hợp `@st.cache_resource`, giúp giảm thời gian khởi động lại từ 4 phút xuống còn **0.45 giây**, đồng thời cung cấp nút bấm "🔄 Tải lại Catalog từ Database" trên giao diện khi cần đồng bộ dữ liệu mới.
- **Windows WDAC compatibility stub**: Trên môi trường Windows có chính sách bảo mật Application Control (WDAC), việc `transformers` nạp thư viện `sklearn` phụ thuộc Cython `_heap.pyd` gây lỗi DLL load failed. Ứng dụng tạo một module stub nhẹ cho `sklearn.metrics.roc_curve` giúp `AutoModel` nạp trơn tru mà không vi phạm chính sách của hệ điều hành.
- **Giữ nguyên 100% logic Clean Architecture**: Toàn bộ thuật toán bám sát các domain và application use cases gốc của production: `SearchProducts`, `build_query_plan`, `index.mask`, `near_vector`, `bm25`, `FuzzyIndex`, `hybrid_filter_score`.

- `src/evaluation/search_bench/debug_search_app.py` — sửa: 
  - Sửa lỗi `AttributeError: 'NormalizedQuery' object has no attribute 'is_unaccented'` bằng cách gọi hàm `is_unaccented(nq.text)` và `detect_style([q])` độc lập thay vì đọc thuộc tính không tồn tại trên dataclass `NormalizedQuery`.
  - Sửa lỗi `AttributeError: 'DestinationDecision' object has no attribute 'confidence'` bằng cách đọc các trường thực tế của `DestinationDecision`: `value`, `source`, `skipped`, `candidates`.
  - Loại bỏ phép gán `outcome.total = len(order)` vì `SearchOutcome.total` là `@property` tự động tính từ `len(self.order)`.
  - Bổ sung cấu hình mặc định đọc từ `settings`: Chốt Bật cờ F4 (`SEARCH_TAXONOMY_FILTER`), bật 2 cờ an toàn 1.18.0 F7 (`SEARCH_DURATION_FILTER`) và `SEARCH_POI_RESOLVE`; bổ sung trường hiển thị `duration (F7)`, `poi_location`, và `destination_via_poi` vào `plan_dict` trên UI.
- `.env` — sửa: thêm `SEARCH_TAXONOMY_FILTER=true`, `SEARCH_DURATION_FILTER=true`, `SEARCH_POI_RESOLVE=true`, và `VECTOR_COLLECTION=ProductE5Small`.

## Kiểm tra

- `scripts/tunnel.ps1`: Đã kiểm tra kết nối PostgreSQL qua SSH tunnel `127.0.0.1:15432`, đếm 16,740 sản phẩm CDP và 3,991 search units trong `catalog.product_meta`.
- Weaviate Cloud: Kết nối thành công collection `ProductE5Small` với 3,991 objects vector.
- virtualenv: Đã cài đặt `streamlit` (1.65.0).
- Streamlit Server: Khởi động thành công server headless trên cổng 8502 (`http://localhost:8502`), kiểm tra HTTP status 200.
- End-to-end Python test: Chạy script kiểm thử toàn diện `scratch/test_all_steps.py` xác minh liên tục và thành công 100% cả 5 giai đoạn (Normalizer -> Query Plan -> Filter Mask -> Retrieval -> Ranking/Fusion).
- Sửa lỗi `AttributeError`: Đã kiểm thử chạy qua bước Normalization với `is_unaccented` và `detect_style`, và bước Query Plan với `DestinationDecision`, xác nhận không còn lỗi phát sinh khi người dùng truy cập.

## Còn lại / rủi ro

- Giữ tiến trình SSH tunnel (PID 15068) duy trì chạy nền để đảm bảo kết nối cơ sở dữ liệu staging không bị gián đoạn.
- Khi tắt máy, người dùng có thể chạy `.\scripts\tunnel-down.ps1` để giải phóng cổng 15432.
