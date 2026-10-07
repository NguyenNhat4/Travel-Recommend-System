# Trang hồ sơ cá nhân, đổi URL lịch sử đặt chỗ sang /profile/booking_history

- Ngày: 2026-10-07
- Người đề xuất: mihhquan / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-07
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.6 (FR-USR-02), §1.5 (FR-BKG-14) và §3; `docs/prd/user-flow.md` §2, §4.5; `docs/prd/data-model.md` (bảng `app.users`); `docs/prd/api-contract.md` (nhóm Auth)
- Mã FR/NFR: FR-USR-02 (hồ sơ cá nhân), FR-BKG-14 (đổi địa chỉ trang); mới — đề nghị cấp **FR-USR-04** và **AC-USR-01**, **AC-USR-02**; liên quan NFR-SEC-01

## Lý do

1. **`/profile` hiện là trang lịch sử đơn** (đề xuất `update-archive/2026-10-07-lich-su-don-hang-va-het-cho-sau-thanh-toan.md`), còn hồ sơ cá nhân chưa có: mục "Hồ sơ cá nhân" ở menu tài khoản chỉ hiện thông báo giả. FR-USR-02 yêu cầu "lưu trữ thông tin cá nhân" nhưng PRD chưa nói sửa được gì. Người dùng muốn một trang hồ sơ sửa được thông tin, và địa chỉ rõ ràng: `/profile` cho hồ sơ, `/profile/booking_history` cho lịch sử đặt chỗ.
2. **Hiện hệ thống không có API sửa thông tin cá nhân.** `AuthUser` chỉ có `userId`, `cdpUserId`, `email`, `fullName`; bảng `app.users` chỉ có `display_name`, không có số điện thoại; chỉ có `PUT /auth/password` để đổi mật khẩu. Sửa họ tên và số điện thoại cần endpoint mới và một cột mới, nên là thay đổi lệch PRD.
3. Bố cục và màu của trang lịch sử được chỉnh lại cùng đợt (không lệch PRD, chỉ ghi để đủ ngữ cảnh).

Giao diện mẫu, người dùng xem trước khi chốt: https://claude.ai/artifact/J5umeEEBdAnLcYsaKgBL8B

## Nội dung đề xuất

### 1. `requirements.md` §1.6 — thêm FR-USR-04 (hồ sơ cá nhân)

Hiện tại: mục kết thúc ở FR-USR-03.

Thêm sau FR-USR-03:

> - **FR-USR-04 (Hồ sơ cá nhân):** Người đã đăng nhập xem và sửa hồ sơ ở `/profile`.
>   - **Sửa được:** họ và tên (bắt buộc, tối đa 100 ký tự) và số điện thoại (không bắt buộc; 10 chữ số, bắt đầu bằng 0, cùng quy tắc với số liên hệ của đơn đặt chỗ). **Chỉ xem:** email (dùng để đăng nhập, không đổi ở đây).
>   - **Đổi mật khẩu** ở cùng trang bằng chức năng đổi mật khẩu có sẵn: nhập mật khẩu hiện tại, mật khẩu mới 8–128 ký tự, nhập lại; đổi xong mọi phiên khác bị đăng xuất.
>   - Lỗi nhập hiện ngay dưới ô khi rời ô; nút Lưu chỉ bật khi có thay đổi hợp lệ; lưu xong có thông báo. Họ tên mới hiện ngay ở header và menu tài khoản, không cần đăng nhập lại.
>   - Số điện thoại chỉ lưu trong tài khoản V-OTA (`app.users`); không gửi sang CDP, Insider hay Stripe; được dùng để điền sẵn ô số điện thoại liên hệ ở bước thanh toán. Không có số điện thoại thì ô đó để trống như hiện nay.
>   - Sở thích du lịch (phong cách, ngân sách, thành viên đi cùng) thuộc FR-USR-02 nhưng **chưa nằm trong đề xuất này**.

### 2. `requirements.md` §1.5 — FR-BKG-14, địa chỉ trang

Hiện tại: "Người đã đăng nhập xem mọi đơn của mình ở `/profile`, mới nhất trước."
Thay bằng: "Người đã đăng nhập xem mọi đơn của mình ở `/profile/booking_history`, mới nhất trước." Phần còn lại của FR-BKG-14 giữ nguyên. Cũng ghi thêm cho FR-BKG-14: thanh lọc (tab, chip dịch vụ) dính ở đầu trang khi cuộn; ô "Ngày đặt" và số đơn nằm ngay dưới thanh lọc; mỗi thẻ đơn có ô ngày của dịch vụ đầu tiên để quét nhanh.

### 3. `requirements.md` §3 — thêm AC-USR-01, AC-USR-02; sửa AC-BKG-18

Thêm sau AC-SEC-01 (hoặc trong nhóm AC-USR nếu đã có):

