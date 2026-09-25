# Gỡ banner "Lên lịch trình kết hợp" ở trang chi tiết sản phẩm

- Ngày: 2026-09-24
- Tác giả: nhatutc2 / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Người dùng yêu cầu bỏ khối banner "Lên lịch trình kết hợp xung quanh <điểm đến>" kèm nút "Hỏi Trợ lý AI →" ở trang chi tiết sản phẩm.

## File thay đổi

- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: xoá banner và import `Sparkles` không còn dùng.

## Quyết định

- Chỉ gỡ banner ở trang chi tiết; nút "Hỏi Trợ lý AI →" ở `SearchView.tsx` là phần khác, giữ nguyên.
- Không thay đổi contract/API; lối vào trợ lý AI vẫn còn qua menu và trang tìm kiếm.

## Kiểm tra

- Typecheck frontend (`npx tsc --noEmit`): pass, không lỗi.

## Còn lại / rủi ro

- Không có.
