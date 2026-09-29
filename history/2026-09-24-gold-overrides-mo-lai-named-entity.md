# `gold/overrides.tsv`: mở lại 5 ý định named_entity bị loại nhầm

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Sau `sb gold drafts --fill`, `named_entity` còn 15/20. Năm ý định thiếu đều bị người soát loại với mã `fabricated_entity` hoặc `other`, nhưng thực thể trong câu **có thật** trong catalog và `source_refs` còn sống. Người dùng chốt bổ sung lại 5 ý định này.

Phục vụ FR-SRC-01, AC-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/gold.py` — thêm: `read_overrides`, `apply_overrides`; hằng `OVERRIDE_COLUMNS`, `OVERRIDE_VERDICTS`.
- `src/evaluation/search_bench/__main__.py` — sửa: `sb gold drafts` đọc `gold/overrides.tsv` và áp sau khi gộp nhãn, in số case bị ghi đè.
- `src/evaluation/search_bench/gold/overrides.tsv` — thêm: 5 dòng `KEEP` (c0340, c0349, c0352, c0358, c0361), mỗi dòng ghi productId, tên, variant, điểm đến của search unit làm bằng chứng.
- `src/evaluation/search_bench/tests/test_gold_drafts.py` — thêm: 6 test (mở lại ý định đã loại, ghi đè thắng bất đồng, 4 trường hợp dòng sai bị từ chối).
- `src/evaluation/search_bench/gold/drafts.txt` — sửa: 182 → **187 dòng**.
- `docs/spec/bench/search-eval-local-spec.md`, `docs/spec/bench/search-eval-checklist.md` — sửa: mô tả `overrides.tsv`, số liệu 187/200.
- `history/2026-09-24-gold-overrides-mo-lai-named-entity.md` — thêm: entry này.

## Quyết định

- **Không ghi event giả vào kho nhãn.** Ghi event `KEEP` dưới tên `QAnh` là mạo danh người soát; ghi dưới tên khác (`auto`) thì `resolve_decisions` coi là bất đồng và bỏ qua case. Chọn một file quyết định riêng, **có commit**: ai mở lại case nào, vì sao, truy được trong git; và `drafts.txt` tái lập được từ kho nhãn + file này.
- `overrides.tsv` thắng mọi nhãn của app cho case đó, kể cả khi các annotator đang bất đồng; bắt buộc có `note`; `edited_query` chỉ có và bắt buộc có khi `NEEDS_EDIT`; case phải tồn tại trong `drafts_raw.tsv`; không được ghi đè một case hai lần.
- Chỉ mở lại **dòng gốc** của mỗi bộ ba; hai cách nói còn lại vẫn `REJECT duplicate`.
- Bằng chứng từng case (tra `items.parquet`, search unit đúng tên trong câu):

  | case | query | search unit |
  |---|---|---|
  | c0340 | Công Viên 30/4 | attraction, Biên Hòa |
  | c0349 | Sông Bằng | attraction, Cao Bằng |
  | c0352 | Núi Sam | attraction, Châu Đốc |
  | c0358 | tiNiWorld | attraction, Cần Thơ |
  | c0361 | Chợ nổi Cái Răng | attraction, Cần Thơ |

## Kiểm tra

- `pytest evaluation/search_bench/tests` (từ `src/`): **145 passed, 9 skipped** (139 trước + 6 mới).
- `sb gold drafts --fill`: **187/200**, "ghi đè từ overrides.tsv: 5 case ({'KEEP': 5})", `named_entity` 20/20.
- Cả 5 query có trong `gold/drafts.txt`; `parse_drafts` đọc lại 187 draft, q001..q187.
- Không chạy `validate_contract.py` / `db/verify.sql`: không đổi OpenAPI, mock, schema hay seed.

## Còn lại / rủi ro

- Còn thiếu 13. **Chặn `sb gold check`**: `amenity_negation` 5/10 và `amenity_offtaxonomy` 5/10 (dưới `min_per_slice` 10) — phải sinh bù `c0601`–`c0630`. Không chặn cổng, chỉ dưới quota kế hoạch: `no_diacritics` 18/20, `amenity_single` 14/15.
- `c0193` "khách sạn ở Hà Nội có bếp riêng" bị loại `fabricated_entity` nhưng `Bếp riêng` là amenity thật (`raw:bep-rieng`, freq 407). Vì là khoá `raw:` (không có alias seed) nên đúng ra thuộc `amenity_offtaxonomy`, không phải `amenity_single` — nên chuyển slice thay vì mở lại.
- `c0397` "khach san o hai phong co may dieu hoa" bị loại là **đúng**: 121/132 property Hải Phòng (92%) có máy điều hòa nên ràng buộc gần như vô hiệu. Hướng sửa là `NEEDS_EDIT` sang amenity chọn lọc hơn (bữa sáng 38%, nhà hàng 34%, hồ bơi 33%), qua `overrides.tsv` hoặc app.
- Mã `fabricated_entity` là giá trị mặc định của selectbox lý do loại trong app; còn 110 lượt loại mang mã này chưa được rà.
