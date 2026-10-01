# CP5: chuẩn hoá theo nguồn ngay khi site cào xong, song song; bản chính thức dùng lại checkpoint

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

CP5 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`. Normalize của một nguồn không phải đợi mọi site cào xong,
và các nguồn chuẩn hoá song song. Trước đây:
- bản nháp chạy lại **toàn bộ** normalize mỗi khi một site xong;
- bản chính thức ánh xạ lại tất cả sau khi mọi site xong.

Phục vụ FR-CAT-01..04. Output không đổi.

## File thay đổi

- `src/data_collection/fresh_catalog.py` — sửa:
  - `Previewer` viết lại: site xong → `normalise.py --only-source` cho từng nguồn của site đó (tối đa 2 tiến trình) → checkpoint thật `<lượt>/normalised/`, mỗi nguồn một bước `normalise.source:<nguồn>` trong `run.json`; sau mỗi nguồn gộp nháp `--merge-only` từ các checkpoint vào `preview/` (gộp dồn khi nhiều nguồn xong cùng lúc).
  - `finish()` luôn đợi các job theo nguồn, chỉ dừng bản gộp nháp.
  - Site cuối của lượt sạch vẫn được chuẩn hoá theo nguồn nhưng không gộp nháp.
  - `normalize()` chạy `--reuse-checkpoints`.
  - `GROUP_INTERIM` thêm `trip_combos`, `booking_attractions`, `booking_flights`, `agoda_api`.
  - `normalise_args(stage=False)` cho chuẩn hoá một nguồn.
  - Khoá của `Previewer` là `RLock`: lần chạy test đầu bị treo do `group_done` giữ khoá rồi gọi `_request_merge`.
- `src/data_collection/normalise.py` — sửa:
  - `--reuse-checkpoints`: bỏ qua nguồn có checkpoint còn mới (dấu vân tay: mtime + cỡ file interim, ngày, tỷ giá, số chuyến mỗi tuyến) và `status` ok.
  - meta checkpoint thêm `status`/`error` và dấu vân tay.
  - `RecordGuard.verdict()` theo từng nguồn; log `normalise.source.done/reuse`.
- `src/data_collection/fresh_settings.py` — sửa: nhãn/giải thích khoá `normalise.preview` ("Chuẩn hoá từng nguồn ngay khi site cào xong (và bản nháp)").
- `src/data_collection/monitor.py` — sửa: `checkpoints()` (meta từng nguồn); `/api/normalise` trả `checkpoints`, kể cả khi bản chính thức chưa có.
- `src/data_collection/monitor_ui/index.html` — sửa: bảng "Chuẩn hoá theo nguồn (checkpoint)" ở tab Chuẩn hoá.
- `src/data_collection/tests/test_live_monitor.py` — sửa: test bản nháp theo cách mới (checkpoint thật, không hard link interim; site cuối không gộp nháp; bản chính thức dùng lại checkpoint; dừng bản nháp vẫn giữ checkpoint; các nhóm site đều được chuẩn hoá theo nguồn).
- `src/data_collection/tests/test_normalise_steps.py` — sửa: 2 test CP5 (4 site xong lần lượt → bản chính thức dùng lại cả 7 nguồn và ra đúng catalog của luồng một lần chạy; checkpoint cũ/lỗi được ánh xạ lại).
- `src/data_collection/README.md` — sửa: mô tả chuẩn hoá theo nguồn, bản nháp và các bảng ổn định trên monitor.
- `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` — sửa: dòng tiến độ CP1–CP5.
- `history/2026-09-28-cp5-normalize-theo-nguon-song-song.md` — thêm: entry này.

## Quyết định

- Bản nháp gộp từ checkpoint thật thay vì chạy lại cả normalize: checkpoint vừa để xem sớm, vừa được bản chính thức dùng lại.
- Chỉ dùng lại checkpoint khi dấu vân tay khớp và `status` ok. Nguồn lỗi ở bước theo nguồn được ánh xạ lại trong bước chính thức, nên lỗi hiện đúng chỗ và lượt vẫn dừng như trước (`CodeError`).
- Tối đa 2 tiến trình chuẩn hoá theo nguồn cùng lúc (VM 2 CPU chạy cùng Chromium). Có công tắc tắt trong Cấu hình.
- Cách làm là **tự xây** bằng Python có sẵn (tiến trình con, `ThreadPoolExecutor`, file checkpoint), không dùng orchestrator ngoài. Mỗi bước là một đơn vị vào/ra theo file để sau này bọc thành task Airflow được.

## Kiểm tra

- Interim 49 MB, mô phỏng lượt thật bằng `Previewer` + `normalize` của job (4 site xong lần lượt):
  - `products.jsonl` `sha256` `bd4730abaf3bab71…` **trùng bản gốc**;
  - bước chính thức dùng lại 7/7 checkpoint;
  - sau khi site cuối xong: 2,7 s chuẩn hoá theo nguồn + 6,2 s gộp (trước đây ~11 s normalize cả khối).
- `pytest tests` (env `vsf`): **387 passed, 3 skipped**. `git diff --check`: sạch.

## Còn lại / rủi ro

- CP6 (chạy lại từ bước lỗi trên monitor) chưa làm.
- Monitor đang mở phải khởi động lại để có API/tab mới; lượt mới tự dùng code mới.
- Chưa chạy lượt cào thật đầy đủ 4 site với code CP1–CP5.
- Chưa commit.
