# Ổn định lượt cào full: gộp mvp2, mang bản sửa Trip, setting hạn giá Trip

- Ngày: 2026-10-07
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở (code chưa commit/deploy; khôi phục 122 dòng Trip chờ người dùng chạy sau deploy)
- Phạm vi: data

## Mục tiêu

Lượt `full` trên VM `vota-backend-crawler-recsys` thất bại liên tục từ 01/10 nên giá cũ dần (Booking quan sát 19/09) và
quy tắc hết hạn giá Trip 7 ngày đã tắt 122 dòng khách sạn Trip. Người dùng muốn tạm tắt quy tắc này và ổn định lượt cào
trước. Phục vụ FR-CAT-01/02/03, NFR-REL-01. Không lệch PRD (quy tắc 7 ngày không nằm trong PRD).

## Chẩn đoán (đọc qua monitor, chỉ đọc)

- Lượt `full-20261006T190010Z-23`: từ 02:14 nhiều việc nặng chạy song song (Vinpearl + Trip attractions trình duyệt, preview,
  nạp DB, index nạp e5/torch) trên VM e2-medium chung backend; bước 0,3 s kéo lên 92–202 s, log trễ, im từ 02:38; supervisor
  (poll 0,5 s) đáng lẽ dừng ở 02:44 nhưng 05:48 mới dừng → cả máy bị treo, khả năng cao cạn RAM (chưa xác nhận OOM vì IAP
  4033 không vào được VM).
- `trip-flights` exit 2: vé thường 34/34 xong, nhưng tìm thương gia/khứ hồi bị Trip từ chối 8/8 → `stopped: failures`.
- DB staging: 144 dòng giá Trip, 122 đã `priceFreshness = stale` (làm mới lần cuối 29/09), 22 còn lại (30/09) sẽ tắt ở
  bảo trì 02:00 08/10 nếu giữ 7 ngày.

## File thay đổi

- merge `origin/release-mvp-v2` vào `test/newcrawl` (local, không push): HA/Patroni, khoá DB crawler, Ops Agent.
- `src/data_collection/collectors/trip_hotels.py`, `collectors/trip_live.py`, `fresh_catalog.py`,
  `tests/test_timeouts_recrawl.py`, `tests/test_trip_hotels.py` — sửa: mang bản sửa Trip SSR/trạng thái giá chưa commit từ
  nhánh `bench_search_recomSys` (`history/2026-10-06-sua-trip-ssr-va-trang-thai-gia.md` ở nhánh đó); xung đột `trip_live.py`
  giữ `log.say` (log JSON của mvp2) + logic sửa.
- `src/data_collection/fresh_settings.py` — thêm setting `tripHotels.priceMaxAgeDays` (mặc định 7, `0` = không tắt).
- `src/data_collection/fresh_catalog_db.py` — sửa: `prepare_rows` nhận `trip_max_age_days = 0` (bỏ qua hết hạn);
  `maintain_catalog`, `load_into_db` nhận `trip_max_age_days`.
- `src/data_collection/fresh_catalog.py` — sửa: truyền setting vào bảo trì, bước `db` và nạp theo phần (`functools.partial`).
- `src/data_collection/tests/test_fresh_trip.py` — thêm test setting (0 tắt, ngưỡng, âm báo lỗi, mặc định 7).
- `src/data_collection/tests/test_timeouts_recrawl.py`, `tests/test_normalise_stream.py` — sửa hàm giả nhận kwargs mới.
- `src/data_collection/README.md` — sửa: mô tả quy tắc theo setting.
- `src/data_collection/fresh_catalog_db.py` — sửa (bug 1, gộp "treo"): `resolve_ref_conflicts` chỉ bỏ qua dòng
  `mergedInto` khi dòng giữ còn tồn tại và nhận ref đó; dòng đang hiện thắng dòng đã gộp khi tranh ref; `prepare_rows`
  bỏ `mergedInto` trỏ tới dòng không còn. Trước đây: `ValueError: ID conflict ... sourceRef changed` làm hỏng cả bước DB.
- `src/data_collection/collectors/common.py` — thêm `BrowserSession.restart()` (đóng/mở lại Chromium, cùng profile).
- `src/data_collection/collectors/booking_base.py` — sửa (bug 2): `fresh_page()` mở tab mới trước rồi đóng tab cũ; Chromium
  từ chối tab thì mở lại trình duyệt một lần, vẫn lỗi thì dừng êm (tiến độ giữ), không ném lỗi làm đỏ cả bước.
