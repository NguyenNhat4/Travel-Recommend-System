# Đề xuất: vé hạng Thương gia mô phỏng cho seed demo

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người yêu cầu: "cần bổ sung thêm data trước, luồng cào sẽ để sau, tôi cần đưa thêm data vé thương gia và khứ hồi trước, để demo".

Chưa có nguồn hợp lệ cho giá thương gia kèm số hiệu chuyến:
- trip.com: trang tìm kiếm bị robots cấm;
- booking.com: chặn bot;
- `booking.vietnamairlines.com`: trả trang chống bot "Pardon Our Interruption" (kiểm 30/09);
- trang tuyến Vietnam Airlines: không có số hiệu chuyến.

Tạo giá lệch PRD FR-CAT-01 ("không suy hạng hoặc tự tạo giá") → đề xuất và chờ chốt (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-09-30-ve-thuong-gia-mo-phong-cho-demo.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-09-30-de-xuat-ve-thuong-gia-mo-phong.md` — thêm: entry này.

## Quyết định

- Chỉ seed demo sinh vé Thương gia mô phỏng; dữ liệu thật (`--real-flight-dates`) không có.
- Giá = giá thật × 2,65 (tỉ lệ trên bảng "Giá vé tham khảo" công khai của Vietnam Airlines HAN–SGN: 3.957.000 / 1.494.000 một
  chiều, 7.914.000 / 2.988.000 khứ hồi); đánh dấu `simulated` và "(giá minh hoạ)".
- Vé khứ hồi thật đã có: 290 vé (268 hạng Phổ thông) trong snapshot `2026-09-30`.

## Kiểm tra

- Chưa sửa code.

## Còn lại / rủi ro

- Chờ người yêu cầu chốt đề xuất.
