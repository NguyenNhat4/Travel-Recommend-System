# Streamlit Debug Search: Nâng cấp trực quan hóa F7, Search POI Resolve và F4 Taxonomy

- Ngày: 2026-10-08
- Tác giả: tqanh123 (người dùng yêu cầu) / Antigravity
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: evaluation, backend

## Mục tiêu

1. Nâng cấp và cải tiến giao diện Streamlit Debug Search App (`src/evaluation/search_bench/debug_search_app.py`) để biểu diễn chuyên sâu, chính xác và trực quan 2 cờ an toàn theo Contract 1.18.0:
   - **F7: Duration Filter (`SEARCH_DURATION_FILTER`)**: Nhận diện cụm thời lượng ("3 ngày 2 đêm", "3N2Đ", N ngày M đêm...) và loại bỏ span này khỏi chuỗi `lexical_text` dùng cho BM25 để chống nhiễu (loại bỏ false-positive như khách sạn "Chợ Đêm"). An toàn 100% không làm rỗng tập ứng viên $F$.
   - **Search POI Resolve (`SEARCH_POI_RESOLVE`)**: Ánh xạ địa danh con/landmark gazetteer (Hồ Hoàn Kiếm, Bãi Dài, Cầu Rồng...) về Điểm đến chính thức (Hà Nội, Nha Trang, Đà Nẵng...) và kích hoạt bộ lọc cứng F1 (`destination_via_poi = True`).
   - **F4: Taxonomy Filter (`SEARCH_TAXONOMY_FILTER`)** (Đã chốt bật): Lọc cứng không gian ứng viên $F$ theo loại hình sản phẩm (hotel, flight, attraction...).
2. Khắc phục triệt để lỗi Windows WDAC / AppLocker policy:
   `ImportError: DLL load failed while importing _uarray: An Application Control policy has blocked this file.`
   khi `transformers` import `AutoModel` nạp `multilingual-e5-small`.

## File thay đổi

- `src/evaluation/search_bench/debug_search_app.py` — sửa:
  - Bổ sung compatibility stub cho `scipy.optimize` để ngăn `_uarray.pyd` DLL load block.
  - Bổ sung thanh nút bấm **Quick Presets** thử nghiệm nhanh 5 kịch bản (F4+F7+POI Hà Nội, F4+F7+POI Nha Trang, F7+Entity Phú Quốc, F4+POI Đà Nẵng, F4+F5 Tuyến bay).
  - Nâng cấp Sidebar hiển thị rõ trạng thái các cờ `[ĐÃ CHỐT BẬT]` (F4), `[BẬT - Tiêu cụm khỏi BM25]` (F7), `[BẬT - Ánh xạ vào F1]` (POI).
  - Nâng cấp Card Mục đích & Nguyên lý của Giai đoạn 2 (QU), Giai đoạn 3 (Filter first $F$), và Giai đoạn 4B (BM25).
  - Thêm 3 Callout Cards trực quan (F4 Taxonomy, F7 Duration, POI Resolve) làm nổi bật thông tin nhận diện.
  - Thêm bảng so sánh biến đổi chuỗi truy vấn (Raw Query ➔ Normalized Query ➔ BM25 Lexical Text sau khi F7 consume).
  - Làm rõ trong Giai đoạn 3: Điểm đến suy ra từ POI Resolve, Taxonomy từ F4, và khẳng định tính an toàn của F7 (không làm rỗng $F$).
  - Làm rõ trong Giai đoạn 4B: Hiệu quả chống nhiễu của F7 trên chuỗi từ khóa BM25.
- `src/backend/app/infrastructure/embeddings/local_e5_embedder.py` — sửa:
  - Bổ sung Windows WDAC stubs cho `scipy.optimize` và `sklearn.metrics` trong hàm `_load()`, giúp `AutoModel.from_pretrained` nạp an toàn trên môi trường Windows mà không bị chặn DLL C-extension.

## Quyết định

- Tuân thủ nghiêm ngặt Clean Architecture và hợp đồng Contract 1.18.0 (`history/2026-10-07-search-duration-poi-entity-contract-1-18-0.md`).
- F7 chỉ tiêu span khỏi `lexical_text` của BM25, không đưa vào `mask_kwargs` của Candidate Universe $F$ vì catalog hiện tại chưa có trường thời lượng (P1).
- POI Resolve đưa điểm đến vào `destination` và đặt `destination_via_poi = True`, từ đó lọc cứng điểm đến trong $F$ khi F1 bật.
- Cắt đứt chuỗi import `_uarray.pyd` bằng stub `scipy.optimize.linear_sum_assignment` mà không làm ảnh hưởng đến các submodule khác của `scipy` (như `scipy.sparse`).

## Kiểm tra

- `.\.venv\Scripts\python.exe -m py_compile src/evaluation/search_bench/debug_search_app.py src/backend/app/infrastructure/embeddings/local_e5_embedder.py`: **PASS** (Exit 0).
- Chạy thử trực tiếp `build_embedder`:
  - `Embed shape: (384,) Norm: 1.0`
  - `SUCCESS!` (Exit code 0).
- Mô phỏng độc lập qua python:
  - Query: `"khách sạn gần Hồ Hoàn Kiếm 3 ngày 2 đêm"`
  - `Taxonomy: hotel strong`
  - `Duration: 3 2 query`
  - `POI: Hồ Hoàn Kiếm -> Hà Nội (destination_via_poi: True)`
  - `Destination: Hà Nội`
  - `Lexical text: 'gần Hồ Hoàn Kiếm'`
- Streamlit server trên cổng 8502 (Task 1691): HTTP 200 OK (`http://localhost:8502/_stcore/health`).

## Còn lại / rủi ro

- Không có. Ứng dụng Streamlit debug chạy mượt mà, chia sẻ chung Postgres (qua OpenSSH tunnel 15432) và Weaviate Cloud (`ProductE5Small`).
