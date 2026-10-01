# Máy gán 597 cặp hole D4a (B0 + E2.e5), chờ người duyệt trong app

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: dang dở — nhãn máy đã ghi, chờ người duyệt trong app rồi mới `holes import` → `gold_v2`
- Phạm vi: evaluation

## Mục tiêu

Người dùng yêu cầu máy gán pool hole `gold_v1__D4a` (597 cặp / 118 câu, sinh từ run `20261001-0623-ec5fbd2` các arm
B0 + E2.e5) **không dùng API key** — Claude tự đọc từng cặp trong phiên và gán theo `gold-guide.md` (gồm 7 quy ước chốt
30/09 + làm rõ #4), người dùng duyệt lại trong app. Theo đúng luồng nhãn máy 29/09. Phục vụ FR-SRC-01..04, AC-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/gold/holes/gold_v1__D4a/labels_A.csv` — thêm: 597 nhãn máy (`sb gold machine-import
  --meta .../pool_meta.json --model claude-fable-5`; dry-run trước, ghi 597 / bỏ qua 0 / từ chối 0).
- `src/evaluation/search_bench/gold/holes/gold_v1__D4a/provenance_A.csv` — thêm: source=machine, lý do từng nhãn.
- `history/2026-10-01-nhan-may-hole-d4a.md` — thêm: entry này.

## Quyết định

- Quy trình gán: digest 597 cặp theo câu (query, filter, name, taxonomy, destination, sao, amenities, snippet, hạng
  phòng) → Claude đọc và gán trong 12 lô → hợp nhất, kiểm phủ kín 597/597, không trùng/thiếu, parent_child nhãn 2 có
  tick hạng phòng (id nở từ prefix theo pool).
- Phân bố: **0 = 193 · 1 = 131 · 2 = 273**.
- Các quyết định gán đáng chú ý (ghi trong `machine_note`, ưu tiên soát khi duyệt):
  1. **Sao không ghi** ở multi_constraint → 1 ("không kiểm được ≥ N", tương tự luật parent_child "không kiểm được").
  2. **c0517/c0531 "3 sao"** → theo filter `≥ 3`: KS 4–5 sao vẫn 2 (vấn đề c0517 từ 29/09 chưa chốt lại — theo filter_text).
  3. **"Khách sạn nghỉ dưỡng" (c0005, c0030)** đọc là resort theo quy ước #6 → khách sạn thường = 1.
  4. **amenity_offtaxonomy theo #4 + làm rõ 30/09**: "điều hòa" chung ≠ "điều hòa độc lập từng phòng" → 1; "Khăn tắm"
     ≠ "Khăn tắm/ga trải giường (phụ phí)" → 1; chỉ khóa amenity đúng nguyên văn mới 2.
  5. **amenity_negation theo #3/#7**: có ghi tiện ích bị cấm → 0 (kể cả "Bếp nhỏ riêng" tính là bếp riêng, c0244);
     không ghi → 2.
  6. **named_entity**: attraction cùng loại nhưng **khác tỉnh** với thực thể → 0; cùng tỉnh sai thực thể → 1; lưu trú
     cùng nơi khi hỏi thực thể lưu trú cụ thể → 1 (c0338 Vincent's House).
  7. **Cát Bà ≠ Hạ Long** (c0409): Cát Bà thuộc Hải Phòng → 0. Rạch Giá ≠ Phú Quốc (c0403) → 0.
  8. **cross_vertical #5** áp nguyên văn: mọi hotel_property/combo/attraction đúng nơi trong danh sách vertical → 2
     (phần lớn nhãn 2 của đợt này nằm ở slice này + amenity "không ghi vẫn có thể 2").

## Kiểm tra

- Script hợp nhất: pool 597 · gán 597 · trùng 0 · thiếu 0 · thừa 0 · label sai 0; mọi prefix hạng phòng nở ra đúng 1 id.
- `machine-import --dry-run`: 597 cặp còn trống sẽ ghi, 0 đã có nhãn người. Import thật: ghi 597 / từ chối 0.
- App dừng trước import, khởi động lại sau (localhost:8501).

## Còn lại / rủi ro

- **Người duyệt toàn bộ 597 nhãn máy trong app** (nhập `gold/holes/gold_v1__D4a/pool_meta.json`, lọc "Có nhãn máy
  chưa duyệt", xem cột lý do máy) — ưu tiên soát 8 nhóm quyết định ở trên. Nhãn máy không chặn `holes import` về mặt
  hợp đồng, nhưng người dùng đã yêu cầu tự duyệt.
- Sau duyệt: `sb gold holes import <thư mục>` → `sb gold check` → commit → `git tag gold_v2` → `sb rescore` →
  `sb compare B0 E2.e5`.
