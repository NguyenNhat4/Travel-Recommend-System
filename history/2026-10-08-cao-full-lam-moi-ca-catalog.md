# Lượt cào full làm mới cả catalog khách sạn và không để một chỗ hỏng làm chết cả lượt

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: fix/full-refresh-stable (worktree `Travel-Recommendation-Product-fullrefresh`, tách từ `origin/release-mvp-v2` 85cea82)
- Trạng thái: hoàn thành (code, test, chạy thử local xong; chưa commit, chưa deploy)
- Phạm vi: data

## Mục tiêu

Người dùng cần mỗi lượt cào full (VM `vota-backend-crawler-recsys`, 02:00) vừa thêm sản phẩm mới vừa làm mới giá **toàn bộ**
catalog, chấp nhận khoảng 10 giờ/lượt, nhưng phải ổn định. Phục vụ FR-CAT-03 (giá và lịch trống đúng), NFR-REL-01. Không
lệch PRD: PRD không quy định phạm vi/lịch cào. Phần "khách sạn mất khỏi nguồn N lượt thì `available = false`" người dùng
hoãn lại (sẽ cần đề xuất PRD riêng).

## Chẩn đoán (chỉ đọc qua monitor VM, API `/api/runs`, `/api/run`, `/api/log`, `/api/dbx/rows`)

- Lượt `full-20261007T190008Z-23` (02:00–03:52 08/10) "Xong" nhưng chỉ ghi 1.880 dòng (809 mới, 1.071 làm mới) trên 17.679
  dòng `cdp.products`. 11.534 dòng (65%) không có `lastSeenAt` = snapshot 23/09 chưa từng được cào lại (Booking 9.368/9.735,
  Agoda 1.254/3.204, Trip 538) mà vẫn `available` và được cuộn cửa sổ 30 ngày mỗi đêm.
- Nguyên nhân: Booking/Agoda chỉ khám phá top N khách sạn mỗi điểm đến `@deep`, không mở lại khách sạn đã có; chuẩn hoá
  (`apply_plan`) còn cắt theo N và phạm vi điểm đến; khách sạn Trip ở lượt full chỉ hỏi giá ID mới tìm (32), xoay vòng mọi
  ID chỉ có ở lượt daily mà lượt daily không bao giờ chạy (`schedule.fullEveryDays = 1`) → 86/136 ID chưa từng có giá.
- Tìm Booking theo điểm đến trên VM trả "0 chỗ nghỉ" ở cả 8 điểm đến (mỗi điểm ~95 s), lượt vẫn "Xong": trang lưu lại có
  tiêu đề "Kết quả tìm kiếm: Nha+Trang", ngày là hôm nay → sau trang thử thách, `+` của `quote_plus` thành chữ thật và mất
  ngày. Từ IP nhà cùng lệnh trả 5/5 khách sạn (không tái hiện được trên máy local).
- Chỉ 1/10 lượt full gần nhất xanh. Kiểu chết cả lượt: supervisor giết cả lượt khi một nguồn quá hạn (02/10 Booking 3.615 s;
  01/10, 06/10 lô stream), một dòng lỗi làm hỏng cả bước DB (03–05/10), container job không giới hạn RAM (30/09 mã -9; VM
  e2-medium chạy chung backend, đêm 08/10 đỉnh ~3,1 GiB tổng container theo biểu đồ người dùng gửi).

## File thay đổi

- `src/data_collection/fresh_catalog_db.py` — sửa: `BOOKING_HOTEL_URL`/`AGODA_HOTEL_URL` nhận slug có `_` (lỗi tìm ra ở lượt
  thử local: Agoda đánh số bản trùng `the-anam_4`, production có ~48 khách sạn như vậy); `refresh_targets_from_rows` (khách sạn tổng quan chưa gộp của Booking/Agoda,
  kể cả dòng nguồn khác đã gộp ref vào `sameAs` qua `bookingUrl`/`agodaUrl`, cũ nhất trước theo `lastSeenAt`);
  `maintain_catalog(refresh_out=…)` lấy danh sách từ chính lần đọc catalog của bước bảo trì; `prepare_rows(quarantine=…)` +
  `_quarantine_plan` tách dòng trùng ID khác ref / trùng `sourceRef` chuẩn thay vì ném lỗi; `load_into_db` tách khách sạn Trip
  chưa đủ mốc ngày thay vì ném lỗi, ghi `db_quarantine.jsonl`, `counts.quarantined`.
