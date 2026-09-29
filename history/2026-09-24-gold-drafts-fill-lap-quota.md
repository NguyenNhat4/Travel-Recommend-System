# `sb gold drafts --fill`: lấp quota bằng 1 cách nói mỗi ý định

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

`sb gold drafts` chỉ xuất được 143/200 ý định. Nguyên nhân chính không phải thiếu draft mà là **23 ý định bị loại sạch cả 3 dòng**, phần lớn với lý do `duplicate` ×3 — tức luật "mỗi 3 dòng giữ 1" bị áp thành "loại cả 3". Người dùng chốt: lấy lại tối đa 1 dòng mỗi bộ ba để đủ quota.

Phục vụ FR-SRC-01..04, AC-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/gold.py` — sửa: `select_drafts(..., fill=, fill_guard=)`; thêm hằng `PHRASING_REASONS`, `NOTE_IS_INTENT_KEY`; report thêm `filled` / `skipped_fill`.
- `src/evaluation/search_bench/__main__.py` — sửa: `sb gold drafts --fill`, hàm `_fill_guard` (đọc `items.parquet`, kiểm `source_refs` còn sống và `filter_json` khớp ≥ 1 sản phẩm), in danh sách lấp và danh sách bỏ qua kèm lý do.
- `src/evaluation/search_bench/tests/test_gold_drafts.py` — thêm: 4 test cho `--fill` (lấy lại ý định chưa gán / loại vì cách nói, không đụng ý định loại vì lỗi thật, tôn trọng `fill_guard`, khử trùng `review_note` chỉ ở slice có khoá); sửa fixture để mỗi case có `review_note` riêng.
- `src/evaluation/search_bench/gold/drafts.txt` — sửa: 143 → **182 dòng**.
- `docs/spec/bench/search-eval-local-spec.md`, `docs/spec/bench/search-eval-checklist.md` — sửa: mô tả `--fill` và số liệu 24/09.
- `history/2026-09-24-gold-drafts-fill-lap-quota.md` — thêm: entry này.

## Quyết định

- **Chỉ lấp hai loại ý định**: (a) chưa gán dòng nào, (b) bị loại toàn bộ nhưng mọi lý do đều thuộc `PHRASING_REASONS = (duplicate, unnatural)` — đó là nhận xét về *cách nói*, không phải về ý định. Ý định bị loại với `fabricated_entity` / `bad_grounding` / `invalid_filter` / `wrong_slice` thì **không tự lấy lại**: đó là khẳng định có lỗi thật, agent không được lật quyết định của người soát.
- **Hàng rào grounding** trước khi lấp: bỏ qua nếu mọi `source_refs` đã biến mất khỏi `items.parquet`, hoặc `filter_json` khớp 0 sản phẩm trong catalog hiện hành. Nhờ vậy `--fill` không kéo lại các ý định đã chết vì catalog trôi (ví dụ `c0433` Pleiku).
- **Khử trùng theo `review_note` chỉ ở `dest_type` và `out_of_catalog`.** Đo trên dữ liệu: note là khoá đủ ở 7/13 slice, nhưng ở `multi_constraint` (20 ý định / 10 note), `audience_style` (25/5), `cross_vertical` (10/5), `abbrev_typo` (15/8) note chỉ mô tả khuôn ràng buộc nên hai ý định khác điểm đến dùng chung note. Bản đầu khử trùng cho mọi slice đã chặn nhầm 9 ý định `multi_constraint` — đã sửa.
- Trong mỗi bộ ba, lấy **dòng có `case_id` nhỏ nhất** (dạng câu gốc, không có tiền tố `tìm`, không có mệnh đề đuôi).
- Dòng được lấp ghi `verdict = AUTO_FILL`, `annotator = auto` trong report và in ra từng dòng, để phân biệt với quyết định của người soát. **Không** ghi ngược event giả vào kho nhãn.

## Kiểm tra

- `pytest evaluation/search_bench/tests` (từ `src/`): **139 passed, 9 skipped** (135 trước + 4 mới).
- `sb gold drafts --fill` trên dữ liệu thật: **182/200** (trước đó 143). Lấp 36 ý định = 25 chưa gán + 11 bị loại toàn bộ vì cách nói. Bỏ qua 30 ý định kèm lý do (12 lỗi thật, 17 trùng khoá, 1 nguồn đã chết).
- Đủ quota sau khi lấp: `dest_type` 25, `audience_style` 20, `amenity_multi` 10, `parent_child` 15, `abbrev_typo` 15, `multi_constraint` 20, `cross_vertical` 10, `out_of_catalog` 10.
- `parse_drafts` đọc lại `gold/drafts.txt`: 182 draft, 13 slice, 20 filter parse được, 10 `expected_no_result`, không trùng `(query, slice)`.
- Không chạy `validate_contract.py` / `db/verify.sql`: không đổi OpenAPI, mock, schema hay seed.

## Còn lại / rủi ro

- **Còn thiếu 18 ý định.** `amenity_negation` 5 + `amenity_offtaxonomy` 5: hết draft, phải chờ `c0601`–`c0630`. `named_entity` 5 + `no_diacritics` 2 + `amenity_single` 1: đang bị loại với lý do lỗi thật nên `--fill` không đụng tới.
- **Năm ý định `named_entity` bị loại là `fabricated_entity`/`other` nhưng thực thể có thật trong catalog**, `source_refs` còn sống: `Công Viên 30/4` (c0340, Biên Hòa), `Sông Bằng` (c0349, Cao Bằng), `Núi Sam` (c0352 → "Miếu Bà Chúa Xứ Núi Sam", Châu Đốc), `tiNiWorld` (c0358, Cần Thơ), `Chợ nổi Cái Răng` (c0361, Cần Thơ). Nếu người soát mở lại 5 case này thì `named_entity` đủ 20/20 và tổng lên 187.
- Mã lý do có thể không đáng tin: `fabricated_entity` là **giá trị mặc định** của selectbox trong app, ai bấm REJECT mà không đổi lý do sẽ ra mã này (`khoi` có 92/129 lượt loại mang mã này). Nên coi thống kê lý do là tham khảo, không phải bằng chứng.
- `c0589` "resort ở Hải Dương" được `--fill` lấy vào `out_of_catalog`, nhưng phân tích grounding 24/09 cảnh báo đây là "bạn giả": catalog có attraction `[VinWonders Phú Quốc] - Workshop Nhà Hải Dương Học Nhí` nên BM25 có thể trả kết quả, làm hỏng phép hiệu chuẩn cutoff ở S7. Hàng rào hiện tại không phát hiện được (slice này không có `source_refs` lẫn `filter_json`). Người soát nên đổi sang một trong 7 điểm đến sạch: Mộc Châu, Tam Đảo, Cà Mau, Lạng Sơn, Sóc Trăng, Bảo Lộc, Lý Sơn.
- Các dòng `AUTO_FILL` chưa được người soát nhìn qua. Trước khi tag `gold_v1` nên rà lại 36 dòng này trong `drafts.txt`.
