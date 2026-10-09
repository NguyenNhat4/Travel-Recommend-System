# Áp dụng: job cào dời ngày vé vào cửa sổ; gom code cào 02/10–06/10 vào test/newcrawl

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở (chưa commit, chưa deploy)
- Phạm vi: data, docs

## Mục tiêu

1. Áp dụng đề xuất đã chốt `docs/prd/update-archive/2026-10-06-job-cao-doi-ngay-ve-vao-cua-so.md` (Đăng Khôi chốt 06/10, điều chỉnh: không ghi yêu cầu hiển thị "giá tham khảo"): vé máy bay của job cào luôn đặt được và cuộn theo ngày như hạng phòng. Phục vụ FR-CAT-01, FR-CAT-03.
2. Người dùng chọn đưa toàn bộ sửa job cào về nhánh `test/newcrawl` (nhánh của job, đã merge vào `release-mvp-v2`), vì kiểm tra cho thấy cả `origin/test/newcrawl` và `origin/release-mvp-v2` vẫn ở code 30/09 (`1afeb93`): VM đang chạy code chưa có sửa nào từ 02/10.

## Gom code vào test/newcrawl (worktree `Travel-Recommendation-Product-newcrawl`, gốc là `test/newcrawl` local `c84f88c`)

- `git show d7ea30a -- src/data_collection | git apply -3`: bước agoda-hotels chạy collector `agoda-api` (có hạng phòng + giá thật).
- `git show bb41479 -- <phần data>`: chỉ các file data/doc của hai entry 02/10 (`2026-10-02-toi-uu-crawler-vm-va-bo-sung-phong.md`, `2026-10-02-mo-lich-phong-30-ngay-va-sua-khoa-trinh-duyet.md`), không lấy phần search bench, CDP replica, recsys append (`ac7642a`).
- Sửa ngày 06/10 (ref trùng, `windowClosed`) và hai entry history của nó, chép từ `bench_search_recomSys` (chưa commit ở đó; đã gỡ khỏi nhánh đó sau khi chép).

## File thay đổi (ngoài các file gom ở trên)

- `docs/prd/data-model.md` — sửa §3.1: job cào và seed demo cùng quy tắc dời ngày vé ngày cố định (theo đề xuất đã chốt).
- `docs/prd/update-archive/2026-10-06-job-cao-doi-ngay-ve-vao-cua-so.md` — thêm: đề xuất trạng thái `đã áp dụng` kèm điều chỉnh khi chốt (file chưa từng được git theo dõi nên chuyển bằng `mv`, không phải `git mv`).
- `src/data_collection/fresh_catalog_db.py` — sửa `apply_window`: vé `fixedDepartureDate` dùng `load_products.seed_fixed_flight_date` + `shift_fixed_flight` (dời hai chặng, đổi ngày trong tên/mô tả, giữ `priceValidUntil`); vé máy bay có giá, chưa gộp luôn `available`; bỏ qua `demo:business:*` (sync chép từ vé gốc); so thay đổi gồm cả name/description. `maintain_catalog` ghi thêm `name`/`description` (`COALESCE`), `load_into_db` cập nhật name/description chỉ cho `taxonomy = flight` (loại khác giữ text đã có trong DB, vd. mô tả rút gọn tay 02/10).
- `src/data_collection/seed/load_products.py` — sửa docstring `seed_fixed_flight_date` (job dùng cùng hàm).
- `src/data_collection/pipeline_graph.py` — sửa: nguồn agoda ghi `agoda_api`, `agoda_hotels` (bản trình duyệt cũ) thành file phụ của site. `d7ea30a` đã bỏ hẳn `agoda_hotels` khiến chuẩn hoá theo site bỏ sót file cũ.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa/thêm: test bật lại theo cửa sổ chuyển sang vé tham quan; test vé ngày cố định ngoài cửa sổ được dời (hai chặng, tên/mô tả, giữ `priceValidUntil`), vé trong cửa sổ giữ ngày, vé gộp vẫn tắt, vé mô phỏng không bị đụng.
- `src/data_collection/tests/test_flight_variants.py` — sửa: test quy tắc cũ "job giữ ngày thật, khoá vé hết hạn" thành quy tắc mới.
- `src/data_collection/tests/test_pipeline_graph.py` — sửa kỳ vọng `SITE_INTERIM['agoda'] = ('agoda_api', 'agoda_hotels')`.
- `src/data_collection/tests/test_live_monitor.py` — sửa: test preview theo độ trễ giả lập tắt khoá một Chromium (`BROWSER_STEPS`, thêm 02/10) để thứ tự xong không phụ thuộc khoá; kỳ vọng nguồn agoda là `agoda_api`.
- `docs/spec/MOCK_DATA_SPEC.md` §2.1, `docs/spec/data-collection/schema.md` (`fixedDepartureDate`, `windowClosed`), `src/data_collection/README.md` — sửa theo quy tắc mới.

## Quyết định

- Dùng lại đúng hàm dời ngày của seed, không viết quy tắc mới.
- "Luôn đặt được" áp cho vé máy bay có giá và chưa gộp; vé không giá hoặc đã gộp vẫn tắt.
- 4 test từng ghi là "fail có sẵn" ở entry 02/10 thật ra pass trên `test/newcrawl` gốc: chúng hỏng do `d7ea30a` (đổi file nguồn agoda) và khoá trình duyệt 02/10. Đã sửa ở đây.

## Kiểm tra

- `pytest src/data_collection/tests` trong worktree (vsf2, `PYTHONPATH=src:src/data_collection`): **476 passed, 18 skipped, 0 failed**.
- Trên `test/newcrawl` gốc `c84f88c` (worktree tạm): 3 file test monitor/normalise 75 passed — xác nhận lỗi do commit gom sang, không phải có sẵn.
- Chạy thử code mới trên dữ liệu DB VM (sau khi gộp 21 khách sạn), trong bộ nhớ, không ghi, as_of 06/10: `refConflicts = 0`; 12.642 dòng đổi cửa sổ; 540 vé bật lại; 244 vé được dời ngày (vd. "Khứ hồi VJ580 / VJ581: CXR - DAD (2026-11-11 – 2026-11-18)" → "(2026-11-01 – 2026-11-08)"); vé máy bay thật đang bán 1.321/1.321.

## Còn lại / rủi ro

- Chưa commit; `test/newcrawl` local còn commit merge `c84f88c` chưa push. Sau khi commit cần merge `test/newcrawl` → `release-mvp-v2` để CI deploy image mới.
- Trước khi deploy, lượt cron tối 06/10 vẫn chạy image 30/09: nếu bước nạp qua được, nó ghi lại lịch phòng kín 25–40%. Deploy hoặc tạm dừng cron trước 19:00 UTC.
- Nhánh `load_products.convert(real_flight_dates=True)` (`daily.py` cũ, `release_flights.py`) vẫn giữ ngày thật; job mới không dùng nhánh này, lượt `maintain_catalog` sau đó sẽ dời ngày.
- `test/newcrawl` local chưa có các commit mới nhất của `origin/release-mvp-v2`; có thể cần merge khi mở PR.