- `src/data_collection/fresh_catalog.py` — sửa: ghi `<lượt>/refresh/{booking,agoda}-hotels.jsonl`, `--refresh-list` cho
  `crawl.py`; Trip lượt full hỏi giá ID mới + mọi ID đã biết (`select_batch`, cũ nhất trước, `refresh: True`);
  `refresh_coverage` → `counts.refresh`, `counts.refreshProblems` (dưới `quality.minRefreshPercent`, hoặc tìm Booking 0 ở mọi
  điểm đến) → `incompleteSources`; `run_source(on_start)` ghi pid vào `detail.pid`; resume từ normalise chốt interim ghi dở;
  `main` tự chạy tiếp một lần `resume <lượt> --from normalise` khi lượt full bị dừng cưỡng bức / chết do tín hiệu.
- `src/data_collection/pipeline_runtime.py` — sửa: bước có `detail.pid` quá hạn thì chỉ `terminate_tree(pid)`, lượt chạy tiếp;
  vẫn "running" thêm `SOURCE_KILL_GRACE` (180 s) mới dừng cả lượt; `on_killed(run_id, stopped)`; lấy run id cả khi worker chết
  trước lần đọc đầu.
- `src/data_collection/fresh_settings.py` — thêm `refresh.existing` (true), `quality.minRefreshPercent` (90),
  `run.autoResume` (true); đổi mặc định `timeout.booking` 60 → 600, `timeout.agoda` 60 → 180.
- `src/data_collection/collectors/agoda_api.py` — sửa: `AgodaOptions.refresh`, `add_refresh` (vào phạm vi ngoài `per_city` và
  ngoài kế hoạch, giữ `hotel_id` đã biết, bỏ trang `gone`), cột `refresh` (ALTER cho state cũ), interim `plan.via = refresh`.
- `src/data_collection/collectors/booking_hotels.py` — sửa: URL tìm kiếm mã hoá `%20`; `discover_plan` xếp khách sạn làm mới
  sau kết quả tìm (`REFRESH_PRIORITY` 1000, `plan.via = refresh`); ghi `interim/booking_hotels.search.json`; log tiêu đề trang
  khi tìm 0.
- `src/data_collection/collectors/booking_base.py` — sửa: `CrawlOptions.refresh`; mở lại Chromium sau mỗi
  `pages_before_restart` trang (`restart_browser`).
- `src/data_collection/collectors/common.py` — sửa: `BrowserOptions.pages_before_restart = 100`.
- `src/data_collection/collectors/trip_live.py` — sửa: bản ghi của ID làm mới mang `plan.via = refresh`.
- `src/data_collection/crawl.py` — sửa: `--refresh-list` cho `booking-hotels`, `agoda-api`.
- `src/data_collection/normalise.py` — sửa: `apply_plan` giữ bản ghi `plan.via = refresh` (không cắt theo N, ngoài phạm vi).
- `src/data_collection/pipeline_graph.py` — sửa: `SITE_ORDER` trip → vinpearl → agoda → booking.
- `src/data_collection/alerts.py` — sửa: cảnh báo lỗi `coverage` ("Cào chưa đủ"), cảnh báo dòng DB bị tách.
- `src/data_collection/monitor_ui/index.html` — sửa: nhãn loại cảnh báo `coverage`.
- `src/data_collection/run_daily_docker.sh`, `src/data_collection/fresh-catalog-runner.env.example` — sửa: `--memory` /
  `--memory-swap` `FRESH_MEMORY` (mặc định 2500m, rỗng = không giới hạn) cho container `fresh-run`.
