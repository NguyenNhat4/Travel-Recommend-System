# Sửa 60 filter multi_constraint: taxonomy → variant

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, data

## Mục tiêu

Toàn bộ 60 dòng slice `multi_constraint` trong `gold/drafts_raw.tsv` dùng `{"eq":["taxonomy","hotel_property"]}`. Nhưng theo `docs/spec/data-collection/schema.md` dòng 30, `taxonomy` chỉ nhận `hotel · flight · attraction · combo · golf`; `hotel_property` là giá trị của cột **`variant`**. `store/filters.py` có cả hai tên trong `KEYWORD_FIELDS` và `validate()` chỉ kiểm tên trường + kiểu giá trị, không kiểm enum — nên filter sai vẫn "hợp lệ" và im lặng khớp 0 sản phẩm.

Hệ quả nếu không sửa: `sb gold pool` áp filter này sẽ ra pool rỗng cho cả slice, và `constraint_precision` (guard ≥ 0,95 trong `sbench.yaml`) trở nên vô nghĩa — đúng slice được dựng để đo nó.

Phục vụ FR-SRC-03, AC-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/gold/drafts_raw.tsv` — sửa: 60 dòng slice `multi_constraint`, `""taxonomy"",""hotel_property""` → `""variant"",""hotel_property""` trong cột `filter_json`. Không đổi cột nào khác, không đổi số dòng (601 kể cả header).
- `history/2026-09-24-sua-filter-multi-constraint-variant.md` — thêm: entry này.

## Quyết định

- Sửa dữ liệu draft chứ không nới `validate()` để chấp nhận `taxonomy = hotel_property`: dữ liệu sai, không phải validator sai. `taxonomy` và `variant` là hai cột khác nhau của `items.parquet` (`variant` = `taxonomy` + `attributes.level`, theo spec Part 1).
- Không sửa `validate()` để kiểm enum giá trị trong lần này: đó là thay đổi hành vi của filter AST, thuộc Part 4 của Người B, và cần bàn riêng. Đã ghi vào "Còn lại".
- Sửa bằng một phép thay chuỗi trên toàn cột thay vì NEEDS_EDIT 20 ý định trong app: đây là lỗi hệ thống của bộ sinh draft, không phải quyết định giữ/loại của người soát.

## Kiểm tra

- Trước khi sửa, đánh giá bằng evaluator pandas `store/filters.py::mask` trên `items.parquet` (2.897 search unit): **60/60 filter khớp 0 sản phẩm**; riêng c0481 "khách sạn 5 sao ở Hà Tĩnh dưới 2 triệu" khớp 0.
- Sau khi sửa: 60/60 `F.parse` + `F.validate` OK; số sản phẩm khớp **min 0 · p50 37 · max 65 · tổng 1.848**; c0481 khớp 6 unit.
- Ba dòng vẫn khớp 0 sau khi sửa: `c0502`, `c0503`, `c0504` (Điện Biên — snapshot 2026-09-21 có 17 record nhưng 0 `hotel_property`). Đây là lỗi grounding do catalog trôi, không phải lỗi filter; đã nằm trong danh sách phải loại khi soát draft.
- Kiểm giá trị hợp lệ trực tiếp trên `items.parquet`: `taxonomy ∈ {attraction, combo, flight, golf, hotel}`, `variant ∈ {attraction, combo, flight_route, golf, hotel_property}`.
- `pytest evaluation/search_bench/tests` (từ `src/`): 135 passed, 9 skipped.
- Không chạy `validate_contract.py` / `db/verify.sql`: không đổi OpenAPI, mock, schema hay seed.

## Còn lại / rủi ro

- `F.validate()` vẫn không kiểm giá trị enum của trường keyword, nên lỗi cùng loại (ví dụ `destination` viết sai chính tả, `variant` sai giá trị) vẫn lọt im lặng. Đề nghị Người B thêm kiểm enum dựa trên `vocab.json` ở Part 4, hoặc thêm cảnh báo khi filter khớp 0 sản phẩm lúc `sb gold pool`.
- `drafts_manifest.json` ghi `qa: "passed: 600 unique grounded candidates"` — lần QA đó không phát hiện lỗi này vì chỉ kiểm `filter_json` parse được, không kiểm tập kết quả khác rỗng. Khi sinh bổ sung draft, QA nên thêm bước "filter khớp ≥ 1 sản phẩm".
- Ba dòng Điện Biên (c0502–c0504) và các ý định chết vì catalog trôi vẫn phải loại tay trong app.
