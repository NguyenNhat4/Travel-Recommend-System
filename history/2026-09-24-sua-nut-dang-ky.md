# Sửa nút "Đăng ký" mở nhầm form đăng nhập

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Bấm "Đăng ký" trên Header thì ra modal đăng nhập, còn vào `/register` thì thấy form đăng nhập. Người dùng không có đường nào vào form đăng ký, trừ khi bấm thêm link chuyển chế độ. Đây là FR-USR-01; route `/register` đã có trong `docs/spec/hop-dong-tich-hop-frontend.md` §3, nên sửa lỗi này không lệch PRD.

## File thay đổi

- `src/frontend/src/components/common/Header.tsx` — sửa: nút "Đăng ký" chuyển tới `/register` thay vì gọi `openLoginModal()`.
- `src/frontend/src/components/auth/LoginView.tsx` — sửa: thêm prop `initialMode` (`login` | `register`, mặc định `login`).
- `src/frontend/src/app/(storefront)/register/page.tsx` — sửa: render `LoginView initialMode="register"`.
- `src/frontend/src/components/common/LoginModal.tsx` — sửa: thêm link "Chưa có tài khoản? Đăng ký miễn phí"; bấm vào thì đóng modal rồi chuyển tới `/register`.

## Quyết định

- Đăng ký dùng trang toàn màn hình `/register`, không làm modal đăng ký, theo `docs/spec/product.md` §4.7.1: modal chỉ dành cho khách bấm hành động cần đăng nhập, còn nút trên header mở trang.

## Kiểm tra

- `npx tsc --noEmit`: không lỗi. `npx eslint` trên 4 file đã sửa: sạch. `npx vitest run`: 76/76 pass.
- `curl http://localhost:3000/register` trên `next dev` đang chạy: render "Đăng ký tài khoản V-OTA" + nút "Tạo tài khoản". `/login` vẫn render "Đăng nhập V-OTA".
- Chưa đăng ký thử một tài khoản thật qua giao diện.

## Còn lại / rủi ro

- Chưa sửa, khác phạm vi: `GET /api/v1/recommendations` trả 500 vì RecSys tắt lúc backend khởi động (`Weaviate 401 Unauthorized` tại `http://weaviate:8080/v1/schema/Product`), khiến `request.app.state.recommend` không tồn tại. Nguyên nhân là cấu hình khoá Weaviate giữa container backend và weaviate.
