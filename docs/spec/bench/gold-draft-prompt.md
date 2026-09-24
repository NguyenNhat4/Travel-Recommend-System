# Prompt sinh 600 case ứng viên cho search gold

Phục vụ **FR-SRC-01**, **FR-SRC-03**, **FR-SRC-04** và **AC-SRC-01** trong `docs/prd/requirements.md`.

## Đầu vào

- `vocab.json` được sinh từ catalog mới nhất, gồm destination, tên sản phẩm, brand, amenity, hạng phòng, hãng bay và mã IATA.
- Quota 13 slice trong `SEARCH_EVAL_LOCAL_SPEC.md` §1.2.
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

Định dạng đầu ra TSV có header:

```text
case_id<TAB>query<TAB>slice<TAB>filter_json<TAB>expected_no_result<TAB>source_refs<TAB>review_note
```

## Quota ứng viên và mục tiêu sau lọc

| Slice | Ứng viên cần sinh | Mục tiêu người dùng tự lọc |
|---|---:|---:|
| `dest_type` | 90 | 30 |
| `audience_style` | 75 | 25 |
| `amenity_single` | 45 | 15 |
| `amenity_multi` | 30 | 10 |
| `amenity_negation` | 15 | 5 |
| `amenity_offtaxonomy` | 15 | 5 |
| `parent_child` | 45 | 15 |
| `named_entity` | 60 | 20 |
| `no_diacritics` | 60 | 20 |
| `abbrev_typo` | 45 | 15 |
| `multi_constraint` | 60 | 20 |
| `cross_vertical` | 30 | 10 |
| `out_of_catalog` | 30 | 10 |
| **Tổng** | **600** | **200** |

Sinh đúng 600 case ứng viên hợp lệ theo cột “Ứng viên cần sinh” và lưu vào `gold/drafts_raw.tsv`. Không cố ý sinh case lỗi, không tạo rejection log và không chọn thay người dùng. Người dùng sẽ tự lọc 600 case xuống bộ 200 theo cột mục tiêu.

## Checklist QA trước khi bàn giao

- Mọi query in-catalog truy được entity nguồn qua `source_refs`.
- Query tự nhiên, không trùng sau NFC + casefold + chuẩn hóa khoảng trắng/dấu câu.
- `filter_json` parse được và phản ánh đúng câu hỏi.
- Query âm thực sự không có destination/entity tương ứng trong vocabulary hiện tại.
- Tổng đúng 600 ứng viên và đúng quota từng slice; chưa có quyết định giữ/loại.
