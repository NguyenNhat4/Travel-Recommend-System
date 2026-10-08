# Thử bảng màu đen vàng

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Thử bảng màu đen và vàng cho cả hệ thống, dựa trên thang `brand` đã có ở `2026-10-08-thang-mau-thuong-hieu-chung.md` (chỉ đổi giá trị, không đổi lớp trong code). Không lệch PRD.

## File thay đổi

- `src/frontend/src/app/globals.css` — sửa: `brand-50…500` thành vàng, `brand-600…950` thành đen (`#2a2a2e` → `#09090b`), `accent-300/400` vàng; chú thích giữ giá trị xanh dương cũ để quay lại.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§6.7) — sửa: ghi bảng màu đang thử.
- `history/2026-10-08-thu-bang-mau-den-vang.md` — thêm: entry này.

## Quyết định

- Đen cho nút chính, hero và chữ nhấn (hover vẫn đậm hơn một nấc); vàng cho nền nhạt, viền chọn, vòng focus và nút Tìm.
- Là bản thử: quay lại xanh dương chỉ cần dán lại 11 giá trị trong chú thích.

## Kiểm tra

- 680 unit test pass. Trình duyệt thật: trang chủ, trang chi tiết khách sạn (thanh tìm kiếm, bộ lọc, thẻ phòng) đã xem, đọc rõ.
- Chưa duyệt các trang còn lại (giỏ, thanh toán, hồ sơ, trợ lý) và chưa đo tương phản từng chỗ dùng `text-brand-300` (11 chỗ, phần lớn trên nền tối).

## Còn lại / rủi ro

- Vàng chỉ xuất hiện ở vài chỗ nên cảm giác thiên về đen; cần quyết định có tăng vàng thành màu nhấn rõ hơn không.
- Chữ vàng trên nền trắng khó đọc; thang này chỉ dùng vàng cho nền, viền và icon, không dùng cho chữ.
