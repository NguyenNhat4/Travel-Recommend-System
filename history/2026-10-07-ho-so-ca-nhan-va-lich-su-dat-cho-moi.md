# Hồ sơ cá nhân (`/profile`), lịch sử đặt chỗ ở `/profile/booking_history`, chỉnh bố cục

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: backend | frontend | contract | data (DDL) | docs

## Mục tiêu

Triển khai đề xuất `docs/prd/update-archive/2026-10-07-ho-so-ca-nhan-va-url-lich-su-dat-cho.md` (mihhquan chốt 2026-10-07):
- FR-USR-04: trang hồ sơ `/profile` sửa họ tên và số điện thoại, đổi mật khẩu; email chỉ xem.
- FR-BKG-14: lịch sử đặt chỗ chuyển sang `/profile/booking_history`; chỉnh bố cục và màu theo bản mẫu https://claude.ai/artifact/J5umeEEBdAnLcYsaKgBL8B (thanh lọc dính, ô ngày ở mỗi thẻ đơn, chân thẻ nền riêng).
- Theo yêu cầu thêm: danh sách thả xuống "Ngày đặt" của trang lịch sử được dựng lại cho cân đối.
- AC-USR-01, AC-USR-02, AC-BKG-18 (đổi địa chỉ).

Ghi chú: `docs/prd/data-model.md` đã có cột `phone` ở `APP_USERS`; DDL chỉ đuổi kịp PRD nên không sửa phần đó của PRD.

## File thay đổi

PRD (cập nhật trước, theo đề xuất đã chốt):
- `docs/prd/requirements.md` — sửa: thêm FR-USR-04, AC-USR-01, AC-USR-02; FR-BKG-14 và AC-BKG-18 đổi sang `/profile/booking_history`.
- `docs/prd/user-flow.md` — sửa: bảng route hai dòng `/profile`, `/profile/booking_history`; §4.5.
- `docs/prd/api-contract.md` — sửa: nhóm Auth thêm `PATCH /auth/me`, `PUT /auth/password`, `phone` ở `GET /auth/me`.
- `docs/prd/update-archive/2026-10-07-ho-so-ca-nhan-va-url-lich-su-dat-cho.md` — thêm: đề xuất đã áp dụng (chuyển thẳng vào lưu trữ, chưa được git theo dõi nên dùng `mv`).

Contract (1.15.0 → 1.16.0, chỉ thêm):
- `src/shared/contracts/paths/auth.yaml`, `schemas/auth.yaml`, `openapi.yaml` — sửa: `PATCH /auth/me` (`updateMe`), `UpdateProfileRequest`, `AuthUser.phone`.
- `src/shared/mocks/auth/updateMe.200-default.json`, `updateMe.422-invalid-phone.json` — thêm; `src/shared/mocks/index.json` — sửa.
- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh.

CSDL:
- `db/vota_schema.sql`, `db/init/01_vota.sql` — sửa (giữ giống hệt nhau): cột `app.users.phone` và ràng buộc `users_phone_format`.
- `db/migrations/0008_user_phone.sql` — thêm: migration idempotent; đã áp lên Postgres local bằng `make db-migrate`, chạy lần hai không áp lại.
- `docs/spec/DATABASE_SCHEMA.md` — sửa: ERD và DDL.

Backend:
- `src/backend/app/application/auth/principal.py`, `ports/auth.py`, `use_cases.py` — sửa: `AuthenticatedUser.phone`, `UserRepository.update_profile`, use case `UpdateProfile`.
- `src/backend/app/infrastructure/auth/postgres_user_repository.py` — sửa: cột `phone`, `update_profile`.
- `src/backend/app/api/v1/schemas/auth.py`, `routes/auth.py`, `app/main.py` — sửa: `UpdateProfileRequest` (trường lạ, body rỗng, họ tên rỗng hoặc null, số điện thoại sai đều 422), `PATCH /auth/me`, nối `update_profile`.
- Test: `tests/contract/test_auth_contract.py`, `tests/unit/application/test_auth_use_cases.py`, `tests/integration/test_auth_postgres.py`, `tests/fakes/auth.py`, `tests/fakes/auth_app.py` — sửa.

