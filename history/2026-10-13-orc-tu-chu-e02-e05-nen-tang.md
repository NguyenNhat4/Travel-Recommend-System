# Nền tảng schema, registry và tool đọc cho orc v2

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: agent, backend

## Mục tiêu

Xây nền E02–E05 của `docs/plan/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md`: orc nhận schema thật của tool, nguồn trả dữ kiện qua một dispatcher có hạn mức, sản phẩm có ref và provenance theo lượt. PRD tương ứng đã áp dụng trong `docs/prd/update-archive/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md`.

## File thay đổi

- `src/backend/app/application/itinerary/orc_contracts.py` — thêm: schema quyết định, tool, result và issue; mô tả field đệ quy.
- `src/backend/app/application/itinerary/product_registry.py` — thêm: ref sản phẩm/fact có scope owner-conversation-run, freshness và cursor.
- `src/backend/app/application/itinerary/orc_dispatch.py` — thêm: dispatch đúng tool orc gọi, hạn mức request vật lý, cache trong lượt và retry cùng tham số.
- `src/backend/app/application/itinerary/flight_lookup.py` — thêm: tra dữ kiện vé, ngày/giờ, độ phủ và partial.
- `src/backend/tests/unit/agents/test_orc_contracts.py` — thêm: schema và mô tả bắt buộc.
- `src/backend/tests/unit/agents/test_orc_registry.py` — thêm: owner, stale/unpresented refs, fact/cursor/cache.
- `src/backend/tests/unit/agents/test_orc_tool_dispatch.py` — thêm: args, source quota, lỗi, continuation.
- `src/backend/tests/unit/application/test_orc_flight_lookup.py` — thêm: route, giờ/ngày, partial, result schema.

## Quyết định

- Chỉ quảng bá sáu tool đọc có adapter; `lookup_flights` là extension tường minh. `build_itinerary` được thêm sau khi kiểm validator.
- Giá/availability từ lịch sử chỉ dùng để nhận diện sản phẩm, không dùng làm facts của lượt mới. Không tự thêm Search/Rec hoặc chọn thẻ khi source trả ít.
- So sánh vé chỉ trên trang đã quét; trang tiếp theo cần quyết định tiếp của orc.

## Kiểm tra

- Test trọng tâm E02–E05 và kiến trúc: 18 passed (sau sửa flight/dispatcher gần nhất).
- Toàn backend: 3012 passed, 40 skipped, 3 xfailed, 2 failed; 2 lỗi snapshot cassette có sẵn ở baseline, không nhận là pass.
- `npm --prefix src/frontend run typecheck`: pass.

## Còn lại / rủi ro

- Chưa nối dispatcher vào graph/API v2; E08–E13 cần thực hiện và kiểm bằng model/catalog thật.
- Số liệu giá vé chỉ có phạm vi trang đã đọc. Chưa chứng minh đủ nguồn vé thật và giả lập để đóng AC-AGT-08.
- DoD bao phủ domain/application ≥80% chưa đo vì môi trường chưa có pytest-cov; không coi đã đạt.
