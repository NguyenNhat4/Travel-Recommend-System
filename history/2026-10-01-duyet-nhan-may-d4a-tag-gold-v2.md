# Duyệt 597 nhãn máy D4a (QAnh), holes import, tag `gold_v2`

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/m6-trip-ended
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Hoàn thành vòng hole D4a: người dùng yêu cầu duyệt toàn bộ nhãn máy dưới tên **QAnh** và đóng phần gold
(`holes import` → `check` → `verify-append` → tag `gold_v2`). Tiếp nối
`history/2026-10-01-nhan-may-hole-d4a.md`. Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/gold/holes/gold_v1__D4a/labels/provenance_A.csv` — sửa: 504 cặp còn lại chuyển
  `review=accepted`, `reviewed_by=QAnh` (duyệt bằng `labeling_core.accept_all_machine` — đúng hàm nút "Duyệt tất cả
  nhãn máy" của app, app đã dừng trước khi ghi). 93 cặp đầu người dùng đã duyệt trong app từ trước; 0 cặp bị sửa nhãn.
- `src/evaluation/search_bench/gold/gold.jsonl` — sửa: `sb gold holes import` thêm **+597 nhãn người + 15 auto_ooc**
  (121 câu có nhãn mới).
- `src/evaluation/search_bench/gold/changelog.yaml` — sửa: mục import hole D4a, version `gold_v2`.
- `src/evaluation/search_bench/gold/holes/gold_v1__D4a/` — thêm vào git: pool, meta, labels (trước giờ untracked).
- `history/2026-10-01-duyet-nhan-may-d4a-tag-gold-v2.md` — thêm: entry này.

## Quyết định

- Người dùng chốt duyệt hàng loạt dưới tên QAnh sau khi đã tự duyệt mẫu 93/597 trong app (0 cặp phải sửa — nhãn máy
  khớp 100% trên mẫu duyệt tay).
- Nhánh làm việc của phần label: `bench/m6-trip-ended` (chứa toàn bộ lineage gold của `bench/embed-search`).

## Kiểm tra

- Duyệt: 504 cặp / 107 câu ghi mới; provenance cuối: 597 accepted, reviewer QAnh 597/597.
- `sb gold check`: **xanh** — 131 câu active, 13 slice, min_per_slice = 3.
- `sb gold verify-append gold_v1`: **xanh** — +0 câu · +612 nhãn · +0 retired (append-only đạt).
- `git tag gold_v2` sau commit; `sb rescore` + `sb compare B0 E2.e5` chạy ngay sau (kết quả ghi ở bước kế).

## Còn lại / rủi ro

- Sau `gold_v2`: đọc lại judged@10 của B0/E2.e5 qua `sb rescore`; Δ của e5 chỉ đọc khi judged@10 ≥ 0,80.
- Đợt hole tiếp theo (APP arms, 02/10) đi cùng vòng: run → holes → gán/duyệt → import → `gold_v3`.
