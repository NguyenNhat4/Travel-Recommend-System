# Bộ lọc miễn phí v2 hiểu điểm tham quan tự do

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13 (chốt cách hiểu trong chat)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (Grounding); `docs/prd/requirements.md` §3 AC-AGT-04
- Mã FR/NFR: FR-AGT-02/04/06, NFR-REL-01, AC-AGT-04/06/07

## Lý do

Người dùng yêu cầu “điểm miễn phí tức vé tham quan tự do”. V2 hiện loại mọi điểm không có giá và không có
ticketed=false, trong khi v1/widget đang gọi những điểm này là tham quan tự do. Đọc backend local cho TP.HCM:
50 điểm còn mở, 41 điểm có giá đứng trước, 9 điểm không có giá đứng cuối, gồm Bưu điện trung tâm và Chợ Bến Thành.
Lọc sau trang nhỏ còn khiến nhiều lượt rỗng dù danh sách có điểm phù hợp.

## Nội dung đề xuất

### `docs/prd/architecture.md` §3 — Grounding

Hiện tại:

> Phân biệt miễn phí có căn cứ, có phí và unknown. Thiếu giá không chứng minh miễn phí.
> free_only chỉ nhận căn cứ vào cửa tự do hoặc giá 0 hợp lệ; thiếu giá không cộng thành 0.

Thay bằng:

> Bộ lọc miễn phí là tìm điểm tham quan tự do. Attraction/golf có giá 0 hoặc ticketed=false là vào cửa tự do.
> Attraction/golf không có giá và không được ghi rõ ticketed=true được nhận theo quy ước tham quan tự do,
> tiền vào cửa tính 0 kèm FREE_ENTRY_ASSUMED: đây là giả định cần xác nhận, không khẳng định miễn phí đã xác minh.
> Giá nguồn vẫn null. Sản phẩm ticketed=true mà thiếu giá, cùng hotel/flight/combo thiếu giá, vẫn unknown;
> không cộng thành 0. Bộ lọc chạy trước phân trang của tập nguồn, không tự đọc thêm trang hay chọn thẻ thay orc.
> Không đưa catalog, cursor, offset hay cơ chế phân trang vào lời chat/nút/Think cho khách. Khi chưa đủ căn cứ,
> nói chưa xác minh được phí vào cửa; khi còn lựa chọn, tự tìm tiếp trong quota hoặc trả phần đã tìm được.

### `docs/prd/requirements.md` §3 AC-AGT-04

Hiện tại:

> Thiếu giá: known subtotal, total/over_by null, trạng thái unknown; không coi thiếu giá là miễn phí.

Thay bằng:

> Thiếu giá: known subtotal, total/over_by null, trạng thái unknown. Riêng attraction/golf không có giá và không
> ghi ticketed=true được tính 0 theo quy ước tham quan tự do, có FREE_ENTRY_ASSUMED cần xác nhận phí vào cửa.
> Giá nguồn giữ null, không khẳng định miễn phí đã xác minh. Hotel/flight/combo và vé thu phí thiếu giá vẫn unknown.

## Thay đổi source sau khi chốt

- `domain/itinerary/draft_validation.py`, `domain/catalog/listing.py`: phân loại có căn cứ/giả định/thu phí/unknown.
- `application/catalog/use_cases.py`, `api/v1/routes/catalog.py`, `contracts/paths/catalog.yaml`: freeOnly trước phân trang.
- `contracts/schemas/catalog.yaml`, `application/catalog/views.py`: entryPolicy tuỳ chọn (free/assumed_free/paid/unknown)
  từ dữ liệu nguồn, để giữ căn cứ ticketed=false dù thuộc tính false bị lược bỏ theo C2; không đổi luật C2.
- `application/itinerary/orc_dispatch.py`, `engine_tools.py`, adapter HTTP/fixture: truyền điều kiện tới nguồn.
- `agents/orc_v2.py`, `domain/itinerary/orc_guardrails.py`, `application/itinerary/v2_final.py`: prompt/Think/final và disclosure.
- Tests local, spec và entry history riêng. Không gọi thêm model thật theo yêu cầu trước đó của người dùng.