- `src/data_collection/README.md` — sửa: mô tả làm mới cả catalog, độ phủ, supervisor theo nguồn, tự chạy tiếp, tách dòng DB, RAM.
- `src/data_collection/tests/test_full_refresh.py` — thêm (25 test).
- `src/data_collection/tests/test_booking_tab_recycle.py`, `tests/test_fresh_monitor.py` — thêm test mở lại Chromium định kỳ,
  giới hạn RAM container.
- `src/data_collection/tests/test_fresh_catalog_job.py`, `test_live_monitor.py`, `test_pipeline_errors.py`,
  `test_timeouts_recrawl.py`, `test_pipeline_graph.py` — sửa: hàm giả `run_source` nhận `on_start`; thứ tự site và hạn giờ Agoda
  mới.

## Quyết định

- Danh sách làm mới lấy trong bước bảo trì (đã đọc toàn bộ `cdp.products`) thay vì một lần đọc DB riêng: không thêm điểm lỗi,
  bảo trì lỗi thì lượt vẫn cào khách sạn mới tìm (`catalog.refresh.skipped`).
- Cũ nhất trước: lượt hết giờ giữa chừng thì lượt sau làm tiếp phần còn lại, không làm lại cùng đầu danh sách.
- Chạy tuần tự (`crawl.parallelSites = 1`, người dùng đồng ý sau khi xem biểu đồ RAM VM): chỉ một Chromium; Booking cuối vì lâu
  nhất. Ước tính trên VM theo tốc độ đo được: 11–14 giờ (Trip KS 3–3,8 giờ cho ~150–200 ID ở ~69 s/khách sạn, Agoda 1,1–1,5 giờ
  cho 1.191 khách sạn, Booking 5,8–8,7 giờ cho ~2.090 trang ở 4–6 trang/phút). Người dùng chấp nhận dài hơn 10 giờ miễn dưới
  24 giờ → `timeout.booking` 600 phút; giữ `crawl.maxHours` 16, `run.maxHours` 18 (lượt 02:00 xong muộn nhất 20:00).
- Không xử lý khách sạn không còn thấy (người dùng hoãn). Đọc DB không xét `available`: khách sạn đang tắt vẫn được hỏi lại.
- Sửa tìm Booking (`%20`) chưa kiểm chứng được trên IP VM; nếu vẫn 0 thì cảnh báo "Cào chưa đủ" báo ngay ở lượt đầu.

## Kiểm tra

- `PYTHONPATH=<worktree>/src pytest -q -p no:cacheprovider tests` trong `src/data_collection` (conda vsf2): 564 passed,
  27 skipped (gồm `tests/test_full_refresh.py` 25 test, 2 test mở lại Chromium, 1 test giới hạn RAM container).
  `python -m compileall -q src/data_collection` OK; `bash -n run_daily_docker.sh` OK.
- Danh sách làm mới trên bản sao 17.679 dòng production (API monitor, chỉ đọc): Booking 1.823, Agoda 1.191 khách sạn.
- Lượt full local đầu-cuối (`LOCAL_CRAWL_NAME=refresh ./local_crawl.sh run full`, DB `vota_crawl_refresh` nạp 1.378 dòng Nha
  Trang từ bản sao production 07/10 `vota_prodcopy`, cấu hình như VM: tuần tự, 1 tab, Trip 15–20 s, hạn giờ mới; phạm vi
  `Nha Trang`, 19 ID Trip Nha Trang lấy từ VM), 11:03–12:10:
  - bảo trì lập danh sách Booking 105, Agoda 53; Trip KS 2 ID mới + 19 ID đã biết = 21/21 có giá (24 phút); Vinpearl 16 phút;
    Agoda 7 phút; Booking 18 phút (7,5 trang/phút), tìm theo điểm đến 5 khách sạn.
  - `counts.refresh`: Booking 98/105 (93,3%), Agoda 53/53, Trip 19/19; `refreshProblems` rỗng. 7 Booking không làm mới đều
    `gone` (Booking chuyển hướng về trang thành phố = đã gỡ khỏi Booking); 8 lỗi tạm thời qua hết ở vòng thử lại.
  - Bước `validate` chặn nạp DB: "Thiếu nhóm sản phẩm flight" — do phạm vi thử một điểm đến không có tuyến bay nội địa nào
    (`trip_flights`: "1 sân bay trong kế hoạch → 0 tuyến"), không phải lỗi; VM `@deep` có vé. Sửa `sources.tripFlights = false`
    trong `run.json` của lượt thử rồi `run resume <lượt> validate`: validate/db/index ok, `run.end status=ok`; DB 1.539 dòng ghi
    (692 mới, 836 làm mới, 0 tách riêng, 0 xung đột). Sau nạp: Booking 107/114 khách sạn có `lastSeenAt` 08/10 (7 còn lại =
    7 trang `gone`), Trip 17/17, Vinpearl 16/16, Agoda 31/36 → 5 thiếu là slug có `_` (đã sửa regex; cào thật riêng 6 khách sạn
    `_N` của Nha Trang bằng `crawl.py agoda-api --refresh-list`: 6/6 có `hotel_id`, giá, `plan.via = refresh`).
  - Hạng phòng Booking cũ không còn trong trang mới (70 dòng) giữ giá cũ: chỉ Trip có đánh dấu phòng biến mất; ghi ở Còn lại.
