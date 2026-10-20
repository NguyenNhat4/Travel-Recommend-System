# Sửa E2E tiến trình trợ lý: bỏ kiểm tra thẻ xem trước đã xoá

- Ngày: 2026-10-14
- Tác giả: Khoa15 / Claude Code
- Nhánh: khoa/perf-lcp-mobile (PR #207)
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

PR #207 có check `Frontend E2E smoke tests` đỏ: hai test `progress and preview follow the stream` ở 390px và 1024px
tìm region `Sản phẩm đã chọn` rồi chờ nó hiện. Region này thuộc `WidgetProgressPreview.tsx`, đã bị xoá bởi
`7fb80221` (feat: add slot planning) trên `release-mvp-v2`, merge vào PR qua `f0e6fef3`. Việc bỏ thẻ là quyết định đã
chốt (`docs/prd/update-archive/2026-10-14-bo-the-xem-truoc-trong-tien-trinh.md`, AC-AGT-09: "trong lúc chờ không hiện thẻ
sản phẩm; thẻ chỉ có trong câu trả lời"). Test không được cập nhật theo nên đỏ.

## File thay đổi

- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: đổi tên test thành "progress follows the stream and shows no
  product cards while waiting"; thay kiểm tra thẻ xem trước bằng kiểm tra không có region `Sản phẩm đã chọn` trong lúc
  chờ và sau khi xong; bỏ kiểm tra nút `Thêm|Đặt ngay` trong thẻ đã xoá.
- `history/2026-10-14-sua-e2e-tien-trinh-bo-the-xem-truoc.md` — thêm entry này.

## Quyết định

- Sửa test, không khôi phục `WidgetProgressPreview`: việc bỏ thẻ đã được chốt và áp dụng, khôi phục sẽ đi ngược PRD.
- Lỗi này không phải do phần hero/panorama của PR #207. Run `Frontend CI` trên `release-mvp-v2` (18:28Z và 23:41Z) cũng
  fail đúng hai test này, và run trên `bf8c1765` (17:12Z, trước merge) đã pass.
- Chưa sửa `release-mvp-v2`: cùng test đang đỏ ở base, cần áp cùng thay đổi vào base (xem "Còn lại").

## Kiểm tra

- Tái hiện trước khi sửa: `NEXT_PUBLIC_ASSISTANT_API=v1 PLAYWRIGHT_PORT=3197 npx playwright test tests/e2e/widget-opening.spec.ts`
  → 2 failed (`toBeVisible` trên `Sản phẩm đã chọn`, element not found), 9 passed.
- Sau khi sửa, cùng spec: 11 passed.
- Toàn bộ E2E legacy như CI (`npx playwright test --grep-invert @assistant-v2`, build `NEXT_PUBLIC_ASSISTANT_API=v1`): 44 passed.
- `npx tsc --noEmit` trong `src/frontend`: exit 0.
- Chưa chạy E2E v2 (`@assistant-v2`).

## Còn lại / rủi ro

- `release-mvp-v2` vẫn đỏ ở cùng hai test cho tới khi áp sửa test này vào base.
- Log E2E có lặp lại `SESSION_REDIS_URL là bắt buộc ở production` từ WebServer. Hai test này đã được sửa nên không còn
  liên quan, nhưng chưa tìm hiểu thêm về cảnh báo này.
- Test vẫn ghi ảnh chụp ra `/tmp/travel-agent-progress-*.png` (có từ trước, chưa đổi).
