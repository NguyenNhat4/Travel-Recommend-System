# Sửa test sức chứa phòng ở trang chi tiết bị chập chờn

- Ngày: 2026-10-01
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

CI frontend fail chập chờn ở `tests/unit/productDetailView.test.tsx` > "khách sạn: gợi ý sức chứa; vượt sức chứa thì khoá
nút đặt…": không tìm thấy `[data-testid="capacity-issue"]`. Tái hiện ở local khoảng 1/3 số lần chạy cả bộ `npx vitest run`.

## File thay đổi

- `src/frontend/tests/unit/productDetailView.test.tsx` — sửa: chờ ô ngày có giá trị (effect đặt lại ngày/số khách theo phòng đã chạy) trước khi bấm bộ đếm khách.

## Quyết định

- Nguyên nhân lấy từ log tạm (đã gỡ) ở lần fail: `findAllByRole('radio')` trả về ngay khi phòng hiện ra, trước khi
  effect `[unit?.id]` của `ProductDetailView` chạy. Khi máy tải nặng, effect chạy sau cú bấm "Thêm người lớn" và ghi đè
  về 1 người lớn; bấm "Thêm trẻ em" thành 2 khách = đúng sức chứa nên không có cảnh báo.
- Sửa test, không sửa component: khoảng hở chỉ là một lượt flush effect, người dùng thật không bấm kịp.

## Kiểm tra

- `npx vitest run` (cả bộ frontend) 8 lần sau khi sửa: 488/488 pass cả 8 lần. Trước khi sửa: fail test này 3/13 lần.

## Còn lại / rủi ro

- Không có.
