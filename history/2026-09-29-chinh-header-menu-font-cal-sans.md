# Chỉnh header, menu dịch vụ, font Cal Sans và gộp trợ lý về một widget

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (chờ nghiệm thu bằng mắt)
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng kiểm tay `/flights` và nêu: bỏ cột "Điểm đến phổ biến" khỏi popup dịch vụ; bỏ Trợ lý AI khỏi header (đang dẫn tới giao diện cũ); bố cục header cái to cái nhỏ; dùng font Cal Sans; sau đó yêu cầu xóa trang `/assistant` để chỉ còn một giao diện trợ lý. Phục vụ FR-AGT-01, FR-CAT-01.

## File thay đổi

PRD (theo đề xuất đã chốt, đã lưu trữ): `docs/prd/user-flow.md` — sửa: wireframe §4.1 bỏ `[Trợ lý AI]`; §2 bỏ route `/assistant`; §3.2, §4.2 (widget thay wireframe trang), §1.2. Đề xuất: `docs/prd/update-archive/2026-09-29-bo-nut-tro-ly-ai-tren-header.md`, `...-gop-giao-dien-tro-ly-ve-widget.md`.

Frontend (`src/frontend/`):
- `src/app/layout.tsx`, `src/app/globals.css` — sửa: nạp Cal Sans + Inter (bỏ Plus Jakarta Sans vốn không được áp dụng), token `--font-sans/--font-display`, `font-synthesis-weight: none`, heading dùng Cal Sans, thang `type-hero`/`type-hero-sub`/`type-title`.
- `src/components/layout/nav/headerStyles.ts` — thêm: hệ kích thước điều khiển header (cao 40 px, 44 px cảm ứng, bo tròn, panel/row dùng chung).
- `src/components/common/Header.tsx` — sửa: bố cục ba cụm, mọi điều khiển cùng hệ, bỏ viên Trợ lý AI, dropdown ngôn ngữ/đặt chỗ/tài khoản cùng vỏ; chế độ gọn 1024–1279 px.
- `src/components/layout/nav/{NavMenu,MenuShell,NavIcon,VerticalChips,navConfig}.ts(x)` — sửa: menu chỉ có dịch vụ, "Tất cả dịch vụ" xếp theo nhóm, bỏ mục trợ lý, bỏ `destinationRoute`; căn `center`; chip cuộn không bị cắt mép và không tràn ở Home.
- `src/features/catalog/landing/{LandingHero,ProductShelf,DestinationTiles,PromoBanner}.tsx`, `src/components/home/HomeView.tsx` — sửa: thang chữ chung, chip/ô tìm kiếm AI 13/16 px; PromoBanner mở widget.
- `src/components/{layout/AppShell,common/MobileTabBar,cart/CartView,search/SearchView,confirmation/ConfirmationView}.tsx` — sửa: nút trợ lý gọi `openFloatingWidget`.
- 26 tệp có tiêu đề h1–h4: bỏ `tracking-tight` (Cal Sans đã khít), tiêu đề ≤ 12 px thêm `font-sans`.
- Xóa: `src/app/(storefront)/assistant/`, `components/assistant/{AssistantView,AssistantConversation,ChatControls,ChatMessageBubble,SavedTripsModal,ShareItineraryModal,SharedTripWelcomeBanner,VoiceListeningBanner,WeatherForecastCard}.tsx`, `services/{assistantShare,shareService,localization}.ts`, `tests/unit/{assistantConversationStarter,assistantShare}.test.ts(x)`, `tests/e2e/assistant-live.spec.ts`.
- Test: sửa `navConfig`, `navMenu`, `cartView`, `confirmationView`, `verticalLanding`, `e2e/routes.spec.ts`, `e2e/navigation.spec.ts`; thêm `headerStyles.test.ts`.
- Docs: `docs/spec/product.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md`, `src/frontend/README.md`.

## Quyết định

- Cal Sans chỉ dùng cho tiêu đề và điều hướng; nội dung dùng Inter. Thử render tiếng Việt: Cal Sans đủ dấu và ₫ nhưng đặc, khó đọc ở 12–16 px. Cal Sans chỉ có một độ đậm nên chặn faux-bold.
- Trước đây `font-sans` ở gốc AppShell ghi đè `body`, cả app render bằng font hệ thống; nay body là Inter.
- Nạp font vẫn bằng `<link>` Google Fonts (không thêm phụ thuộc mạng lúc build).
- Chia sẻ lịch trình: phần tạo/nhận liên kết chỉ nằm ở trang cũ nên bị xóa theo; widget chưa có chức năng chia sẻ. Liên kết `/assistant?share=` đã phát ra sẽ 404.
- Không đổi contract/DB/backend.

## Kiểm tra

- `vitest run`: 42 file, 386 test pass. `eslint`: 0 lỗi, 2 cảnh báo có sẵn (`ItineraryMap`).
- `tsc --noEmit`: chỉ lỗi từ `.next/types` cũ của trang đã xóa (dev server tự sinh lại); mã nguồn sạch.
- Playwright trỏ vào dev server (3000): `navigation`, `routes`, `widget-opening` 26/26 pass. Không chạy `npm run test:e2e` chuẩn (không có `npm`, build ghi đè `.next`).
- Đo header ở 1024–1440 px (đã đăng nhập và khách): không chồng lấn; xem ảnh chụp 375/1024/1440.

## Còn lại / rủi ro

- Chờ nghiệm thu bằng mắt. Nút lưới "Tất cả dịch vụ" nay trùng bốn menu nhóm; có thể bỏ nếu muốn gọn hơn.
- Chưa dọn `.next/types` cũ; dev server sẽ tự cập nhật.
- Chưa commit.