- `src/data_collection/collectors/booking_base.py` — sửa (bug 4, có từ trước): vòng thử lại cuối lượt dùng lại `first_page`
  đã đóng khi thay tab → URL thử lại lỗi "Target page ... has been closed"; nay mỗi worker giữ tab hiện tại qua các vòng.
- `src/data_collection/collectors/trip_live.py` — sửa (bug 3): `price_packet` coi `isRoomListSoldOut` + mọi hạng
  `isFullRoom` là `sold_out` (trước đây `missing` → bước giá Trip `partial`).
- `src/data_collection/collectors/trip_live.py` — sửa (bug 5): `capture_prices` thử lại một vòng các (khách sạn, ngày)
  `missing` (HTTP 200 nhưng 0 gói giá, lỗi thoáng qua); lần thử lại hỏng không xoá kết quả cũ.
- `src/data_collection/tests/test_trip_price_retry.py` — thêm: 2 test trình duyệt giả (đỏ khi bỏ vòng thử lại, xanh khi có).
- `src/data_collection/fresh_catalog.py` — sửa (bug 6): `resume_run` ghi lại `incompleteSources` theo kết quả mới (gồm
  `unpricedHotelDates` của coverage mới); trước đây cào lại một nguồn thành công vẫn kết thúc `partial` vì dấu của lần đầu.
- `src/data_collection/tests/test_pipeline_hardening.py` — sửa test resume (thêm `save`), thêm test bug 6.
- `src/data_collection/tests/test_fresh_catalog_job.py` — thêm 2 test gộp treo / dòng hiện thắng dòng gộp.
- `src/data_collection/tests/test_booking_tab_recycle.py` — thêm: 3 test Chromium từ chối tab (đỏ với code cũ, xanh mới).
- Ngoài git (thư mục ignored, worktree chính): `src/data_collection/data/vm-repair-20261007/restore_stale_trip.py` — khôi
  phục dòng `stale` từ `vm-repair-20261006/backup-before-maintain-2026-10-06.jsonl` (122/122 ID có trong bản sao lưu, 115 có
  giá và đang bán); mặc định chạy thử + rollback, `--apply` sao lưu trước rồi ghi.

RecSys (người dùng muốn gộp vào cùng nhánh `test/newcrawl`, tự mở PR vào `release-mvp-v2`) — chép nguyên từ nhánh
`bench_search_recomSys` (chưa commit ở đó), xem `history/2026-10-07-recsys-trong-so-0-7-0-15.md`:
- `src/backend/app/domain/recommendation/profile.py` — `W_SHORT, W_POP, W_LONG` 0,6/0,25/0,15 → 0,7/0,15/0,15.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.7 — công thức điểm 3 thành phần theo trọng số mới.
- `docs/prd/update/2026-10-06-recsys-trong-so-ngan-han-pho-bien.md` → `docs/prd/update-archive/` (`đã áp dụng`, chốt
  bởi người dùng 2026-10-07; PRD không đổi câu chữ vì FR-REC-04 không ghi số).
- `history/2026-10-07-recsys-trong-so-0-7-0-15.md` — chép entry gốc.

Các file `docs/spec/MOCK_DATA_SPEC.md`, `monitor.py`, `monitor_ui/index.html`, `pipeline_graph.py`, `seed/parse_combos.py`,
`tests/test_fresh_catalog_job.py`, `tests/test_monitor_storage.py`, `tests/test_simulated_business.py`,
`tests/test_combo_items_sync_db.py` là việc dở của `history/2026-10-07-parse-lai-combo-tu-db.md`, không thuộc entry này.

## Quyết định

- Người dùng chọn: setting mặc định 7 (hành vi cũ), chỉnh về 0 trên monitor sau deploy; khôi phục 122 dòng từ bản sao lưu;
  agent đổi setting trên monitor.
- Đã đổi trên monitor VM (người dùng đồng ý, có hiệu lực từ lượt 02:00 08/10): `tripFlights.fareMinutes` 30 → 0,
  `stream.index` true → false, `crawl.parallelSites` 2 → 1. Giá trị lưu từ monitor thắng biến env.
