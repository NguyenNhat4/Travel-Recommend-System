# Monitor: bước con của lượt cũ hiện "Chưa ghi số liệu" thay vì "Không chạy"

- Ngày: 2026-10-09
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: test/newcrawl (chưa commit)
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Demo monitor local trên lượt `full-20261007T135856Z-29419`: ô "Kiểm tra catalog" báo Xong (3.578 dòng) nhưng 6 bước con đều
"Không chạy". Lượt 07/10 chạy trước khi job ghi số liệu bước con của maintain / validate / db / index (từ 08/10): các kiểm
tra đã chạy và đạt, chỉ thiếu số liệu từng bước con, nên nhãn "Không chạy" sai nghĩa.

## File thay đổi

- `src/data_collection/monitor.py` — sửa: `with_plan` đặt trạng thái `noData` cho bước con dự kiến khi ô lớn đã xong
  (`ok` / `partial`) mà không ghi bước con nào; các trường hợp khác giữ như cũ (`notRun`, `waiting`, trạng thái ô chưa chạy).
- `src/data_collection/monitor_ui/index.html` — sửa: nhãn `noData` = "Chưa ghi số liệu", tooltip giải thích lượt chạy trước
  khi job ghi số liệu bước con.
- `src/data_collection/tests/test_monitor_progress.py` — sửa: thêm test ô Kiểm tra xong không có bước con → 6 ô `noData`.

## Quyết định

- Chỉ đổi nhãn khi ô lớn không ghi bước con nào; nếu ô có một phần bước con (vd. index bị hoãn) thì bước con thiếu vẫn là
  "Không chạy" như trước. Không đổi job, không đổi dữ liệu; không lệch PRD.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q data_collection/tests` (env vsf2, từ `src/`): 647 passed, 27 skipped.
- `node --check` script của `index.html`: OK.
- Monitor local (lượt sandbox `vmcheck`, `full-20261007T135856Z-29419`): maintain / validate / db / index → bước con
  `noData`, hiện "Chưa ghi số liệu"; normalise (có `steps.json`) vẫn hiện số liệu thật.

## Còn lại / rủi ro

- Chưa commit / deploy.
