# Mở lịch hạng phòng đủ 30 ngày, sửa khoá trình duyệt của job cào, kiểm lại DB VM

- Ngày: 2026-10-02
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: dang dở
- Phạm vi: data, docs

## Mục tiêu

Người dùng yêu cầu kiểm tra lại toàn bộ phần việc trong `2026-10-02-toi-uu-crawler-vm-va-bo-sung-phong.md` (cùng ngày, chưa commit). Người dùng cũng muốn mọi ngày trong lịch phòng đều còn trống, vì FE sẽ đọc `attributes.availability` và tự giới hạn 30 ngày. Phục vụ FR-CAT-03.

## File thay đổi

- `src/data_collection/seed/catalog_meta.py` — sửa: `room_calendar` trả `"1" × 30`; bỏ `room_closed_target` và lịch mô phỏng kín 25–40%.
- `src/data_collection/seed/config.py` — sửa: bỏ `ROOM_CLOSED_*`, `ROOM_VINPEARL_MULT`, `ROOM_WEEKEND_*`; ghi số đo Recall mới cạnh `MULTI_TICKET_RATE`.
- `src/data_collection/seed/load_products.py` — sửa: hạng phòng lấy nguyên cửa sổ `[as_of, as_of + 29]`, không cắt theo `availableFrom/To` của nguồn; docstring.
- `src/data_collection/fresh_catalog_db.py` — sửa: `apply_window` áp cùng quy tắc cửa sổ cho hạng phòng (job cào hằng ngày).
- `src/data_collection/seed/seed_histories.py` — sửa: chuyến sắp tới của P1 không lọc phòng theo ngày nguồn nữa; bỏ biến và import thừa.
- `src/data_collection/fresh_catalog.py` — sửa: thay khoá bọc cả khối bằng `browser_slot()`. Khoá chỉ giữ trong lúc chạy, không giữ khi chờ retry. Hạn giờ của bước tính từ lúc lấy được khoá. Thêm `find_hotels` (bước tìm ID khách sạn Trip, có mở Chromium nhưng không có `.step`). Bỏ hai tên bước không tồn tại.
- `src/data_collection/tests/test_seed_load_products.py` — sửa: thay test kín 25–40% bằng test phòng mở đủ cửa sổ dù ngày nguồn hẹp hoặc đã qua.
- `src/data_collection/tests/test_fresh_catalog_job.py` — thêm: test `apply_window` cho hạng phòng có ngày nguồn hẹp.
- `src/data_collection/README.md` — sửa: số lượt giữ mặc định 7 → 2, nêu thêm `RUNS_KEEP`.
- `docs/spec/MOCK_DATA_SPEC.md`, `docs/spec/DATABASE_SCHEMA.md`, `docs/spec/PRODUCT_SCHEMA.md`, `AGENTS.md` §6.2 — sửa: quy tắc lịch và cửa sổ của hạng phòng; số đo seed/Recall mới.

## Quyết định

- Người dùng chọn mở hai nhóm. (a) Lịch mô phỏng kín 25–40%: mở đủ 30 đêm. (b) Phòng chỉ có giá cho 1–2 ngày (752 phòng booking.com trên VM chỉ mở 23–24/10): cửa sổ thành nguyên 30 ngày, giá giữ làm giá tham khảo. Giữ (c): ngày nguồn thật đã hỏi và báo hết phòng vẫn là `0`. Việc này do `real_room_calendar` và `_with_observed` làm, nên không bịa trạng thái trái với nguồn (NFR-REL-01).
- Không lệch PRD. `requirements.md` FR-CAT-03 và `data-model.md` §3.1 chỉ quy định có lịch 1/0. Tỷ lệ kín và việc cắt theo ngày nguồn chỉ nằm ở spec và AGENTS §6.2, nên các file đó được sửa trong cùng thay đổi. Chuỗi ví dụ có số 0 trong `data-model.md` chỉ để minh hoạ, giữ nguyên.
- Giữ `MULTI_TICKET_RATE = 0.35`: quét lại cho thấy mức này không làm baseline vượt trần (số đo ở mục Kiểm tra).

## Kiểm tra

