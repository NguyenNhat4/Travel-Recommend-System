# Banner mời đăng nhập để nhận gợi ý ở trang chủ

- Ngày: 2026-10-09
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khách chưa đăng nhập không thấy khối "Gợi ý" và cũng không có lời giải thích. Thêm banner mời đăng nhập, đúng `docs/spec/product.md` §4.1.3 ("Khách vãng lai: banner 'Đăng nhập để nhận gợi ý theo chuyến đi của bạn' + [Đăng nhập] [Đăng ký]"); phục vụ FR-REC. Không lệch PRD.

## File thay đổi

- `src/frontend/src/components/home/GuestRecommendationBanner.tsx` — thêm: banner (icon la bàn, tiêu đề, một dòng mô tả, nút Đăng nhập và Đăng ký cao 44 px, xếp cột trên mobile).
- `src/frontend/src/components/home/HomeView.tsx` — sửa: hiện banner khi `authReady && !currentPersona`; nút Đăng nhập mở `openLoginModal()`, Đăng ký đi `/register`.
- `src/frontend/tests/unit/homeView.test.tsx` — sửa: mock `authReady`, `openLoginModal`; thêm 2 test (hiện và bấm nút; ẩn khi đang nạp phiên hoặc đã đăng nhập).
- `src/frontend/src/components/common/Header.tsx`, `Footer.tsx` — sửa: chữ "V" trong ô logo thành "X" cho khớp tên X-OTA (sót ở entry `2026-10-09-doi-ten-hien-thi-x-ota-frontend.md`).
- `history/2026-10-09-banner-moi-dang-nhap-goi-y-trang-chu.md` — thêm: entry này.

## Quyết định

- Chờ `authReady` mới hiện banner để khách đã đăng nhập không thấy banner nháy lên lúc nạp phiên.
- Màu brand (xanh), không dùng màu AI (tím), vì đây là lời mời tài khoản, không phải tính năng trợ lý.

## Kiểm tra

- `vitest run tests/unit/homeView.test.tsx`: 10 test pass; `tsc --noEmit` sạch; `eslint` thư mục home và file test sạch.
- Xem bằng Playwright ở `localhost:3000` (desktop 1280 px và mobile 390 px): banner hiện, không tràn ngang. Chưa bấm thử luồng đăng nhập thật.

## Còn lại / rủi ro

- Sau sửa logo: `vitest run` toàn bộ 78 file, 815 test pass; `tsc` sạch.
