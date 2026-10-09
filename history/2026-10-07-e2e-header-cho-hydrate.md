# E2E header: chờ hydrate xong mới focus nút nhóm

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Frontend CI trên `release-mvp-v2` (run 37588770040, commit 737ede46) fail test `header groups open by keyboard and lead to the category pages`: `aria-expanded` của nút "Lưu trú" vẫn là `false` sau khi bấm Enter, fail cả 3 lần retry. Cùng cây frontend đó (d8d334e6, `feat/agent`) lại pass, nên đây là lỗi chập chờn.

## File thay đổi

- `src/frontend/tests/e2e/navigation.spec.ts` — sửa: chờ `networkidle` trước khi focus nút "Lưu trú".

## Quyết định

- Nguyên nhân: thanh nhóm trong `Header.tsx` nằm trong `<Suspense>` vì dùng `useSearchParams`. Ở `/` (trang tĩnh), server render bản fallback (`<!--$!-->` + `BAILOUT_TO_CLIENT_SIDE_RENDERING` trong `.next/server/app/index.html`), sau khi hydrate thì client thay bằng nút DOM mới. Test focus nút cũ ngay sau `goto` nên khi bị thay, focus rơi về `body` và Enter không mở menu. Đã tái hiện bằng cách làm chậm chunk JS rồi focus trước khi hydrate: nút cũ `isConnected=false`, `activeElement=BODY`, đúng lỗi `Received: "false"` của CI.
- Sửa ở test (chờ hydrate như test kế bên đã làm), không đổi component. Người dùng thật dùng bàn phím trước khi hydrate xong cũng mất focus như vậy; nếu muốn xử lý thì phải bỏ Suspense bailout ở thanh nhóm, là việc riêng của FE.

## Kiểm tra

- `npm run build:web` rồi `npx playwright test tests/e2e/navigation.spec.ts`: 10/10 pass.
- Spec tạm (đã xoá) làm chậm chunk JS 1,5 s rồi chờ `networkidle`: pass. Khi focus trước lúc hydrate thì fail đúng như CI.

## Còn lại / rủi ro

- CI không upload `test-results/` nên lần fail không có trace; nên thêm bước upload artifact khi e2e fail.
- Hành vi mất focus trước hydrate của thanh nhóm (xem Quyết định) chưa được sửa.