- `pytest src/data_collection/tests` (vsf2, `PYTHONPATH=src`): 462 passed, 18 skipped, 4 failed. Ba fail (`test_live_monitor` preview, `test_normalise_steps`, `test_normalise_stream`) cũng fail trên HEAD `d7ea30a`, chạy trong worktree sạch, nên là lỗi có sẵn. `test_timeouts_recrawl::test_deadline_stops_the_source_and_its_children` fail một lần khi chạy cả suite nhưng PASS khi chạy riêng (19/19), nên coi là flaky do tải máy.
- Recall@20 baseline, snapshot 11.387 dòng, `as_of 2026-10-02`, lịch phòng mới. Seed 42: 0,599 ở cả hai mức. Seed 1–61: 0.35 cho trung bình 0,515, cao nhất 0,599, 0/61 vượt 0,60; 0.10 cho trung bình 0,514, cao nhất 0,607, 1/61 vượt. Report seed 42: 7.324 event, purchase 3.288 (attraction 597, combo 246).
- DB VM (tunnel 15432, `vota_db_dev`, chỉ đọc):
  - Khách sạn có phòng đặt được: **2.137/2.447 (87,3%)**. Entry trước ghi 2.142, chênh 5, có thể do job hằng ngày đã chạy sau đó.
  - Search unit: 3.393.
  - Lịch phòng hiện tại (code cũ): khoảng 9.300 phòng kín 6–13 đêm; 752 phòng booking.com kín 28–30 đêm vì cửa sổ nguồn chỉ là 23–24/10.
- Chạy thử `apply_window` mới trên dữ liệu VM, trong bộ nhớ và transaction chỉ đọc, không ghi: 8.857 dòng sẽ đổi. Trong 8.620 phòng đang bán: 8.579 mở đủ 30 đêm, 41 phòng có 1–3 đêm nguồn thật báo hết phòng.
- `db/verify.sql` trên DB VM, chạy chỉ đọc: 19 dòng PASS (gồm `products >= 11387`). **3 dòng lỗi** do VM chưa áp migration 0005/0006 (`app.schema_migrations` chỉ có 0001–0004): thiếu `booking_items.metadata`, `app.booking_travelers`, cột `adults` của giỏ. Vì vậy câu "verify.sql 100% PASS" ở entry trước là chưa đúng.

## Sửa DB VM (người dùng yêu cầu "sửa DB trước")

- Lỗi: `apply_window` tắt (`available = false`) các dòng có ngày nguồn nằm ngoài cửa sổ, nhưng khi cửa sổ cuộn tới ngày đó thì không bao giờ bật lại. Ví dụ: "Khách sạn Dương Đông" (Phú Quốc, Agoda) có giá cho 31/10, bị tắt ngày 01/10 và vẫn tắt ngày 02/10.
- Đã ghi lên DB VM (tunnel 15432, `vota_db_dev`), trong một transaction có khoá `pg_advisory_xact_lock(7791024)` (cùng khoá với `maintain_catalog`). Bật lại 144 dòng: 71 property, 73 room. Điều kiện chọn: có giá, có cửa sổ giao với `[02/10, 31/10]`, không bị gộp trùng (`mergedInto`), không có `priceFreshness`. Sau đó chạy `apply_window` mới cho đúng các dòng này, nên 73 phòng có lịch 30 ngày mở đủ.
- Bản sao lưu 144 dòng trước khi sửa: `src/data_collection/data/vm-repair-20261002/backup-stuck-rows-20261002.jsonl` (thư mục ignored).
- Sau khi sửa: 0 dòng còn kẹt. `window = 30 days` PASS, `room calendars 30 chars` PASS. Khách sạn có phòng đặt được: 2.137 → 2.142/2.447.
- Phía FE (chỉ đọc code, không sửa): trang chi tiết `ProductDetailView.tsx` chỉ hiển thị số sao, địa chỉ, tên, 1 ảnh, mô tả và danh sách hạng phòng. Không hiển thị `amenities`, bộ ảnh `images`, điểm review, giờ nhận/trả phòng hay bản đồ. Khi `available = false`, ảnh bị phủ lớp "tạm hết chỗ". Khách sạn Dương Đông không có hạng phòng nào trên DB nên mục chọn phòng trống.

