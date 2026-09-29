# P4: hạn giờ cho từng nguồn / cả phần cào, và cào lại một nguồn

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

P4 của `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` (người yêu cầu: "làm P4 đi"). Theo mục đã chốt 3–5:

- **P4a:** mỗi bước cào có hạn giờ; cả phần cào có `crawl.maxHours`. Trước đây `fresh_catalog.py` không có hạn giờ nào,
  nên một nguồn treo giữ lượt và khoá mãi.
- **P4b:** nguồn bị chặn / lỗi / quá giờ cào lại được riêng, không cào lại cả lượt.
  - Chỉ bằng tay (lệnh và nút trên monitor).
  - Lưu `trip_targets.run.json` để cào lại được giá khách sạn Trip.

Phục vụ FR-CAT-01..04.

## File thay đổi

- `src/data_collection/pipeline_errors.py` — sửa:
  - loại lỗi `timeout`, lớp `StepTimeout` (trạng thái bước `timeout`), `EXIT_TIMEOUT = 124`;
  - `classify_exit(124)` → timeout;
  - chiến thuật như bị chặn: bỏ qua, không thử lại.
- `src/data_collection/fresh_run_log.py` — sửa: `terminate_tree(pid)` dừng một tiến trình và mọi tiến trình con của nó
  (lấy danh sách con trước khi gửi tín hiệu). `terminate_children` dùng chung `_terminate`.
- `src/data_collection/pipeline_graph.py` — sửa:
  - `Source.timeouts` (khoá hạn giờ của từng bước), `STEP_TIMEOUT`, `SOURCE_BY_KEY`;
  - điểm chạy lại `crawl` (`RECRAWL`): `resume_plan('crawl')` = crawl → normalise → validate → db → index;
  - `resume_options(<bước cào>)` = `('crawl',)`.
- `src/data_collection/fresh_settings.py` — sửa: thêm `crawl.maxHours` (16 giờ, env `CRAWL_MAX_HOURS`) và
  `timeout.vinpearl` 90, `timeout.tripFlights` / `tripAttractions` / `booking` / `agoda` 60, `timeout.tripHotelsDiscover` 60,
  `timeout.tripHotelsPrices` 480 (phút; 0 = không giới hạn), nhóm "Thử lại và kiểm chất lượng".
- `src/data_collection/fresh_catalog.py` — sửa:
  - `run_source(..., deadline)`: luồng canh; quá hạn thì `terminate_tree` (crawl.py + Chromium) và trả 124;
  - `deadline_after`, `step_deadline` (hạn giờ riêng của bước hoặc hạn cả phần cào, lấy cái sớm hơn);
  - `seal_interim`: bỏ dòng ghi dở ở cuối file interim; chỉ có `<nguồn>.jsonl.tmp` (Vinpearl) thì đổi tên;
  - `run_cancellable(..., deadline)` ném `StepTimeout` và huỷ việc đang chạy;
  - `crawl_sites(..., deadline)`:
    - bước quá giờ xử lý như bị chặn: niêm phong interim, không thử lại, chuẩn hoá phần đã cào, nguồn khác chạy tiếp;
    - quá hạn cả phần cào: bỏ bước và nhóm chưa bắt đầu, ghi mã 124;
    - bước trong tiến trình quá giờ thì bỏ bước phụ thuộc;
  - tách `crawl_trip_prices` (dùng cho lượt và cho cào lại); `save_run_targets` → `trip_targets.run.json` (lượt full sau
    tìm ID, lượt daily sau chọn lô);
  - hỏi giá khách sạn Trip quá giờ: lượt không có khách sạn Trip mới, không còn lỗi "Không có khách sạn Trip đủ JSON giá";
  - `recrawl_source` + `resume_run(..., source)` + `run_job(..., source)` + CLI `--from crawl --source <nguồn>`;
    `run.json` ghi `resumes[].from = "crawl:<nguồn>"`; cào lại bị chặn / quá giờ lần nữa → mã 3.
- `src/data_collection/alerts.py` — sửa: cảnh báo `warning` loại `timeout` cho bước quá giờ.
- `src/data_collection/monitor.py` — sửa:
  - `SEVERITY['timeout']` bằng `blocked`;
  - nút cào lại chỉ trên ô cào `blocked` / `timeout` / `error`, đúng chế độ lượt; khách sạn Trip cần `trip_targets.run.json`;
  - `resume(run, from, source)`: kiểm nguồn, thêm `--source`, bọc `xvfb-run` khi không có DISPLAY (như `start()`);
  - `/api/resume` nhận `source`.
- `src/data_collection/monitor_ui/index.html` — sửa:
  - nhãn và màu "Quá giờ", loại cảnh báo `timeout`;
  - nút "Cào lại nguồn này" gửi `source` = làn của ô; câu giải thích và hộp xác nhận riêng.
- `src/data_collection/local_crawl.sh` — sửa: `run resume <mã lượt> crawl <nguồn>` (có Xvfb).
- `src/data_collection/README.md` — sửa: mục "Hạn giờ và cào lại một nguồn" và lệnh mẫu.
- `src/data_collection/tests/test_timeouts_recrawl.py` — thêm, 19 test:
  - tiến trình thật: quá hạn thì dừng cả tiến trình cháu; xong trước hạn giữ mã thoát;
  - `step_deadline`, `run_cancellable`, loại lỗi;
  - `seal_interim` (file tạm, file nối thêm, file đủ dòng);
  - `crawl_sites`:
    - nguồn quá giờ được niêm phong và chuẩn hoá, không thử lại, nguồn khác chạy tiếp;
    - hạn riêng bị giới hạn bởi hạn cả phần cào;
    - hết hạn cả phần cào thì bỏ bước chưa chạy;
    - bước trong tiến trình quá giờ thì bỏ bước phụ thuộc;
  - `run_job('full')`:
    - nguồn quá giờ → lượt mã 3 vẫn nạp, có cảnh báo, có `trip_targets.run.json`;
    - hỏi giá Trip quá giờ không làm hỏng lượt;
  - cào lại:
    - chỉ nguồn đó rồi mọi bước sau;
    - bị chặn lại → mã 3;
    - khách sạn Trip cần ID đã lưu và chỉ hỏi giá;
    - các yêu cầu sai;
  - monitor: nút chỉ trên ô hỏng; API truyền `--source`.