> | **AC-USR-01** | Người dùng mở `/profile`, đổi họ tên và số điện thoại hợp lệ rồi bấm Lưu; sau đó tải lại trang | Có thông báo đã lưu. Tải lại vẫn thấy giá trị mới; header hiện họ tên mới; ô số điện thoại liên hệ ở bước thanh toán được điền sẵn. Email không sửa được. Nhập số điện thoại sai (ví dụ `034548`) thì báo lỗi dưới ô khi rời ô, nút Lưu tắt; gọi thẳng API với số sai hoặc họ tên rỗng trả `422 VALIDATION_ERROR`, không đổi gì. |
> | **AC-USR-02** | Người dùng đổi mật khẩu với mật khẩu hiện tại đúng, rồi sai | Đúng: đổi được, phiên ở thiết bị khác bị đăng xuất, phiên hiện tại vẫn dùng được. Sai: lỗi nêu rõ mật khẩu hiện tại không đúng, không đổi gì. Mật khẩu mới ngắn hơn 8 ký tự bị chặn ngay trong form. |

Sửa AC-BKG-18: thay "mở `/profile`" bằng "mở `/profile/booking_history`".

### 4. `user-flow.md` §2 — bảng route

Dòng `/profile` hiện tại: "Đơn hàng của tôi (Hồ sơ & Lịch sử) … Booking Cards, Pagination, Empty State".
Thay bằng hai dòng:

> | `/profile` | **Hồ sơ cá nhân** | Xem và sửa họ tên, số điện thoại; xem email; đổi mật khẩu (FR-USR-04) | Account Shell (menu trái, tab trên điện thoại), Profile Form, Password Form |
> | `/profile/booking_history` | **Lịch sử đặt chỗ** | Xem lại đơn theo ba tab Sắp đến, Hoàn thành, Đã huỷ; lọc theo dịch vụ và ngày đặt; phân trang (FR-BKG-14) | Account Shell, Tab trạng thái, Service Chips, Date Filter, Booking Cards, Pagination, Empty State |

Dòng `/booking/:referenceCode`: đường dẫn "Đơn hàng của tôi" ở đầu trang chi tiết dẫn về `/profile/booking_history`. §4.5: đổi tiêu đề thành "Hồ sơ cá nhân (`/profile`), Lịch sử đặt chỗ (`/profile/booking_history`) và Chi tiết đơn"; cập nhật wireframe theo bản mẫu (khung tài khoản hai cột).

### 5. `data-model.md` — bảng `app.users`

`data-model.md` đã có cột `phone` ở `APP_USERS`; không sửa PRD phần này. Chỉ DDL thực tế (`db/vota_schema.sql`) thiếu cột; thêm `phone text NULL` kèm ràng buộc CHECK (10 chữ số bắt đầu bằng 0) cho khớp PRD. Không đổi `cdp.profiles`.

### 6. `api-contract.md` — nhóm Auth

Thêm: `PATCH /api/v1/auth/me` (body `{ fullName?, phone? }`, trả `AuthUser` mới); `AuthUser` thêm `phone` (null khi chưa có). Đổi mật khẩu dùng `PUT /api/v1/auth/password` có sẵn. Ví dụ chỉ minh hoạ, nguồn sự thật là `openapi.yaml`.

## Thay đổi source sau khi chốt

PRD cập nhật trước, rồi theo thứ tự contract, DDL, backend, frontend, test:

- **Contract** (`src/shared/contracts/`): `PATCH /auth/me` (`updateMe`), `UpdateProfileRequest`, `AuthUser.phone` (thêm trường, không đổi trường cũ; phiên bản 1.16.0); mock; `validate_contract.py`.
- **DDL**: `db/vota_schema.sql`, `db/init/*.sql`, migration idempotent `db/migrations/0008_user_phone.sql`, `docs/spec/DATABASE_SCHEMA.md`; chạy `make db-migrate`, `db/verify.sql`.
- **Backend** (`src/backend/app/`): use case sửa hồ sơ (`application/auth/`), port và adapter Postgres cho `app.users`, route `PATCH /auth/me`; `/auth/me` và phản hồi phiên trả `phone`; test miền, use case, contract, tích hợp Postgres. Kiểm tra họ tên và số điện thoại dùng cùng quy tắc với `Contact`.
- **BFF/Frontend** (`src/frontend/`): route `/profile` (khung tài khoản, form hồ sơ, form đổi mật khẩu, kiểm tra khi rời ô), route `/profile/booking_history` (chuyển `BookingHistoryView` sang đây và chỉnh bố cục, màu theo bản mẫu), cập nhật họ tên trong phiên BFF và `TravelContext` sau khi lưu, điền sẵn số điện thoại ở checkout, đổi mọi liên kết `/profile` cũ (header, đường dẫn ở trang chi tiết đơn, test); cân nhắc chuyển hướng `/profile?tab=…` cũ sang địa chỉ mới.
- **Spec**: `docs/spec/hop-dong-tich-hop-frontend.md` §3, §4.6a; `docs/spec/hop-dong-tich-hop-auth.md`; `docs/spec/hop-dong-tich-hop-backend.md`; `src/frontend/README.md`, `src/backend/README.md`.

## Điểm còn mở

- Sở thích du lịch (phong cách, ngân sách, thành viên đi cùng) để đợt sau; cần quyết định nơi lưu.
- Xác minh email và đổi email không nằm trong đề xuất này.
- Phiên của BFF (`SessionUser`) đang giữ họ tên; cần chọn cách làm mới ngay sau khi lưu (ghi đè bản ghi phiên) để header không hiện tên cũ.
