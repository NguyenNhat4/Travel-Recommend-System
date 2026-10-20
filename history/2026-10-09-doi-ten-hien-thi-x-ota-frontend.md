# Đổi tên hiển thị V-OTA sang X-OTA trên frontend

- Ngày: 2026-10-09
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Đổi chữ hiển thị "V-OTA" thành "X-OTA" trên giao diện. Người dùng chốt chỉ sửa frontend, không đụng backend, mock và PRD (xem `docs/prd/update/2026-10-09-doi-ten-hien-thi-x-ota.md`).

## File thay đổi

- `src/frontend/src/**` (Header, Footer, LoginView, LoginModal, layout.tsx, các trang hotels/flights/experiences/combos, HomeView, ProductDetailView, FlightResultsView, TicketPanel, ConfirmationView, CartView, ReviewStep, SearchView, WhyPopover, ItineraryMap, widget trợ lý, TravelContext, recentSearches, historyModel...) — sửa: chuỗi hiển thị V-OTA → X-OTA.
- `src/frontend/server/app.ts`, `src/frontend/server/routes/{trips,health}.ts`, `src/frontend/metadata.json` — sửa: chuỗi hiển thị/tên.
- `src/frontend/tests/e2e/checkout-leave.spec.ts`, `tests/unit/{checkoutView,productDetailView}.test.tsx` — sửa: chuỗi mong đợi theo UI.
- `docs/prd/update/2026-10-09-doi-ten-hien-thi-x-ota.md` — sửa: ghi quyết định chốt và phạm vi thu hẹp.
- `history/2026-10-09-doi-ten-hien-thi-x-ota-frontend.md` — thêm: entry này.

## Quyết định

- Giữ nguyên: bình luận mã, `src/data/personas.ts` và tên khách sạn mẫu trong test (dữ liệu mẫu), `api.gen.ts` (sinh tự động từ contract), README, backend, mock, PRD, tên kỹ thuật (`vota`...).
- Câu `message` lỗi do backend trả (`PRODUCT_NOT_FOUND`) vẫn là "…không còn trên V-OTA." vì backend không đổi; trang 404 sản phẩm của frontend tự hiển thị X-OTA.
- PRD chưa cập nhật theo ý người dùng, nên đề xuất ở `docs/prd/update/` vẫn nằm đó (chưa chuyển archive).

## Kiểm tra

- `tsc --noEmit`: sạch. `vitest run`: 78 file, 813 test pass. `eslint`: 0 lỗi (3 cảnh báo có sẵn). Chưa chạy e2e Playwright.

## Còn lại / rủi ro

- Giao diện còn lệch PRD/backend: PRD và `errors.py` vẫn ghi V-OTA. Cần xử lý đề xuất khi muốn đồng bộ.