- RAM: lượt local trên đo bằng tổng PSS theo tên tiến trình nên lẫn Chrome/app khác trên máy (không dùng). Đo lại đúng cây
  tiến trình (`/proc`, PSS mỗi 15 s) của `crawl.py booking-hotels` cùng danh sách 105 khách sạn + tìm Nha Trang (14:16–14:29):
  117 xong, 7 `gone`, 0 lỗi, 11,4 trang/phút; PSS đỉnh 2.485 MB, thường 1,9–2,3 GB → hạ `pages_before_restart` 300 → 100.
- Chạy `crawl.py booking-hotels` tìm "Nha Trang" từ máy local (thư mục tạm, không DB): 5/5 khách sạn, 10 trang/phút.
- RAM: lượt local trên đo bằng tổng PSS theo tên tiến trình nên lẫn Chrome/app khác trên máy (không dùng). Đo lại đúng cây
  tiến trình (`/proc`, PSS mỗi 15 s) của `crawl.py booking-hotels` cùng danh sách 105 khách sạn + tìm Nha Trang (14:16–14:29):
  117 xong, 7 `gone`, 0 lỗi, 11,4 trang/phút; PSS đỉnh 2.485 MB, thường 1,9–2,3 GB → hạ `pages_before_restart` 300 → 100.
- Chạy `crawl.py booking-hotels` tìm "Nha Trang" từ máy local (thư mục tạm, không DB): 5/5 khách sạn, 10 trang/phút.

## Còn lại / rủi ro

- Khách sạn không còn trên nguồn (Booking `gone` 7/105 ở Nha Trang) và hạng phòng Booking/Agoda biến mất vẫn giữ giá cũ,
  `available` như trước — phần "tắt sau N lượt" người dùng hoãn, cần đề xuất PRD.
- Sửa tìm Booking (`%20`) chỉ kiểm được từ IP nhà; lượt VM đầu tiên sau deploy phải xem `counts.refresh['booking-hotels.search']`.
- Sau deploy: trên monitor VM đặt `timeout.booking` 600, `timeout.agoda` 180 (VM đang lưu 150/120, giá trị lưu thắng mặc
  định), cân nhắc `schedule.time` 21:00–22:00 để xong trước giờ có người dùng; kiểm `FRESH_MEMORY` với RAM thật của VM.
- `FRESH_MEMORY` 2500m sát mức Booking đo được: Chromium có thể bị kernel giết trong cgroup (nguồn lỗi → thử lại, tiếp tục từ
  hàng đợi đã lưu; backend không bị ảnh hưởng). VM e2-medium 4 GB chạy chung backend là giới hạn thật; nâng VM (8 GB) thì
  tăng `FRESH_MEMORY` và mới nên bật cào song song.
- Commit/PR/deploy do người dùng quyết định.
