# Prompt sinh 630 case ứng viên cho search gold

Phục vụ **FR-SRC-01**, **FR-SRC-03**, **FR-SRC-04** và **AC-SRC-01** trong `docs/prd/requirements.md`.

## Đầu vào

- `vocab.json` được sinh từ catalog mới nhất, gồm destination, tên sản phẩm, brand, amenity, hạng phòng, hãng bay và mã IATA.
- Quota 13 slice trong `docs/spec/bench/search-eval-local-spec.md` §1.2 (`gold.slices`): tổng mục tiêu 200, mỗi slice ≥ `gold.min_per_slice`.
- Catalog chỉ dùng để grounding. Không sao chép nguyên mô tả dài vào query.

## Prompt

Bạn là người xây dựng bộ truy vấn đánh giá tìm kiếm du lịch tiếng Việt. Hãy sinh query ngắn, tự nhiên, giống cách khách hàng thật gõ vào ô tìm kiếm.

Quy tắc bắt buộc:

1. Mỗi query có đúng một `slice` chính trong danh sách quota được cung cấp.
2. Với query in-catalog, mọi destination, tên sản phẩm, brand, amenity, hạng phòng, hãng bay hoặc mã IATA phải xuất hiện trong `vocab.json`. Không bịa entity.
3. Không tạo hai query chỉ khác viết hoa, dấu câu hoặc khoảng trắng. Slice `no_diacritics` được phép là câu bỏ dấu có chủ đích, nhưng vẫn phải khác ý định với các query đã có.
4. Giữ cách nói tự nhiên; không dùng văn phong kiểm thử như “truy xuất đối tượng”, “lọc bản ghi”, “taxonomy”.
5. `multi_constraint` phải có ít nhất ba ràng buộc có thể chuyển thành filter. Xuất AST JSON tương ứng ở `filter_json`.
6. `out_of_catalog` phải dùng destination hoặc entity không có trong `vocab.json`, để `filter_json` và `source_refs` rỗng, đồng thời đặt `expected_no_result=true`.
7. Thuộc tính vắng mặt trong catalog nghĩa là không biết, không khẳng định là `false`. Với `amenity_negation`, câu hỏi chỉ có nghĩa “không ghi nhận amenity đó”.
8. Không gán nhãn liên quan 0/1/2 và không gán quyết định giữ/loại ở bước này.
9. Mỗi case in-catalog phải có ít nhất một `source_refs` trỏ về `productId` nguồn để người duyệt kiểm tra.
10. Một **ý định** được phép xuất hiện tối đa 3 dòng (3 cách nói của cùng ý định). Số ý định **phân biệt** của mỗi slice phải ≥ mục tiêu sau lọc của slice đó, vì bộ 200 cuối chỉ giữ **một** cách nói cho mỗi ý định. Đổi tiền tố (`tìm …`) hoặc thêm mệnh đề đuôi (`…, có lựa chọn nào?`) **không** tạo ý định mới.

Định dạng đầu ra TSV có header:

```text
case_id<TAB>query<TAB>slice<TAB>filter_json<TAB>expected_no_result<TAB>source_refs<TAB>review_note
```

## Quota ứng viên và mục tiêu sau lọc

| Slice | Ứng viên cần sinh (≥ 3 × mục tiêu) | Mục tiêu người dùng tự lọc |
|---|---:|---:|
| `dest_type` | 90 | 25 |
| `audience_style` | 75 | 20 |
| `amenity_single` | 45 | 15 |
| `amenity_multi` | 30 | 10 |
| `amenity_negation` | 30 | 10 |
| `amenity_offtaxonomy` | 30 | 10 |
| `parent_child` | 45 | 15 |
| `named_entity` | 60 | 20 |
| `no_diacritics` | 60 | 20 |
| `abbrev_typo` | 45 | 15 |
| `multi_constraint` | 60 | 20 |
| `cross_vertical` | 30 | 10 |
| `out_of_catalog` | 30 | 10 |
| **Tổng** | **630** | **200** |

Sinh case ứng viên hợp lệ theo cột “Ứng viên cần sinh” và lưu vào `gold/drafts_raw.tsv`. Không cố ý sinh case lỗi, không tạo rejection log và không chọn thay người dùng. Người dùng sẽ tự lọc xuống bộ 200 theo cột mục tiêu, giữ **một** cách nói cho mỗi ý định.

**Trạng thái 24/09/2026.** `gold/drafts_raw.tsv` đang có 600 dòng (`c0001`–`c0600`), sinh theo quota trước khi người dùng nâng hai slice nhỏ lên 10. Hai slice `amenity_negation` (`c0241`–`c0255`) và `amenity_offtaxonomy` (`c0256`–`c0270`) mỗi slice chỉ có **5 ý định** (15 dòng = 5 ý định × 3 cách nói) — không đủ cho mục tiêu 10. Còn thiếu **30 dòng** = 2 slice × 5 ý định mới × 3 cách nói; phải **append** thành `c0601`–`c0630`, **không đánh số lại** dòng cũ (app gán nhãn khoá quyết định theo `case_id`). Đây là task riêng của Người A, không nằm trong lần sửa quota này. Hai slice `dest_type` (90 dòng / 30 ý định) và `audience_style` (75 / 25) giữ nguyên số ứng viên: mục tiêu giảm còn 25 và 20 nên người dùng được bỏ hẳn 5 ý định mỗi slice.

## Checklist QA trước khi bàn giao

- Mọi query in-catalog truy được entity nguồn qua `source_refs`.
- Query tự nhiên, không trùng sau NFC + casefold + chuẩn hóa khoảng trắng/dấu câu. Hai dòng chỉ khác tiền tố `tìm` hoặc mệnh đề đuôi là **cùng một ý định** — chỉ tính là cách nói thay thế, không tính là ứng viên độc lập.
- `filter_json` parse được và phản ánh đúng câu hỏi.
- Query âm thực sự không có destination/entity tương ứng trong vocabulary hiện tại.
- Mỗi slice đạt cột “Ứng viên cần sinh” và có **ý định phân biệt ≥ mục tiêu**; chưa có quyết định giữ/loại.
