# Xem lịch trình và bản đồ của trợ lý trên màn hẹp

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §4.2 (mục 4 "Ngoài phạm vi")
- Mã FR/NFR: FR-AGT-03, FR-AGT-04

## Lý do

Bài review UX ngày 12/10 (Chrome, cửa sổ hẹp khoảng 625px) phát hiện: khi cửa sổ hẹp hơn 1024px, người dùng không xem được lịch trình theo ngày và bản đồ. Nút "Xem lộ trình & Bản đồ song song" bấm vào không có tác dụng: khung lịch trình và bản đồ có kích thước 0. Trong khi đó, lời trả lời của trợ lý vẫn nói "xem chi tiết ở khung lịch trình bên phải".

Không chỉ điện thoại bị ảnh hưởng. Laptop chia đôi màn hình cũng hẹp hơn 1024px. Hiện `user-flow.md` §4.2 mục 4 ghi "giao diện mobile" là ngoài phạm vi, nên sửa phần này là mở rộng phạm vi.

Trong lúc chờ chốt, ngày 12/10 đã ẩn nút "Xem lộ trình & Bản đồ song song" khi màn hẹp hơn 1024px, để không còn nút bấm không có tác dụng. Thay đổi này không đổi phạm vi (`history/2026-10-12-sua-giao-dien-tro-ly-theo-review-ux.md`).

## Nội dung đề xuất

`user-flow.md` §4.2:

- Hiện tại (mục 4): "**Ngoài phạm vi:** danh sách bình luận, ảnh/video của người đánh giá (…); giao diện mobile."
- Thay bằng: "**Ngoài phạm vi:** danh sách bình luận, ảnh/video của người đánh giá (…). Giao diện riêng cho mobile vẫn ngoài phạm vi, trừ phần sau: **màn hẹp hơn 1024px** thì widget toàn màn hình có ba tab **Chat · Lịch trình · Bản đồ** thay cho ba cột. Nút "Xem lộ trình & Bản đồ" mở tab Lịch trình. Bấm một thẻ hoặc tên sản phẩm thì mở panel chi tiết ở tab Lịch trình. Tab Bản đồ dùng chung bộ lọc ngày với tab Lịch trình."
- Câu "khung lịch trình bên phải" trong lời trả lời của trợ lý (`narrate_outro`, `cost_UNKNOWN` và prompt narrate) đổi thành "khung lịch trình", để đúng với cả hai bố cục.

## Thay đổi source sau khi chốt

- `src/frontend/src/features/itinerary/widget/FloatingWidget.tsx`: dưới `lg` thì hiện thanh tab thay cho bố cục 3 cột (hiện tại cột phải là `hidden lg:flex`, nút thu chat là `hidden lg:flex`).
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`: dưới `lg`, nút "Xem lộ trình & Bản đồ" hiện lại và mở tab Lịch trình.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts`: thêm trạng thái tab đang mở. Bấm thẻ thì chuyển sang tab Lịch trình.
- `src/backend/app/agents/steps/messages.py`, `src/backend/app/agents/steps/prompts.py`: bỏ chữ "bên phải".
- `docs/spec/hop-dong-tich-hop-frontend.md` §4.8, và test frontend cho bố cục tab.
