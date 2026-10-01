# CP1: đo thời gian, số dòng, RAM và lỗi của từng bước normalize

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

CP1 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`. Người dùng cần biết normalize đang ở bước nào, bước nào
chậm, lỗi ở bước nào. Trước đây normalize là một bước duy nhất trong `run.json`; khi lỗi chỉ còn một dòng thông báo, không
có tên bước, và traceback có thể mất khỏi `job.log`. Phục vụ FR-CAT-01..04. Không đổi output (so `sha256`).

## File thay đổi

- `src/data_collection/normalise.py` — sửa:
  - `StepClock`: 10 bước, mỗi bước có giây, số dòng vào → ra, RAM đỉnh; ghi `<stage-dir>/steps.json` mỗi khi đổi bước; log `normalise.step.start/done/failed`.
  - Tách thân `main()` sang `_normalise()` để bắt lỗi một chỗ: bước lỗi ghi `error` + traceback.
  - Tuỳ chọn `--today` để cố định ngày khi so/test. Không truyền thì như cũ.
  - Ảnh chụp `normalise_stages/*.jsonl.gz` nén mức 1 thay vì 9.
- `src/data_collection/fresh_catalog.py` — sửa: normalize lỗi thì báo `normalise lỗi ở bước '<tên>': …`; lượt lỗi in traceback vào `job.log` trước khi `RunRecorder` trả stdout/stderr về luồng gốc.
- `src/data_collection/monitor.py` — sửa: `/api/run` trả `normaliseSteps`; `/api/normalise` trả `steps`, và vẫn trả các bước (`incomplete`) khi normalize đang chạy hoặc đã chết.
- `src/data_collection/monitor_ui/index.html` — sửa: bảng "Thời gian từng bước normalize" ở tab Chuẩn hoá (nút xem traceback); dòng "Normalize đang ở bước …" / "lỗi ở bước …" ở tab Luồng & nguồn.
- `src/data_collection/tests/test_normalise_steps.py` — thêm: 4 test (đủ 10 bước và số dòng; bước lỗi có tên + traceback + log; job và monitor hiện bước lỗi; `--today` cố định output).
- `src/data_collection/tests/fixtures/normalise_sample/interim/*.jsonl` — thêm: 37 bản ghi interim thật của 7 nguồn (392 KB). Chọn theo `dedup_report.csv` để có gộp trùng Vinpearl/booking/agoda ở Nha Trang, vé trùng điểm tham quan, tuyến bay, combo. Chỉ có điểm đánh giá tổng hợp (`reviewScore`/`reviewCount`), không có nội dung đánh giá hay tên người. Dùng cho test CP1–CP5.
- `history/2026-09-28-cp1-do-tung-buoc-normalize.md` — thêm: entry này.

## Quyết định

- Dùng đồng hồ "bấm giờ" (`begin()` ở đầu mỗi bước) thay vì bọc `with`, để không phải thụt lề lại cả khối `main()`. CP4 sẽ tách hàm thật.
- `peakRssMb` là RAM đỉnh của cả tiến trình tính tới hết bước (`ru_maxrss`), không phải RAM riêng của bước.
- Hạ mức nén ảnh chụp vì số đo cho thấy nén mức 9 tốn khoảng 1/3 thời gian; ảnh chụp chỉ để xem.

## Kiểm tra

- Interim 49 MB (7 nguồn), `--destinations @deep`, chạy trong ngày: `products.jsonl` `sha256` `bd4730abaf3bab71…`, 2.546 dòng, **trước và sau giống nhau**. Thời gian 15,0 s → 11,0 s.
  - Theo bước: ánh xạ 6,3 s, gộp trùng khách sạn 1,2 s, vé máy bay/combo 1,0 s, lọc 0,9 s, còn lại < 0,5 s; RAM đỉnh 285 MB.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:<repo>/src python -m pytest -q -p no:cacheprovider tests` (env `vsf`): **365 passed, 3 skipped** (trước: 361).

## Còn lại / rủi ro

- CP2 (cô lập lỗi theo bản ghi) tiếp theo.
- Monitor cần khởi động lại để có API mới.
- Chưa commit.
