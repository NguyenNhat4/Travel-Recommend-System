# Recommender Architecture Lab

Streamlit workbench so sánh 10 prototype recommender trên cùng catalog và cùng temporal holdout:

1. Random baseline
2. Global popularity
3. Popularity theo điểm đến và mùa
4. Content-based theo thuộc tính có cấu trúc
5. Content-based multilingual embedding
6. Item-item collaborative filtering
7. Implicit-feedback ALS
8. Personalized PageRank trên user-item graph
9. Markov next-item sequence
10. Hybrid contextual

Đây là **offline evaluator**, tách khỏi Streamlit itinerary agent tại `src/evaluation/agent/streamlit_app.py`. App chỉ đọc PostgreSQL và có hai chế độ: benchmark batch (holdout purchase mới nhất của mỗi user) và persona explorer. Các model dùng chung eligibility `catalog.product_meta.is_recommendable`; availability được đo thành metric thay vì lọc trước để kết quả còn ý nghĩa so sánh.

Expander **Kiến trúc 10 recommender** trong app vẽ luồng catalog/CDP → temporal split → 10 phương pháp → eligibility/ranking → metrics và export bằng Mermaid. Browser cần truy cập Mermaid CDN để vẽ; mã Mermaid được giữ trong iframe để xem nếu CDN không tải được.

## Điều kiện

- Python 3.10+.
- PostgreSQL local đã seed bằng `make demo-db`.
- Cài dependency backend và Streamlit:

```bash
python -m pip install -r src/backend/requirements.txt
python -m pip install -r src/evaluation/requirements.txt
```

- Cấu hình hai URL đọc dữ liệu. `DATABASE_URL` cần role `vota_app` để đọc catalog; `CDP_DATABASE_URL` cần role chỉ đọc như `cdp_eval_login`. Không dùng `SEED_DATABASE_URL` trong app.

```bash
export DATABASE_URL='postgresql://vota_app_login:vota@localhost:5432/vota'
export CDP_DATABASE_URL='postgresql://cdp_eval_login:eval@localhost:5432/vota'
```

Có thể đặt `EMBED_MODEL` (mặc định `intfloat/multilingual-e5-base`) và `EMBED_CACHE_DIR` (mặc định `.embcache`). Lần chạy đầu có thể tải model và embed catalog; lần tiếp theo dùng cache.

## Chạy

Từ repository root:

```bash
python -m streamlit run src/evaluation/streamlit_app.py
```

Mở URL local mà Streamlit in ra. Chọn **Benchmark batch** để giữ lại purchase mới nhất cho từng user, fit mọi phương pháp trên cùng phần train và xuất kết quả CSV/JSON. Chọn **Persona explorer** để xem top‑K, taxonomy, destination, availability, điểm và mô tả cơ sở xếp hạng của các model đã chọn. Các sản phẩm đã xuất hiện trong lịch sử user sẽ bị loại khỏi gợi ý.

## Chỉ số

- Recall@10 và Recall@20: tỷ lệ target purchase xuất hiện trong top K.
- NDCG@10: target càng đứng cao thì điểm càng lớn.
- Cross-category rate: tỷ lệ gợi ý thuộc taxonomy chưa mua trong chuyến gần nhất được quan sát trong train.
- Availability precision: tỷ lệ gợi ý có `available=true` trong snapshot catalog hiện tại.
- Catalog coverage: phần search unit được đề xuất ít nhất một lần trong top‑20.
- p95/p99 rank runtime: phân vị 95 và 99 thời gian xếp hạng một user; không gồm fit hoặc tải model.

Split được tái lập: mỗi user có purchase hợp lệ giữ lại purchase mới nhất theo `timestamp`, sau đó `productId`, rồi vị trí đầu vào để xử lý timestamp trùng. Train chỉ chứa event có thời điểm sớm hơn timestamp holdout; mọi event cùng thời điểm hoặc xảy ra sau target đều bị loại để tránh leakage. Không có target thì user vẫn có thể đóng góp event vào train, nhưng không được tính metric. Những event có product không resolve trong search-unit catalog không thể làm target holdout.

## Giới hạn

CDP seed tạo lịch sử tổng hợp; metric chứng minh pipeline evaluation chạy nhất quán, không phải hiệu quả dự kiến trên khách thật. Random là sanity baseline. ALS, graph và sequence được triển khai nhỏ gọn bằng NumPy/Python để có thể chạy cục bộ; chúng chưa được tuned bằng dữ liệu hành vi production. Hybrid dùng trọng số minh họa cố định, không học từ target holdout.