- Rút gọn `description` của `b1e7651b-bf8d-5123-aac6-0a755cc0c049` (Khách sạn Dương Đông) từ 16.279 xuống 779 ký tự. Bản mới chỉ gồm các câu và dữ kiện có trong mô tả gốc của Agoda (cắt bớt, ghép lại), không thêm thông tin. Bản gốc: `src/data_collection/data/vm-repair-20261002/description-backup.jsonl`.
- Áp lịch phòng mới cho toàn bộ hạng phòng trên DB VM: chạy `apply_window` (code mới) trên cả catalog nhưng chỉ ghi 8.630 dòng `hotel_room`; 154 dòng thay đổi không phải phòng không ghi. Kết quả: trong các phòng đang bán, 8.652 mở đủ 30 đêm, 41 phòng có ngày nguồn thật báo hết phòng, 0 phòng có cửa sổ hẹp hơn 30 ngày. Sao lưu trạng thái cũ (available, from, to, availability): `src/data_collection/data/vm-repair-20261002/backup-room-window-20261002.jsonl`.
- Người dùng sau đó yêu cầu thêm: "giờ các phòng đều phải avai", FE chỉ cho đặt trong 30 ngày, áp dụng trước mắt. Đã mở nốt các ngày nguồn thật báo hết phòng của 41 hạng phòng, tức nhóm (c) trước đó được giữ. Kết quả: 8.693/8.693 phòng đang bán có lịch `"1" × 30`. Sao lưu lịch cũ: `src/data_collection/data/vm-repair-20261002/backup-room-soldout-days-20261002.jsonl`. Đây là quyết định riêng cho DB demo. Code vẫn giữ quy tắc (c), nên sau khi deploy, job sẽ ghi lại các ngày hết phòng thật. 17 hạng phòng không có giá (`available = false`, `unit_price` null) vẫn để nguyên vì không có giá để đặt.
- `db/verify.sql` sau khi sửa: 20 dòng PASS, vẫn 3 dòng lỗi do thiếu migration 0005/0006.

## Rà parser combo (người dùng yêu cầu "rà lại")

Phục vụ FR-CAT-04.

File sửa:
- `src/data_collection/seed/parse_combos.py`
- `src/data_collection/fresh_catalog_db.py` (thêm `bring_manual_combo_mapping`)
- `Dockerfile.fresh-catalog.dockerignore` (đưa `snapshots/2026-09-30/combo_items_manual.jsonl` vào image)
- `src/data_collection/tests/test_seed_parse_combos.py` (3 test mới)
- `src/data_collection/tests/test_fresh_catalog_job.py` (2 test mới)
- `docs/spec/MOCK_DATA_SPEC.md` §3

Lỗi tìm thấy trên DB VM (172 combo, 420 dòng `combo_items`):
1. 39 combo bay + ở của Trip bị tách theo tên.
   - Nhãn vé máy bay mất điểm đến: "Vé máy bay khứ hồi TP. Hồ Chí Minh".
   - Tên khách sạn vỡ đôi ở "&" hoặc ",": "Happy Day Riverside Hotel | Spa Đà Nẵng".
   - Phòng ghi tiếng Anh bị nhận là `other`.
   - "Phòng nhìn ra sân golf" bị nhận là `golf`.
   - Không gắn được tuyến bay nào.
2. Combo chỉ nêu địa điểm ("Combo Phá Đảo 04 Khu", "Combo Công viên nước + Túi tote") mất vé vào cửa.
3. "01 người" bị tính là một thành phần.
4. **Trên VM không còn dòng `source = manual` nào.** Job hằng ngày chạy `parse_combos` trong thư mục lượt cào, mà thư mục này không có file mapping duyệt tay; image Docker cũng loại thư mục snapshot. Kết quả: mỗi lần nạp DB đều xoá 64 mapping đã duyệt.

