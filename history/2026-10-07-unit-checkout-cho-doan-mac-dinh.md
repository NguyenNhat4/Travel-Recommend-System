# Unit checkout: `open()` chờ đoàn mặc định dựng xong

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Frontend CI run 37596301200 (commit 9a71f7cd) fail test `AC-BKG-07: bấm Tiếp tục khi còn thiếu thì ở lại bước...` trong `tests/unit/checkoutView.test.tsx` với `Found multiple elements with the role "alert"`. Commit đó chỉ đổi file e2e và history, còn ở d8d334e6 test này pass, nên đây là lỗi chập chờn.

## File thay đổi

- `src/frontend/tests/unit/checkoutView.test.tsx` — sửa: helper `open()` chờ ô `Họ (Người lớn 1)` khi đang ở bước Hành khách.

## Quyết định

- Bằng chứng từ log CI: hộp tóm tắt lỗi chỉ có 2 lỗi, là "Đoàn khách: Cần ít nhất 1 người lớn" và "Người liên hệ · Số điện thoại", cộng thêm dòng `role="alert"` thứ hai của `party-counters`. Như vậy lúc bấm Tiếp tục thì `drafts` đang rỗng. Đoàn mặc định được dựng trong `useEffect` ở `useCheckout.ts` (khởi tạo, khoảng dòng 147) **sau** lần render đã hiện heading "Hành khách", mà `open()` chỉ chờ heading.
- Chưa tái hiện được ở local: probe cho thấy 34/34 lần đoàn đã được dựng khi `open()` trả về, kể cả khi ép tải CPU. Cách sửa chỉ thêm bước chờ cho đúng điều mà mọi test trong file vốn đã giả định, nên an toàn dù cơ chế chính xác trên CI là gì.
- Không đổi component: người dùng thật không bấm kịp trong khe hở giữa render và effect.

## Kiểm tra

- `npx vitest run tests/unit/checkoutView.test.tsx`: 39/39 pass.

## Còn lại / rủi ro

- Chưa có bằng chứng trực tiếp là cách sửa này hết flaky trên CI. Nếu test còn fail, xem số lỗi trong hộp tóm tắt để biết đoàn có rỗng không.
