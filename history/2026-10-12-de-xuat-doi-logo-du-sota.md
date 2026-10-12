# Đổi tên hiển thị sang Sota, logo chữ S (frontend)

- Ngày: 2026-10-12
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: dang dở
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng yêu cầu đổi tên hiển thị và các thành phần liên quan sang "Sota", ô logo chữ "S" (trước đó là X-OTA, ô chữ "X"). Thay đổi lệch PRD nên có đề xuất `docs/prd/update/2026-10-12-doi-logo-du-sota.md`.

## File thay đổi

- `src/frontend/src/**`, `src/frontend/server/app.ts`, `src/frontend/server/routes/trips.ts`, `src/frontend/metadata.json` — sửa: mọi chuỗi hiển thị "X-OTA" thành "Sota"; ô logo "X" thành "S" ở `components/common/Header.tsx` (2 chỗ) và `components/common/Footer.tsx`.
- `src/frontend/tests/e2e/checkout-leave.spec.ts`, `tests/unit/{checkoutView,productDetailView}.test.tsx` — sửa: chuỗi mong đợi theo UI.
- `docs/prd/update/2026-10-12-doi-logo-du-sota.md` — thêm: đề xuất (trạng thái chờ chốt).
- `history/2026-10-12-de-xuat-doi-logo-du-sota.md` — thêm: entry này.

## Quyết định

- Tên hiển thị là "Sota" theo tin nhắn mới nhất của người dùng (trước đó nói "Dự Sota"). Phạm vi rộng: mọi chữ "X-OTA" trong `src/frontend`.
- Giữ nguyên như đợt 2026-10-09: backend, mock, PRD, `docs/spec`, tên kỹ thuật `vota`, `personas.ts`, bình luận mã.
- Chữ logo ở Header chính và Footer đang `uppercase` nên hiển thị "SOTA".

## Kiểm tra

- `tsc --noEmit`: sạch. `eslint .`: 0 lỗi (3 cảnh báo có sẵn). `vitest run`: 79 file, 822 test pass. Chưa chạy e2e Playwright.

## Còn lại / rủi ro

- Đề xuất vẫn ghi `chờ chốt`: cần người dùng xác nhận chính thức (tên "Sota" hay "Dự Sota", phạm vi rộng) rồi đổi trạng thái.
- Câu lỗi backend (`PRODUCT_NOT_FOUND`) vẫn ghi V-OTA vì backend không đổi.
