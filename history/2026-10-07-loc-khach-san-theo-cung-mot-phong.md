# Lọc khách sạn theo cùng một hạng phòng

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành (backend chưa chạy trong container đang phục vụ; xem "Còn lại")
- Phạm vi: backend, contract, docs

## Mục tiêu

Người dùng muốn tìm kiếm bỏ những khách sạn không còn phòng đúng theo truy vấn, để khỏi phải mở trang chi tiết mới thấy hết phòng. Bản trước (`history/2026-10-07-loc-theo-ngay-o-tim-kiem.md`) lọc từng điều kiện độc lập trên cả khách sạn (giá trên giá thấp nhất, số khách trên sức chứa lớn nhất, ngày trên mọi phòng), nên một khách sạn có phòng rẻ kín lịch và phòng đắt còn lịch vẫn qua. Trang chi tiết thì chỉ cho chọn hạng phòng đang bán (`available` và có giá) rồi kiểm số khách, ngày trên đúng phòng đó. Bản này làm tìm kiếm khớp luật đó. Không lệch PRD: khớp AC-SRC-03 ("hạng phòng đặt được ngày X và đủ chỗ cho 2 người").

## File thay đổi

- `src/backend/app/domain/catalog/unit_attributes.py` — sửa: `ChildRow` thành `(id, giá, sức chứa, lịch, đang bán được)`; `calendars` chỉ còn cho vé tham quan và golf.
- `src/backend/app/domain/catalog/stay_dates.py` — sửa: bỏ `stay_calendars_open` (lịch khách sạn xét theo từng phòng).
- `src/backend/app/application/ports/unit_index.py` — sửa: `mask` gọi `_rooms_ok` khi có lọc giá, số khách hoặc ngày: giữ đơn vị có phòng con khi có ít nhất một con đang bán thoả đồng thời cả ba; `matched_children` nhận `stay` và bỏ phòng chưa bán được.
- `src/backend/app/application/search/use_cases.py` — sửa: bỏ `_joint_children` (mask đã đúng nên không còn loại ở bước kiểm lại); `_child_filter` thêm ngày.
- `src/shared/contracts/schemas/search.yaml`, `schemas/catalog.yaml` — sửa: mô tả `TravelContext.checkIn`, `revalidatedDrops`, `matchedChildren` (không đổi cấu trúc, vẫn 1.19.0).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` (§2.5) — sửa.
- `src/frontend/src/types/api.gen.ts` — sinh lại.
- `src/backend/tests/unit/application/test_search_stay_dates.py`, `test_unit_index_mask.py`, `test_search_v116_knobs.py`, `unit/domain/test_unit_attributes.py`, `test_stay_dates.py` — sửa/thêm.
- `history/2026-10-07-loc-khach-san-theo-cung-mot-phong.md` — thêm: entry này.

## Quyết định

- Phòng "đang bán được" = `available` và có giá, đúng `isBookable` ở trang chi tiết. Khi có lọc cấp phòng, khách sạn có phòng con mà không phòng nào bán được thì bị loại (trước đó không điều kiện cấp phòng thì giữ như cũ).
- Phòng không khai sức chứa hoặc không có lịch thì không bị loại (không biết thì giữ, như trước).
- Kiểm ngay ở `mask` thay vì loại sau khi lấy ứng viên, nên `total`, `facets` và danh sách ứng viên đều chính xác; `revalidatedDrops` không còn tăng vì lý do này.
- `matchedChildren` giờ cũng xuất hiện khi chỉ có lọc ngày (khách sạn), liệt kê các phòng còn mở đúng ngày.
- Thay đổi hành vi nhỏ của `matchedChildren` ở lọc giá/số khách: bỏ các phòng không giá (trước đó giữ phòng giá null khi chỉ lọc số khách).

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract`: 1760 passed, 2 skipped.
- `.venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS. `src/frontend`: `tsc --noEmit` sạch sau khi sinh lại `api.gen.ts`.
- Catalog thật trong Postgres (nạp `PostgresCatalogReader`, `UnitIndex.mask`), khách sạn Nha Trang 105 còn bán: 2 người giữ 105; 6 người trong một phòng giữ 5; dưới 1,5 triệu giữ 90; 12→14/10 giữ 105; 2 người + 12→14/10 + dưới 1,5 triệu giữ 90. Mọi khách sạn đang bán đều có phòng bán được; lịch phòng của lần nạp 07/10 mở hết nên ngày chưa loại khách sạn nào ngoài luật cửa sổ đặt phòng.
- Chưa chạy `RUN_POSTGRES_INTEGRATION=1`; chưa kiểm qua HTTP với backend mới.

## Còn lại / rủi ro

- Container backend :8000 chạy code cũ; cần build lại image để tìm kiếm trên web dùng lọc cùng phòng. Frontend không đổi.
- Số khách ở nhiều phòng được frontend chia đều làm tròn lên rồi so với sức chứa của MỘT phòng; đoàn chia không đều có thể bị loại nhầm hoặc giữ nhầm (nêu ở `history/2026-10-07-loc-so-khach-o-trang-danh-muc.md`).
- Kết quả không hiện phòng khớp trên thẻ khách sạn (`matchedChildren` đã có ở API nhưng giao diện chưa dùng).
