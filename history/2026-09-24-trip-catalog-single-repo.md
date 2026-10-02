# Cào catalog mới trong một repo Travel

- Ngày: 2026-09-24
- Tác giả: người dùng / Codex
- Nhánh: codex/fresh-trip-catalog-release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: data
- Thay thế: `history/2026-09-24-trip-catalog-fresh-release-mvp-v1.md`, `history/2026-09-24-xoay-vong-id-trip-tren-vm.md` về yêu cầu checkout crawler Trip riêng

## Mục tiêu

Chỉ dùng một nhánh mới của Travel-Recommendation-Product, xuất phát từ `release-mvp-v1`, để cào dữ liệu mới đa nguồn; thêm Trip hotel room JSON, chuẩn hóa đủ sáu biến thể catalog và upsert DB. Máy chạy Ubuntu console, 2 CPU/4 GB RAM, không cần checkout repo crawler tham khảo và không dùng sản phẩm/interim cũ làm input.

## File thay đổi

- `src/data_collection/collectors/trip_live.py` — thêm: tìm ID Trip theo thành phố, lấy metadata bằng HTTP/SSR, bắt JSON phòng/giá theo ngày bằng Chromium/Xvfb, giữ HTML response gốc khi cần fallback và báo cáo coverage.
- `src/data_collection/collectors/trip_hotels.py` — sửa: nhận cả thẻ SSR `span.hotelName` hiện tại để discovery tìm được ID mới.
- `src/data_collection/normalise.py` — sửa: chuẩn hóa giá/tình trạng Trip theo ngày và giữ tất cả phòng Trip theo physicalRoomId, kể cả khi khách sạn gộp với nguồn khác.
- `src/data_collection/fresh_catalog.py` — thêm: điều phối full/daily/auto, kiểm tra sáu biến thể, tạo run tạm và nạp DB sau khi kiểm tra coverage.
- `src/data_collection/fresh_catalog_db.py` — thêm: đối chiếu ID/sameAs và upsert transaction vào `cdp.products`, cập nhật giá/trạng thái, thêm phòng mới, ánh xạ FK combo theo ID canonical, hết bán phòng biến mất sau phản hồi hợp lệ, hết hạn giá Trip cũ.
- `src/data_collection/fresh_catalog_schedule.py` — thêm: xoay vòng ID dựa trên thời điểm thử, chỉ giữ ID/thành phố và timestamp.
- `src/data_collection/run_fresh_catalog_vm.sh` — sửa: entrypoint một repo với Xvfb, DB local/cloud tùy cấu hình.
- `src/data_collection/requirements.txt` — sửa: thêm `curl_cffi` cho HTTP metadata.
- `src/data_collection/tests/test_trip_hotels.py` — sửa: kiểm tra thẻ SSR có tên dạng span.
- `src/data_collection/tests/test_fresh_trip.py` — thêm: kiểm tra JSON giá, ba mốc ngày, phòng mới, coverage lỗi, chuẩn hóa thành `products.jsonl`, gộp DB và hết hạn giá.
- `src/data_collection/README.md` — sửa: hướng dẫn cài/chạy một repo trên Ubuntu console và lịch full/daily.
- `history/2026-09-24-trip-catalog-single-repo.md` — thêm: entry này.

## Quyết định

- Bám FR-CAT-01/02/03 và FR-CAT-04: 13 cột sản phẩm, phòng gắn khách sạn, giá và trạng thái theo ngày đã hỏi, parse thành phần combo bằng code `seed` sẵn có.
- Lượt full đầu và mỗi 7 ngày cào lại các nguồn Travel; lần đầu tìm tối đa 10 ID Trip/thành phố, mỗi tuần thêm tối đa 3 ID/thành phố trong 7 thành phố có cityId thuộc `@deep`; các ngày còn lại xoay tối đa 60 ID Trip/ngày. Giá Trip hỏi ở 14/30/60 ngày, không suy ra các ngày chưa hỏi.
- Chỉ nạp Trip hotel hoàn tất mọi mốc bằng giá hoặc sold-out JSON rõ ràng. Response lỗi không được coi là hết phòng. Full marker ghi sau khi DB thành công; raw và catalog của lượt chạy xóa mặc định.
- Không sửa schema/contract và không sửa các nhánh có sẵn. Nhánh này chưa được push.

## Kiểm tra

- `python -m unittest discover -s tests -p 'test_fresh_trip.py'`: 6 pass trong `vsf2`.
- `python -m unittest discover -s tests -p 'test_trip_hotels.py'`: 13 pass trong `vsf2`.
- `python -m unittest discover -s tests -p 'test_quality.py'`: 20 pass trong `vsf2`.
- `bash -n run_fresh_catalog_vm.sh run_daily_docker.sh cron_hotels_daily.sh`: pass.
- `python -m compileall -q fresh_catalog.py fresh_catalog_db.py fresh_catalog_schedule.py collectors/trip_live.py normalise.py`: pass.
- `PYTHON_BIN=.../vsf2/bin/python run_fresh_catalog_vm.sh status`: in đúng `Next run: full; known Trip IDs: 0; daily batch: 60; initial/city: 10; new/city: 3`.
- Smoke test live Trip qua Xvfb: một khách sạn Nha Trang có JSON giá tại cả 3 ngày 14/30/60, tương ứng 21/24/23 offers; chuẩn hóa thành 7 sản phẩm (1 property, 6 rooms có giá) và `prepare_rows` cho 6 phòng mới, đúng 13 trường.
- Smoke test discovery live: tìm 12 ID tại Nha Trang và chọn 1 ID mới thành công.

## Còn lại / rủi ro

- Đã cào Trip live trên máy hiện tại nhưng chưa chạy full đa nguồn hoặc upsert PostgreSQL trên Google Cloud VM thật; các nguồn có thể chặn hoặc đổi JSON/HTML. Cần chạy `--full` trên VM với DB đã migrate, xem log trước khi gắn cron.
- Càng nhiều ID, chu kỳ xoay với 60 ID/ngày sẽ dài; tăng ngân sách/ngày hoặc hạ tốc độ mở rộng ID nếu vượt 7 ngày.