- Người dùng đồng ý tăng `timeout.booking` 60 → 150 trên monitor VM (Booking cần khoảng 70 phút: 24 phút lập kế hoạch +
  251 trang). Người dùng không cần nhanh, cần mọi bước xanh.
- Người dùng đồng ý tăng `runs.keep` 2 → 5 trên monitor VM (giữ log 5 lượt để tra lỗi; mỗi lượt khoảng 25 MB, đĩa trống
  6,5 GB). Kiểm tra monitor 20:52: lượt kế tiếp 02:00 08/10 `full`, các setting trên đúng giá trị, VM chưa có
  `tripHotels.priceMaxAgeDays` (code chưa deploy).
- Người dùng chọn: phần "parse lại combo" (`history/2026-10-07-parse-lai-combo-tu-db.md`) đi cùng PR này; chưa commit/mở PR
  cho tới khi một lượt `full` local sạch bằng toàn bộ code mới xanh hết.
- Người dùng đồng ý tắt `stream.enabled` trên monitor VM (true → false, 08/10 ~00:45): chuẩn hoá/gộp/nạp DB chạy một lần
  sau khi cào xong, không song song với Chromium. Nguồn vẫn cách ly (`--allow-partial-sources`); lượt chết giữa chừng thì
  chưa nạp gì nhưng resume được từ chuẩn hoá/DB.
- Người dùng chọn mở rộng phạm vi cào sau khi deploy code mới (không chạy thử local trước), chấp nhận 8–10 giờ/lượt (< 24 giờ):
  `scope.destinations` @deep → @v1 (38 điểm đến, 20 sân bay, 12 thành phố Trip có cityId), `agoda.hotelsPerDestination`
  20 → 30, `timeout.tripAttractions` 60 → 150, `timeout.booking` 150 → 240, `timeout.agoda` 120 → 240,
  `timeout.processing` 30 → 60, `crawl.maxHours` 16 → 18, `run.maxHours` 18 → 22. Job hiện tại (`fresh_catalog`) chỉ
  làm mới phạm vi cào; phần catalog ngoài phạm vi (snapshot 23/09, nạp tay 06/10) giữ giá cũ. Ước tính ngoại suy từ số đo
  8 điểm đến, chưa đo thật; rủi ro bị chặn tăng theo số request (×4–5).
- Khôi phục chỉ chạy SAU khi image mới đã deploy và `tripHotels.priceMaxAgeDays = 0`, nếu không bảo trì tắt lại ngay.

## Kiểm tra

- `PYTHONPATH=..:. pytest -q tests` trong `src/data_collection`: 527 passed, 27 skipped.
- `restore_stale_trip.py`: `py_compile` OK; chưa chạy với DB (không có quyền ghi staging trong phiên).
- Sau 3 bug: `pytest -q tests` 533 passed, 27 skipped. Test tab Booking chạy với code cũ: 3 failed đúng lỗi thật.
- Agoda riêng local, tham số VM: 20 phút 23 giây, 362 request, 0 chặn/lỗi, 86/160 khách sạn có phòng, RAM 313 MB.
- Lượt `full` local (`./local_crawl.sh`, bộ `vmcheck`: DB `vota_crawl_vmcheck` nạp sẵn 13.920 dòng bản sao lưu 06/10,
  setting như VM trừ `crawl.parallelSites = 4`): bảo trì, Trip vé, Trip điểm tham quan, Vinpearl, Agoda, Trip KS tìm ID,
  chuẩn hoá, kiểm tra, index xanh; Trip KS giá `partial` 74/77 (bug 3); Booking đỏ ở trang 150 "Failed to open a new
  tab" (bug 2; máy local swap 3,3/4 GB lúc đó — nguyên nhân Chromium từ chối tab chưa chứng minh, thử đóng-tab-cuối trên
  Chromium thật không tái hiện); DB đỏ "ID conflict" (bug 1). Kiểm chứng ngoại tuyến: `prepare_rows` trên bản sao lưu +
  1.602 dòng mới không còn xung đột; `price_packet` đọc lại 231 lượt thật: 5 `missing` → `sold_out`, còn lại không đổi.