Cách sửa:
- Combo `trip_real_flight_hotel` đọc thẳng từ `attributes` và `url`.
- Ngưỡng khớp tên khách sạn của combo Trip là 0,7. Ở 0,4–0,67 vẫn còn cặp sai, ví dụ "Hạ Na Hotel Đà Lạt" ~ "Hasa Đà Lạt Hotel" (0,67).
- Hạng phòng không khớp thì gán về property với `confidence = 0.6`, đúng spec §3. Không tự chọn phòng rẻ nhất.
- Mảnh chỉ nêu venue thành vé vào cửa của venue.
- Bỏ các mảnh dạng "N người/khách". "TẶNG 02 buổi" vẫn giữ: đó là buổi tặng thật, test cũ khẳng định điều này.
- Job nạp DB ghép mapping duyệt tay.

Kiểm tra:
- `pytest tests/test_seed_parse_combos.py tests/test_trip_combos.py tests/test_seed_load_products.py tests/test_fresh_catalog_job.py`: 70 passed.
- Snapshot 2026-09-30 (133 combo):
  - Map được: 93/188 (49%) → 138/199 (69%).
  - Hàng đợi soát tay: 67 → 47 dòng.
  - Không combo nào có mapping duyệt tay bị đổi kết quả.
- Catalog VM (172 combo, xuất chỉ đọc, chưa ghi DB):
  - 420 dòng: 278 `description_parse`, 78 `api`, 64 `manual`. Map được 183/247 (74%).
  - Kiểm tra trước khi ghi: không lỗi FK, không trùng PK.
  - File ở `src/data_collection/data/vm-repair-20261002/combos/`, kèm bản sao lưu `combo_items` hiện tại của VM.
- **Chưa ghi `catalog.combo_items` lên VM:** lệnh ghi bị chặn (ghi vào tài nguyên dùng chung), chờ người dùng cho phép.

## Bổ sung khoá trình duyệt

Khi đọc collector để làm slide pipeline, thấy `vinpearl` (vé/tour qua trang có Cloudflare, dùng `BrowserSession`) và `trip-flights` (báo giá thương gia, dùng Playwright) cũng mở Chromium. Đã thêm 2 bước này vào `BROWSER_STEPS` trong `fresh_catalog.py`.

Kiểm tra: `pytest tests/test_pipeline_graph.py tests/test_timeouts_recrawl.py tests/test_fresh_catalog_job.py` cho 63 passed.

## Còn lại / rủi ro

- **Job cào trên VM vẫn chạy code cũ.** Lượt sau, `maintain_catalog` sẽ ghi lại lịch kín 25–40% và cắt cửa sổ phòng theo ngày nguồn. Cần deploy code mới trước lượt cron kế tiếp.
- Mô tả Agoda của các khách sạn khác cũng có thể dài tương tự (văn bản SEO nhiều mục dính liền nhau). Mới sửa tay một khách sạn; chưa có quy tắc rút gọn chung trong normaliser.

- Lỗi không bật lại trong `apply_window` chưa sửa trong code, chờ người dùng đồng ý. Sẽ tái diễn với các dòng có ngày nguồn nằm ngoài cửa sổ ở các lượt sau.
- Lịch mở đủ 30 ngày mới chỉ áp cho 73 phòng vừa bật lại. Các phòng khác trên DB VM vẫn theo lịch cũ. Muốn FE thấy lịch mở đủ thì phải triển khai code mới lên job cào trên VM, rồi để `maintain_catalog` chạy, hoặc chạy `apply_window` một lần. Chỉ sửa DB mà không triển khai thì `maintain_catalog` của image cũ sẽ ghi lại lịch kín ở lượt sau. Cả hai việc chờ người dùng đồng ý.
- VM thiếu migration 0005, 0006: chờ người dùng đồng ý chạy `python db/migrations/run.py --database-url <dsn staging>`.
- Seed của P1 vẫn dùng `room_calendar` (lịch mô phỏng), không dùng lịch thật Vinpearl. Lỗi lệch này có sẵn từ trước, không sửa trong task này.
- Còn từ entry trước: đổi `COHERE_API_KEY` rồi embed 320 search unit; chạy `./run_daily_docker.sh cleanup` trên VM; ghi lại lệnh đã dùng để cào và upsert phòng Agoda.