Frontend:
- `src/frontend/src/services/server/sessionStore.ts`, `bffSession.ts`, `proxy.ts` — sửa: `SessionUser.phone`, `updateSessionUser`; proxy ghi họ tên, số điện thoại mới vào phiên sau `PATCH /auth/me` 200.
- `src/frontend/src/services/auth.ts`, `src/types/travel.ts`, `src/context/TravelContext.tsx` — sửa: `updateProfile`, `changePassword`, `phone`, `TravelContext.updateProfile` cập nhật người dùng hiện tại ngay.
- `src/frontend/src/features/profile/` — thêm: `AccountShell.tsx` (khung menu trái / tab ngang), `ProfileView.tsx`, `profileModel.ts`.
- `src/frontend/src/app/(storefront)/profile/layout.tsx`, `page.tsx`, `booking_history/page.tsx` — thêm/sửa: khung chung, hồ sơ, lịch sử; `/profile?tab=…` cũ chuyển sang địa chỉ mới giữ bộ lọc.
- `src/frontend/src/features/bookings/BookingHistoryView.tsx`, `BookingCard.tsx` — sửa: bố cục mới, địa chỉ mới; `DaysFilter.tsx` — thêm: danh sách thả xuống "Ngày đặt" tự dựng (thay ô chọn gốc), mở lên trên khi sát đáy, bàn phím đầy đủ.
- `src/frontend/src/components/common/Header.tsx`, `components/confirmation/BookingDetailSections.tsx` — sửa: "Hồ sơ cá nhân" → `/profile`, "Chuyến đi & Đặt phòng của tôi" và đường dẫn ở trang chi tiết đơn → `/profile/booking_history`.
- `src/frontend/src/components/checkout/useCheckout.ts` — sửa: điền sẵn số điện thoại liên hệ từ hồ sơ khi chưa gõ gì.
- Test: `tests/unit/profileModel.test.ts`, `profileView.test.tsx`, `accountShell.test.tsx`, `daysFilter.test.tsx` — thêm; `bookingHistoryView.test.tsx`, `confirmationView.test.tsx` — sửa; `tests/api/bff-auth.test.ts` — sửa (4 test mới cho phiên sau khi sửa hồ sơ); `tests/e2e/routes.spec.ts` — sửa: thêm `/profile/booking_history`.

Tài liệu:
- `docs/spec/hop-dong-tich-hop-frontend.md` (§3, §4.6a, §4.6b mới), `hop-dong-tich-hop-backend.md` (`PATCH /auth/me`), `hop-dong-tich-hop-auth.md`, `src/frontend/README.md`, `src/backend/README.md` — sửa.

## Quyết định

- Phạm vi sửa do người dùng chọn: họ tên, số điện thoại, đổi mật khẩu; email chỉ xem. Sở thích du lịch để sau.
- Số điện thoại chỉ ở `app.users`, không gửi CDP, Insider, Stripe.
- Ràng buộc `phone` có cả ở API (pydantic) lẫn CSDL (CHECK); test tích hợp chứng minh DB từ chối dù bỏ qua API.
- Đổi mật khẩu dùng lại `PUT /auth/password`; sai mật khẩu hiện tại trả 401 `INVALID_CREDENTIALS` (dùng chung thông điệp với đăng nhập) nên Web tự hiển thị "Mật khẩu hiện tại không đúng." chứ không dùng thông điệp của server.
- Giữ tông xanh V-OTA hiện có; không dùng bảng màu xanh lá mà công cụ gợi ý thiết kế đưa ra.
- Tôi hiểu nhầm "popup tất cả" ban đầu thành menu "Tất cả dịch vụ" ở header và sửa nhầm; đã hoàn tác (`git checkout` hai file `NavMenu.tsx`, `headerStyles.ts`) trước khi làm đúng chỗ là ô "Ngày đặt".

## Kiểm tra

- `validate_contract.py`: PASS (115 schema, 93 fixture).
- `make db-migrate` áp `0008` lên Postgres local; chạy lại báo "đã cập nhật (8 migration)".
- Backend: `pytest src/backend/tests` (không cờ tích hợp): 1214 pass, 28 skip, 8 fail. Cả 8 fail đều ở `test_assistant_contract.py` do không nối được Redis (`localhost:6379` chưa chạy) và đã đỏ y hệt trên mã gốc khi kiểm bằng `git stash`; không liên quan thay đổi này. Test tích hợp Postgres của phần đã sửa (`test_auth_postgres.py`, `test_booking_postgres.py`, `RUN_POSTGRES_INTEGRATION=1`): 19 pass. Bộ tích hợp đầy đủ chạy lần trước còn một test đỏ có sẵn: `test_local_postgres_adapters.py::test_database_roles_enforce_the_two_connection_boundary` (DB local có 2002 hồ sơ, test chờ 2000).
- Frontend: `tsc --noEmit` sạch; `eslint .` 0 lỗi (2 cảnh báo sẵn có ở `ItineraryMap.tsx`); `vitest run tests/unit tests/api tests/contract`: 65 file, 666 test pass.
- Mở thật trên trình duyệt (Next dev, API mock): `/profile` (lưu, báo lỗi, đổi tên hiện ở header), `/profile/booking_history` (máy tính, điện thoại), danh sách "Ngày đặt" (mở xuống ở máy tính, lật lên ở điện thoại), chuyển hướng `/profile?tab=cancelled&days=30` sang địa chỉ mới; không lỗi console.
- Chưa chạy: Playwright e2e (cần `next build`); `db/verify.sql` (chưa chạy lại sau migration `0008`).

## Còn lại / rủi ro

- Máy khác phải chạy `make db-migrate` trước khi khởi động Backend mới, nếu không `GET /auth/me` lỗi vì thiếu cột `phone` (đã ghi trong `src/backend/README.md`).
- Seed (`src/data_collection/seed`) không ghi `phone`; cột nullable nên không ảnh hưởng, các tài khoản seed bắt đầu không có số.
- Hồ sơ của 4 tài khoản persona seed: tên hiển thị nay lấy từ `app.users.display_name` thay vì tên cố định của thẻ persona.
- Sở thích du lịch (phần còn lại của FR-USR-02), xác minh và đổi email chưa làm.
- Các thay đổi từ đầu phiên chưa commit.
