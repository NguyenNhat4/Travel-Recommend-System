# Bỏ link ở tên sản phẩm đã có thẻ, giữ bản đồ khi mở panel chi tiết

- Ngày: 2026-10-02
- Người đề xuất: nhatnm / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: nhatnm, 2026-10-02 (yêu cầu trực tiếp trong phiên)
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §3.2, §4.2
- Mã FR/NFR: FR-AGT-03, AC-AGT-01

## Lý do

Sau đề xuất `2026-10-02-the-va-panel-chi-tiet-trong-tro-ly.md`, người dùng thử trên desktop và chỉ ra hai điểm:

- Tên sản phẩm vừa là link xanh vừa có thẻ ngay dưới, nên bị lặp.
- Mở panel chi tiết thì bản đồ biến mất.

## Nội dung đề xuất

`user-flow.md` §4.2, quy tắc 2:

- Hiện tại: "Bấm thẻ hoặc tên sản phẩm … X hoặc Esc: về lịch trình + bản đồ."
- Thay bằng: "Bấm thẻ: mở panel chi tiết thay chỗ danh sách ngày, bản đồ vẫn hiện và focus đúng điểm … Tên của sản phẩm
  đã có thẻ chỉ in đậm, không làm link."

Wireframe và nhãn bước H của §3.2 sửa theo cùng nội dung.

## Thay đổi source sau khi chốt

- `components/assistant/inlineBold.tsx`: thêm `plainIds`.
- `WidgetNarration.tsx`: tên của sản phẩm đã có thẻ không làm link.
- `WidgetPlanPanel.tsx`: panel chi tiết thay cột danh sách ngày, giữ cột bản đồ.
- `FloatingWidget.tsx`: chỉ hiện panel chi tiết toàn cột khi không có lịch trình.