- `src/data_collection/tests/test_pipeline_graph.py` — sửa: `RESUME_STEPS` có `crawl`; `resume_options` của bước cào.
- `src/data_collection/tests/test_pipeline_errors.py`, `tests/test_fresh_catalog_job.py`, `tests/test_live_monitor.py` —
  sửa: hàm giả `run_source` nhận thêm `deadline`.
- `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` — sửa: tiến độ; bảng đối chiếu Airflow (P1, P3, P4a, P4b → "có").
- `history/2026-09-29-p4-han-gio-va-cao-lai-mot-nguon.md` — thêm: entry này.

## Quyết định

- Bước `crawl.py` quá giờ không đổi trạng thái nhóm thành `timeout`, giống bước bị chặn (test cũ khẳng định nhóm vẫn
  `ok`). Bước trong tiến trình quá giờ thì nhóm `timeout`, giống bị chặn thì nhóm `blocked`.
- Dừng nguồn bằng cây tiến trình (`/proc`), không đổi cách khởi động `crawl.py` (không `start_new_session`), để nút Dừng
  của monitor (`terminate_children`) vẫn tìm thấy mọi tiến trình con.
- Giá khách sạn Trip chỉ ghi khi cả bước xong (`trip_live.crawl` giữ kết quả trong bộ nhớ), nên quá giờ thì mất giá của
  lượt đó. Ghi rõ ở giải thích của `timeout.tripHotelsPrices`.
- Cào lại dùng đúng `crawl_sites` (thử lại, bị chặn, hạn giờ như lượt thường), không có bản nháp, không cập nhật xoay vòng
  khách sạn Trip.

## Kiểm tra

- `pytest tests` (env `vsf`): **508 passed, 5 skipped** (thêm 19 test; 5 skip như trước).
- **Kiểm test bắt được lỗi**, mỗi lần tắt một hành vi rồi khôi phục (đã `cmp` file khôi phục):
  - bỏ `terminate_tree` → test tiến trình thật fail (tiến trình con còn sống);
  - bỏ `seal_interim` → test niêm phong fail;
  - bỏ kiểm hạn cả phần cào → test bỏ bước chưa chạy fail;
  - monitor hiện nút ở mọi ô cào → test nút fail.
- **So kết quả monitor** trên 12 lượt thật (bản chụp của P3): chỉ khác `RESUME_STEPS` có thêm `crawl`. Không lượt nào trong
  12 lượt có ô cào hỏng, nên sơ đồ không đổi.
- **Lượt thật** `full-20260929T040739Z-86917` (sandbox, `timeout.vinpearl` = 2 phút, chạy liên tục bật):
  - Vinpearl dừng sau 120,2 s (`catalog.source.timeout`), bước `timeout`, mã 124, `sealed: ["vinpearl"]`;
  - `vinpearl.jsonl.tmp` → `vinpearl.jsonl` (26 bản ghi, dòng cuối trọn) → 130 sản phẩm Vinpearl trong catalog;
  - các nguồn khác xong; gộp, kiểm tra, nạp DB (186 dòng), index chạy tiếp;
  - lượt `partial`, mã 3; cảnh báo `timeout`;
  - **không còn tiến trình Chromium / crawl.py mới** sau lượt (so danh sách PID trước/sau).
- **Cào lại thật**: `./local_crawl.sh run resume full-20260929T040739Z-86917 crawl agoda`:
  - chỉ chạy `crawl.py agoda-hotels`, rồi normalise, validate, db, index, mã 0;
  - `resumes[].from = "crawl:agoda"`; không sót tiến trình.
  - Agoda đã xong từ trước nên crawl.py báo "Không còn URL nào cần crawl" (tiếp tục từ tiến độ đã lưu), interim không đổi.
- `git diff --check`: sạch; `bash -n local_crawl.sh`: ok.
- Cấu hình sandbox (`data/local_crawl/state/settings.json`, Git ignore) đã trả về như trước lượt thử.
- Chưa mở monitor trong trình duyệt: nút "Cào lại nguồn này" và nhãn "Quá giờ" chỉ kiểm qua API và test.

## Còn lại / rủi ro

- Người yêu cầu kiểm tay (plan P4, "Bạn kiểm"):
  - đặt hạn giờ booking 1 phút, chạy lượt local;
  - bấm "Cào lại nguồn này" trên monitor.
- **Cào lại nguồn đã xong không lấy dữ liệu mới:** crawl.py tiếp tục từ tiến độ đã lưu, nên cào lại có ích cho nguồn bị
  chặn / quá giờ giữa chừng. Vinpearl luôn chạy `--refresh` nên cào lại là cào lại từ đầu (~16 phút).
- **Trạng thái lượt sau khi chạy lại** là kết quả của lần chạy lại (như CP6): cào lại agoda thì lượt thành `ok` dù ô
  Vinpearl vẫn "quá giờ". Muốn lượt giữ `partial` khi còn ô cào hỏng thì cần quyết định riêng.
- Tự động cào lại sau N giờ khi bị chặn: để sau (mục đã chốt 4).
- Người yêu cầu muốn gọi Cohere song song khi index (P5, key hiện là Trial). Chưa làm, chưa có trong plan.
- Chưa commit.
