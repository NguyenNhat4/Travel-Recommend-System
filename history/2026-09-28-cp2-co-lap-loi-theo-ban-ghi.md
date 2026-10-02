# CP2: cô lập lỗi theo bản ghi khi ánh xạ nguồn

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

CP2 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`. Trước đây một bản ghi interim hỏng làm sập cả normalize
và mất cả catalog của lượt. Phục vụ FR-CAT-01..04. Không đổi output khi dữ liệu sạch.

## File thay đổi

- `src/data_collection/normalise.py` — sửa:
  - `RecordGuard` bọc 11 lời gọi ánh xạ: vinpearl khách sạn/tour, booking, agoda API/trình duyệt, trip khách sạn/điểm tham quan/tuyến bay/combo, booking điểm tham quan, combo Vinpearl.
  - Bản ghi lỗi ghi vào `<stage-dir>/errors.jsonl` (bước, nguồn, hàm, khoá bản ghi, lỗi, traceback rút gọn) + log `normalise.record.failed`, rồi đi tiếp.
  - Ngưỡng an toàn: một nguồn có ≥ 3 bản ghi lỗi và vượt `--max-error-percent` (mặc định 5), hoặc mọi bản ghi đều lỗi → `RecordErrorRateExceeded`.
  - `normalise_report.json` thêm `recordErrors`.
- `src/data_collection/fresh_settings.py` — sửa: khoá `normalise.maxErrorPercent` (5, 0–100) ở nhóm Chiến thuật.
- `src/data_collection/fresh_catalog.py` — sửa: truyền `--max-error-percent` theo cấu hình.
- `src/data_collection/monitor.py` — sửa: bước `errors` trong `/api/normalise/rows`/`row`; `/api/normalise` trả `recordErrors` theo nguồn, kể cả khi normalize dừng giữa chừng.
- `src/data_collection/monitor_ui/index.html` — sửa: thẻ "Bản ghi lỗi khi ánh xạ" ở tab Chuẩn hoá, danh sách lỗi theo nguồn, xem traceback.
- `src/data_collection/tests/test_normalise_steps.py` — sửa: 4 test CP2.
- `history/2026-09-28-cp2-co-lap-loi-theo-ban-ghi.md` — thêm: entry này.

## Quyết định

- Chỉ bọc bước ánh xạ: đây là nơi dữ liệu từng nguồn biến động. Các bước sau chạy trên dòng đã chuẩn 13 trường; lỗi ở đó vẫn dừng normalize với tên bước (CP1).
- "Mọi bản ghi của nguồn đều lỗi" luôn dừng, kể cả nguồn nhỏ: đó là dấu hiệu lỗi code, như Vinpearl 0 tour ngày 25/09/2026.
- Ngưỡng tối thiểu 3 bản ghi để nguồn nhỏ không bị dừng vì 1–2 bản ghi lẻ.

## Kiểm tra

- Interim 49 MB: `sha256` `bd4730abaf3bab71…`, 2.546 dòng, giống trước; `errors.jsonl` rỗng; 10,4 s.
- `pytest tests` (env `vsf`): **369 passed, 3 skipped** (thêm 4).

## Còn lại / rủi ro

- CP3 tiếp theo. Chưa commit.