- Chạy lại bằng code mới (`./local_crawl.sh run resume <lượt> crawl booking`): Booking 102 trang còn lại xanh (564 s),
  chuẩn hoá/kiểm tra/DB (3.535 dòng ghi, refConflicts 0, Fortuna Hanoi hiện lại)/index xanh, `run.end status=ok exit=0`.
  Trip KS giá vẫn `partial` ở lượt này vì đã chạy bằng parser cũ trước khi sửa bug 3. Lần chạy lại chỉ 102 trang < 150
  nên chưa kiểm chứng trực tiếp đường thay tab của bug 2 trên site thật (chỉ test giả lập).
- Booking đủ phạm vi trên site thật (`crawl.py booking-hotels` tham số VM, 1 tab, Xvfb, 19:59–20:19, RAM đủ): exit 0, 260/261
  trang, qua mốc thay tab 150 không lỗi (không cần mở lại trình duyệt); 1 URL thử lại hỏng vì bug 4. Đường Chromium từ
  chối tab chỉ được phủ bằng test giả lập. Sau bug 4: test mới đỏ khi bỏ phần sửa, xanh khi có; `pytest -q tests` 534 passed.
- Lượt `full` local sạch bằng toàn bộ code mới + phần combo (20:59–23:03, 4 site song song, DB sandbox nạp lại từ bản sao
  lưu 06/10, `tripHotels.priceMaxAgeDays = 0`): bảo trì, Trip vé, Trip điểm tham quan, Vinpearl, Agoda, Booking (256/256,
  0 lỗi, qua mốc thay tab 150), Trip KS tìm ID, chuẩn hoá, kiểm tra, DB (3.569 dòng, 0 xung đột), index e5 (81 vector) xanh;
  Trip KS giá `partial` 72/73 do 1 lượt `missing` thoáng qua → bug 5. `run.end status=partial exit=0`.
  Sau bug 5: `pytest -q tests` 536 passed.
- Cào lại khách sạn Trip của lượt sạch bằng code có bug 5 (`resume <lượt> crawl tripHotels`, 23:04–00:31): 219 lượt
  (209 có giá, 10 hết phòng, 2 `missing` thoáng qua) + vòng thử lại 2/2 có giá → `trip-hotels.prices` ok, 73/73,
  `unpricedHotelDates` 0; chuẩn hoá/kiểm tra/DB (13.692 dòng ghi, 0 xung đột)/index e5 xanh. Lượt vẫn `partial` chỉ vì
  dấu `incompleteSources` của lần đầu (bug 6, sửa sau đó). Sau bug 6: `pytest -q tests` 537 passed; test bug 6 đỏ khi bỏ
  phần sửa.
- RecSys trên nền `release-mvp-v2`: `pytest -q src/backend/tests/unit` 1609 passed, 2 skipped; `tests/architecture` 8 passed.
  Gate RecSys local 07/10 (DB local, vector e5-small npy, split as_of 2026-09-24): LLBO engine R@20 0,852 / NDCG@10 0,507;
  temporal R@5 0,153 / NDCG@10 0,113 — chưa ghi baseline mới (baseline_v1 đo bằng vector Cohere).
- Trước khi push (08/10): merge `origin/release-mvp-v2` mới nhất (fast-forward tới `3cd1459`, đã gồm `7fdd28f` của
  `origin/test/newcrawl`), không xung đột (chỉ trùng file spec Search/RecSys, khác mục). Kiểm tra theo CI: `compileall`
  OK; `validate_contract.py` PASS; `pytest -q src/backend/tests` 1818 passed, 35 skipped; `src/data_collection` 537 passed;
  bộ test của `ha-checks` 75 passed. Push lên `test/newcrawl` không chạy workflow nào (CI/CD chỉ chạy khi push vào
  `main`/`release-*` hoặc PR vào đó).
- DB staging (chỉ đọc qua monitor): 21 dòng gộp, đều có dòng giữ nhận ref → lượt 02:00 08/10 không dính bug 1.

## Còn lại / rủi ro

- Commit + PR `test/newcrawl` → `release-mvp-v2`, deploy image job cào (người dùng làm; không push trong phiên).
- Sau deploy: đặt `tripHotels.priceMaxAgeDays = 0` trên monitor, chạy thử rồi `--apply` script khôi phục.
- Theo dõi lượt 02:00 08/10 với 3 setting mới; xác nhận OOM cần người có quyền IAP vào VM.
- 22 dòng Trip còn lại sẽ bị tắt ở 02:00 08/10 nếu chưa deploy kịp (script khôi phục xử lý được sau đó).
- Bật lại quy tắc (7) khi lượt cào ổn định.
