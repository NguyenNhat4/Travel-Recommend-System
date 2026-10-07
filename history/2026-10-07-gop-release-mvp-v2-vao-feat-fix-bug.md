# Gộp origin/release-mvp-v2 vào feat/fix-bug

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: backend | frontend | contract | docs

## Mục tiêu

Kéo code mới nhất của `release-mvp-v2` (79 commit so với nhánh này, mới nhất là `88dae87`, PR #119) về nhánh đang làm, sau khi đã đẩy commit `0b1c7b1` (hồ sơ cá nhân, lịch sử đặt chỗ `/profile/booking_history`, chi tiết đơn).

## File thay đổi

Ba file xung đột nội dung, đã giải quyết giữ cả hai bên:
- `src/backend/app/api/v1/routes/booking.py` — sửa: import gộp (`logging`, `Literal`, `Query`, `log_event`, `BookingTab`); giữ `GET /bookings` của nhánh này và log của nhánh release.
- `src/frontend/src/services/server/proxy.ts` — sửa: giữ khối ghi họ tên, số điện thoại vào phiên sau `PATCH /auth/me` (nhánh này) trước đoạn log `bff.proxy` và `trackStream` (nhánh release); body đã đọc (`payload`) vẫn trả nguyên cho client; log lỗi làm mới phiên đổi từ `logAuth` (không còn) sang `log.warn` của `lib/logger`.
- `src/shared/contracts/openapi.yaml` — sửa: phiên bản.

Sửa thêm sau khi gộp:
- `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py` — sửa: số phiên bản ứng dụng và test kiểm khớp contract, 1.17.0 → 1.18.0.
- `docs/spec/hop-dong-tich-hop-auth.md` — sửa: ghi `phone` và `PATCH /auth/me` bắt đầu từ contract 1.18.0.

Phần còn lại do git tự gộp (docs, workflow CI, Dockerfile, search/catalog, evaluation…).

## Quyết định

- Gộp (merge) vào nhánh hiện tại thay vì rebase, theo cách các lần trước (`Merge branch 'release-mvp-v2' into feat/booking`); không viết lại lịch sử đã đẩy.
- Số phiên bản contract: nhánh release dùng 1.16.0 và 1.17.0 cho thay đổi tìm kiếm, nhánh này dùng 1.15.0 và 1.16.0 cho đơn hàng và hồ sơ; hai bên trùng số nhưng khác nội dung. Kết quả gộp chứa cả hai nên đặt **1.18.0** (chỉ thêm, tương thích ngược) để không số nào mang hai nghĩa.
- Migration: nhánh release không thêm migration, `0008_user_phone.sql` giữ nguyên số; `db/vota_schema.sql` và `db/init/01_vota.sql` vẫn giống hệt nhau.

## Kiểm tra

- `validate_contract.py`: PASS (115 schema, 93 fixture).
- Backend `RUN_POSTGRES_INTEGRATION=1 pytest src/backend/tests`: 1765 pass, 8 skip, 1 fail có sẵn (`test_local_postgres_adapters.py::test_database_roles_enforce_the_two_connection_boundary`: DB local có 2002 hồ sơ, test chờ 2000). Chạy không cờ: 1738 pass, 1 fail là test kiểm phiên bản (đã sửa ở trên).
- Frontend: `tsc --noEmit` sạch; `eslint .` 0 lỗi (2 cảnh báo sẵn có); `vitest run tests/unit tests/api tests/contract`: 68 file, 684 test pass.
- Chưa chạy: Playwright e2e (cần `next build`), `db/verify.sql`.

## Còn lại / rủi ro

- Nhánh release thêm dependency `pino` cho frontend. Máy này không có `npm`, nên để chạy kiểm tra tôi chép `pino` và các gói phụ thuộc vào `src/frontend/node_modules` (thư mục không theo dõi bằng git). Máy khác chạy `make update` hoặc `npm --prefix src/frontend install` sau khi pull.
- Chưa đẩy lên remote: merge commit mới chỉ ở máy này.
