# Search: lọc cứng điểm đến suy ra từ câu (FR-SRC-03) và bộ ngưỡng riêng cho câu không dấu — sau cờ, mặc định tắt

- Ngày: 2026-10-05
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `fix/search`
- Trạng thái: hoàn thành (phần backend + contract + spec; đo bằng bench ghi ở `history/2026-10-05-search-bench-app-e5s.md`)
- Phạm vi: backend, contract, docs

## Mục tiêu

Hai trong bốn kiểu câu yếu của `/search` (plan `fix/search`, Day 6): **lẫn loại / sai điểm đến** (slice `dest_type`: hybrid tụt 13,19 điểm
so dense vì BM25 vớt theo tên chứa địa danh bất kể loại) và **câu không dấu** (slice `no_diacritics`: dense và hybrid rỗng 12/12, hybrid +
normalize còn rỗng 8/12). Người dùng chốt 05/10: lọc điểm đến từ câu là hiện thực FR-SRC-03 ("điểm đến do câu truy vấn quyết định"),
không cần đề xuất PRD; làm sau cờ mặc định tắt, chỉ bật sau khi bench xác nhận. Phục vụ FR-SRC-01/03/04, AC-SRC-01.

## File thay đổi

- `src/backend/app/domain/search/destination.py` — thêm: `decide_destination` (param thắng; đúng một địa danh → lọc; ≥ 2 nơi → `multi`;
  câu vé máy bay → `flight`), `DestinationDecision.as_dict`, `is_flight_query`, `FLIGHT_CUES`.
- `src/backend/app/domain/search/lexical.py` — thêm `is_unaccented(q, min_tokens=3)` (câu gốc không dấu, ≥ 3 token chữ).
- `src/backend/app/domain/search/__init__.py` — sửa: export các hàm trên.
- `src/backend/app/application/search/use_cases.py` — sửa: `SearchProducts` thêm `dest_filter`, `dest_filter_fallback`, `no_diacritics`,
  `no_diacritics_cutoff`, `no_diacritics_min_tokens`; `__call__` nhận `derive_destination` (Agent ghi đè theo lượt); tách `_retrieve` để
  chạy lại khi F rỗng (FR-SRC-04, không gọi embed lần hai); `_hybrid` nhận `cfg` / `cutoff` hiệu lực và `drop_tokens` (token địa danh
  không tính vào độ phủ khi filter suy ra đang áp); diagnostics `derivedDestinations` (luôn), `destinationFilter`, `queryProfile`;
  `appliedFilters` khi cờ bật và có hard filter; `cutoff` của response = cutoff hiệu lực.
- `src/backend/app/core/config.py` — sửa: `search_dest_filter=False`, `search_dest_filter_fallback=True`,
  `search_no_diacritics_mode="off"|"relax"`, `search_no_diacritics_{lexical_k 20, lexical_cutoff 0.0, min_coverage 0.4, cutoff None, min_tokens 3}`.
- `src/backend/app/main.py` — sửa: dựng `HybridConfig` thứ hai khi `relax`, nối 5 tham số mới vào `SearchProducts`; `version="1.14.0"`.
- `.env.example` — sửa: khối biến mới (comment, mặc định).
- `src/shared/contracts/openapi.yaml` — sửa: `version: 1.14.0`. `src/shared/contracts/schemas/search.yaml` — sửa: `EngineDiagnostics` thêm
  `derivedDestinations`, `destinationFilter`, `queryProfile` (optional); ghi chú `AppliedFilters` được phát từ 1.14.0; mô tả `cutoff`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 (luật F điểm đến thay dòng "bước 2", đoạn câu không dấu), §2.4 yaml
  (`destFilter`, `noDiacriticsMode`), §2.5 (`destinationSource`).
- `src/backend/tests/unit/domain/test_destination.py`, `src/backend/tests/unit/application/test_dest_filter.py`,
  `src/backend/tests/unit/application/test_no_diacritics.py` — thêm; `src/backend/tests/unit/domain/test_lexical.py` — sửa (thêm test
  `is_unaccented`).

## Quyết định

- Tham số `destination` tường minh luôn thắng; không giao với địa danh suy ra. Câu ≥ 2 nơi hoặc câu vé máy bay không lọc (nơi đi / nơi
  đến, thương hiệu chứa địa danh). F rỗng → chạy lại không lọc và khai `fallback = dropped_empty` (FR-SRC-04).
- Khi filter suy ra đang áp, bỏ token địa danh khỏi độ phủ tên ở bước vớt BM25 — đây là đòn bẩy cho `dest_type`; câu chỉ có địa danh
  thì giữ nguyên token.
- Câu không dấu: không phục hồi dấu trước embed (unigram sai ở đúng các token hay gặp: sạn/sân, hồ/hộ; cần từ vựng `searchText` mà
  `UnitIndex` không giữ) — chỉ nới cổng vớt BM25 và cutoff cho riêng câu phát hiện không dấu; vector và khoá cache không đổi. Giá trị nới
  là **tạm, trong mẫu**, chờ dev/test split (S đẩy `devtest.py`).
- `derivedDestinations` phát kể cả khi cờ tắt để bench đếm tần suất filter sẽ kích hoạt mà không đổi kết quả.
- Contract bump thẳng **1.14.0**: `release-mvp-v2` đã dùng 1.13.0 (rating / reviewCount) mà nhánh này chưa có; khi merge không dùng lại số.
- Không đụng `release-mvp-v2`; phần backend giữ gọn (domain 2 file, application 1 file, config, main) để cherry-pick.

## Kiểm tra

- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/backend/tests/unit/domain src/backend/tests/unit/application
  src/backend/tests/architecture src/backend/tests/contract` → **610 passed** (29 test mới; cờ tắt ≡ hành vi cũ trên fixture, trừ khoá
  khai báo `derivedDestinations`).
- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py` → PASS (102 schema).
- Chưa đo trên gold (bench): xem entry bench.

## Còn lại / rủi ro

- Cờ mặc định tắt; chỉ đề xuất bật sau khi bench trên gold_v3 qua guard slice (`named_entity`, `abbrev_typo`, `cross_vertical`,
  `out_of_catalog`, win rule `max_slice_loss 3.0`).
- Địa danh đồng âm không dấu ("hue" → Huế) và thương hiệu chứa địa danh có thể suy sai; fallback chỉ cứu khi F rỗng, không cứu khi F
  sai nhưng không rỗng.
- Phủ định và chiều bay chưa làm (chờ câu gold mới); số khách chưa thành filter.
- Phần `release-mvp-v2`: `use_cases.py` ở release có `scored()` (rating) → cherry-pick cần giải conflict.
