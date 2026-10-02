# Ẩn nút trang chi tiết cho điểm tham quan tự do

- Ngày: 2026-10-02
- Người đề xuất: người dùng / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: người dùng, 2026-10-02 ("Chốt: ẩn với Tham quan tự do")
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §4.2, mục 3
- Mã FR/NFR: FR-AGT-03, FR-AGT-04, NFR-REL-01

## Lý do

Người dùng yêu cầu nút “Xem trang chi tiết” nổi bật hơn và không hiện với sản phẩm có nhãn “Tham quan tự do”. PRD hiện liệt kê nút này trong panel nhưng chưa nêu ngoại lệ. Các sản phẩm có thể đặt vẫn cần đường dẫn theo FR-AGT-04.

## Nội dung đề xuất

Tại `docs/prd/user-flow.md` §4.2 mục 3:

- Hiện tại: `giá, "Thêm vào giỏ", "Xem trang chi tiết".`
- Thay thế: `giá, "Thêm vào giỏ", "Xem trang chi tiết". Nút "Xem trang chi tiết" chỉ hiện khi sản phẩm không có nhãn "Tham quan tự do"; điểm tham quan tự do vẫn xem được bộ ảnh, mô tả, địa chỉ và chỉ đường trong panel.`

Phân loại dùng cùng quy tắc đang có của nhãn “Tham quan tự do”: `ticketed=false`, hoặc thiếu giá với taxonomy attraction/golf. Không suy luận từ tên và không đổi catalog/API.

## Thay đổi source sau khi chốt

- `src/frontend/src/features/itinerary/widget/WidgetProductDetail.tsx`: dùng `isFreeToVisit` để ẩn link.
- `src/frontend/tests/unit/widgetProductDetail.test.tsx`: kiểm tra điểm tự do không có link, sản phẩm có giá vẫn có link đúng.
- Giữ kiểm thử E2E của panel và đường dẫn cho sản phẩm có giá.
