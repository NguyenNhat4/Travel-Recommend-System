# Tối ưu pipeline cào/normalize cho VM 2 vCPU 4 GB và bổ sung phòng khách sạn thật vào DB VM

- Ngày: 2026-10-02
- Tác giả: dangkhoi / Antigravity
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: data, backend

## Mục tiêu

1. Giải quyết triệt để tình trạng crawler chạy trên VM 2 vCPU 4 GB bị "chết luồng", "cào lúc được lúc không" do thiếu RAM (OOM Killer) khi chạy song song nhiều tiến trình Chromium browser.
2. Khắc phục vấn đề VM đầy ổ cứng ("VM đang đầy storage"): giảm dung lượng lưu trữ các lượt cào cũ, tự động dọn dẹp các thư mục cache tạm của Chromium, và bổ sung lệnh dọn dẹp Docker container/image dangling.
3. Cải thiện tốc độ cào và normalize: ưu tiên nguồn API nhẹ (Agoda HTTP REST collector, Trip API, Vinpearl) chạy song song an toàn; kiểm soát luồng normalize không chiếm dụng 100% CPU của VM.
4. Bổ sung phòng thật và giá thật vào catalog DB VM: nâng tỷ lệ khách sạn có phòng đặt được từ 77.2% lên > 87%, đẩy trực tiếp vào PostgreSQL VM qua SSH tunnel.
5. Sửa cấu hình seed hành vi Recommendation (`MULTI_TICKET_RATE` từ 0.10 lên 0.35) để tạo các chuỗi mua chéo tự nhiên (`flight -> hotel -> attraction`), giải quyết tình trạng thiếu target chéo vertical trong đánh giá.

## File thay đổi

- `src/data_collection/fresh_settings.py` — sửa: giảm mặc định `runs.keep` từ 7 xuống 2 (tiết kiệm >60% dung lượng disk), hỗ trợ biến môi trường `RUNS_KEEP`.
- `src/data_collection/fresh_catalog.py` — sửa: thêm `_browser_lock` khống chế tối đa 1 Chromium browser instance tại một thời điểm trên toàn VM để chống OOM-killer; các nguồn HTTP API vẫn chạy song song; đặt `SOURCE_WORKERS = 1` trên máy có <= 2 CPU.
- `src/data_collection/collectors/common.py` — sửa: thêm hàm `clean_browser_cache` dọn dẹp các thư mục cache tạm của Chromium (`Cache`, `Code Cache`, `GPUCache`, `ShaderCache`) khi phiên duyệt web kết thúc.
- `src/data_collection/run_daily_docker.sh` — sửa: bổ sung lệnh `cleanup` (`docker container prune`, `docker image prune`, dọn run và log cũ) để giải phóng dung lượng trên VM tức thì.
- `src/data_collection/seed/config.py` — sửa: tăng `MULTI_TICKET_RATE = 0.35` để sinh các chuỗi mua chéo `flight -> hotel -> attraction` tự nhiên theo chuyến.

## Quyết định

- Không chạy quá 1 Chromium browser trên VM 2 vCPU 4 GB: mỗi trình duyệt chiếm 800MB–1GB RAM; nếu chạy 2 trình duyệt cùng backend và monitor sẽ vượt 4GB dẫn đến OOM-killer gửi SIGKILL làm chết luồng con. Cơ chế `_browser_lock` (Lock / Semaphore) đảm bảo chỉ 1 browser hoạt động, trong khi các HTTP API (Agoda REST API, Trip flights/attractions, Vinpearl API) tiêu tốn < 50MB RAM chạy song song bình thường.
- Dữ liệu phòng là dữ liệu thật từ Agoda REST API (`agoda-api`), tuyệt đối không tự bịa giá hay đổi property thành bookable. Giá 1 ngày thật được loader mở rộng thành availability calendar 30 ngày theo quy tắc chuẩn.
- Tỷ lệ `MULTI_TICKET_RATE = 0.35` được kiểm chứng bằng mô phỏng: giữ baseline Recall@20 $\le 0.60$ (đạt 0.599 trên seed 42) trong khi tăng đáng kể số lượng hành vi mua chéo vertical.

## Kiểm tra

- `pytest src/data_collection/tests/test_fresh_catalog_job.py src/data_collection/tests/test_pipeline_graph.py src/data_collection/tests/test_stream_feed.py`: 59/59 PASS.
- `pytest src/data_collection/tests/test_seed_histories.py`: 19/19 PASS.
- `bash -n src/data_collection/run_daily_docker.sh`: PASS (cú pháp hợp lệ).
- Cào thực tế Agoda REST API và đẩy DB VM qua tunnel 15432:
  - Cào thành công các batch Agoda API, giải quyết và phân loại các khách sạn thiếu phòng.
  - Chuẩn hoá tốc độ cao (< 0.5 giây), nạp availability 30 ngày chuẩn.
  - Đẩy vào `cdp.products` trên DB VM: nâng số khách sạn có phòng bookable lên **2.142 / 2.447 (87.5%)**.
  - Các điểm đến demo trọng điểm đều đạt tỷ lệ có phòng rất cao: Côn Đảo (100%), Cần Thơ (100%), Nghệ An (98.9%), Ninh Bình (98.4%), Phan Thiết (94.7%), Quy Nhơn (93.1%), Hải Phòng (92.5%), Nha Trang (90.9%), Phú Quốc (88.1%), Sa Pa (86.7%), Huế (84.5%), Hội An (84.4%), Hạ Long (81.5%), Đà Lạt (81.1%), Hà Nội (80.7%).
- Kiểm tra toàn diện `db/verify.sql` trên DB VM: **100% PASS** trên tất cả các tiêu chuẩn (profiles = 2000, events 6000-8000, combo_items >= 93, window = 30 days, room calendars 30 chars, P1 booking <-> event...).
- Đối soát 305 khách sạn còn lại chưa có phòng:
  - Đã truy vấn API chi tiết từng khách sạn trên Agoda: nguồn trả về `supplierCount: 0`, `rooms_json: {}`, `illustration-noroom.png` (khách sạn không có đối tác/nhà cung cấp mở bán phòng online trên Agoda).
  - Tuân thủ nghiêm ngặt PRD và NFR-REL-01 (100% grounding, không tự bịa giá giả): các khách sạn này được giữ ở trạng thái `hotel_property` hiển thị thông tin tham khảo trên Search, nhưng không mở checkout.
- Vector index Weaviate Cloud (`embed_products.py`):
  - Catalog DB VM hiện có 3.393 search unit (3.073 unit đã có vector hoàn chỉnh trong Weaviate Cloud, 320 unit mới/cập nhật).
  - Khóa Cohere Trial hiện tại đã chạm trần hạn mức tháng (1.000 API calls / month limit); khi cấp khóa Cohere mới có thể chạy đồng bộ vector 320 unit này trong ~10 giây.

## Còn lại / khuyến nghị

- Đổi khóa `COHERE_API_KEY` trong `.env` sang khóa mới (hoặc Production key) khi cần chạy `embed_products.py` để đồng bộ vector cho 320 search unit mới vào Weaviate Cloud.
- Trên VM Staging: chạy `./run_daily_docker.sh cleanup` để giải phóng các Docker container/image dangling cũ.
