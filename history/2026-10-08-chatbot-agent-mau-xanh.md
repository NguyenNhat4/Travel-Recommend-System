# Chatbot agent đổi từ tím sang xanh

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Yêu cầu "chỉnh lại màu xanh cho chatbot agent". Sau `2026-10-08-mau-thuong-hieu-travel-blue.md`, khung chat/launcher/banner trợ lý dùng `ai-*` (tím) còn phần kế hoạch/chi tiết sản phẩm trong cùng widget dùng `brand-*` (xanh), nên widget lệch tông. Chỉ đổi màu, không đổi hành vi, contract hay backend; không lệch PRD.

## File thay đổi

- `src/frontend/src/app/globals.css` — sửa: 11 giá trị `--color-ai-50…950` thành đúng thang `brand` (xanh); cập nhật chú thích vai trò `ai`.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§6.7) — sửa: dòng `ai` ghi cùng giá trị với `brand`, trước đó là tím.
- `history/2026-10-08-chatbot-agent-mau-xanh.md` — thêm: entry này.

## Quyết định

- Đổi giá trị token thay vì thay lớp `ai-*` → `brand-*` ở ~20 file: ít thay đổi, và giữ token `ai` để sau này tách lại màu AI chỉ cần sửa `globals.css`.
- Hiểu "màu xanh" là xanh `brand` (`#2563EB`) cho thống nhất với phần còn lại của widget; nếu muốn một sắc xanh khác (ví dụ sky `#0EA5E9`) chỉ sửa 11 giá trị `ai`.
- `purple-600` ở `ItineraryMap.tsx` là màu phân loại ghim bản đồ, giữ nguyên.

## Kiểm tra

- `vitest run tests/unit`: 64 file, 680 test pass. `tsc --noEmit`: sạch.
- Chưa xem trực quan widget trong trình duyệt.

## Còn lại / rủi ro

- Widget AI và nút đặt chỗ nay cùng màu, không còn phân biệt "AI" với "Đặt chỗ" bằng màu.
