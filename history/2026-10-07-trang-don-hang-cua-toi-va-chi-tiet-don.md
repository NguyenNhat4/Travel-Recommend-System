# Trang Đơn hàng của tôi (`/profile`) và trang chi tiết đơn đầy đủ

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành (trừ FR-BKG-16, hoãn theo quyết định khi chốt)
- Phạm vi: backend | frontend | contract | docs

## Mục tiêu

Triển khai đề xuất `docs/prd/update-archive/2026-10-07-lich-su-don-hang-va-het-cho-sau-thanh-toan.md` (mihhquan chốt 2026-10-07): FR-BKG-14 (danh sách đơn: ba tab Sắp đến / Hoàn thành / Đã huỷ, lọc dịch vụ và ngày đặt 1/7/30/60, phân trang 5 đơn, trạng thái trống/lỗi), FR-BKG-15 (chi tiết đơn hai cột), AC-BKG-18, AC-BKG-19. Giao diện chốt trên bản mẫu https://claude.ai/artifact/ATHDHksuHw5ddMFS5ADqX9.

**Hoãn theo quyết định khi chốt:** FR-BKG-16 và AC-BKG-20 (kiểm tra lại chỗ sau khi Stripe thu tiền, từ chối và hoàn 100% khi hết chỗ) không đưa vào PRD và không code đợt này; không thêm `INVENTORY_UNAVAILABLE` vào `PaymentFailureReason`.

## File thay đổi

PRD và đề xuất (PRD cập nhật trước, theo đề xuất đã chốt):
- `docs/prd/requirements.md` — sửa: thêm FR-BKG-14, FR-BKG-15, AC-BKG-18, AC-BKG-19; FR-USR-02 trỏ tới FR-BKG-14.
- `docs/prd/user-flow.md` — sửa: dòng route `/profile` và `/booking/:referenceCode`; thêm §4.5 wireframe.
- `docs/prd/api-contract.md` — sửa: §2.6 thêm `GET /bookings` (ví dụ minh hoạ).
- `docs/prd/update-archive/2026-10-07-lich-su-don-hang-va-het-cho-sau-thanh-toan.md` — thêm (đề xuất đã áp dụng, chuyển thẳng vào lưu trữ; chưa được git theo dõi nên dùng `mv`): trạng thái đã áp dụng, ghi FR-BKG-16 hoãn.

Contract (1.14.0 → 1.15.0, chỉ thêm):
- `src/shared/contracts/paths/booking.yaml` — sửa: `GET /bookings` (`listBookings`).
- `src/shared/contracts/schemas/booking.yaml` — sửa: `BookingTab`, `BookingSummaryItem`, `BookingSummary`, `BookingListResponse`.
- `src/shared/contracts/schemas/common.yaml` — sửa: `Pagination`.
- `src/shared/contracts/openapi.yaml` — sửa: phiên bản, đăng ký schema mới.
- `src/shared/mocks/index.json` — sửa; `src/shared/mocks/booking/listBookings.200-default.json`, `.200-cancelled.json`, `.200-empty.json`, `.422-invalid-tab.json` — thêm.
- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh bằng `openapi-typescript`.

Backend:
- `src/backend/app/domain/booking/listing.py` — thêm: `BookingTab`, `BookingOverview`, `tab_of`, `item_end_date`; `domain/booking/__init__.py` — sửa: export.
- `src/backend/app/application/ports/booking_store.py` — sửa: `BookingTx.list_overviews`, `get_many`.
- `src/backend/app/infrastructure/persistence/postgres_booking.py` — sửa: hai method mới (một truy vấn tóm tắt, một truy vấn nạp theo lô, không N+1); tách `_payment_of`, `_item_of` khỏi `_load` để dùng lại.
- `src/backend/app/application/booking/queries.py`, `views.py`, `__init__.py` — sửa: `ListBookings`, `booking_summary`, `pagination`.
- `src/backend/app/api/v1/routes/booking.py`, `src/backend/app/main.py` — sửa: route `GET /bookings`, nối `list_bookings`.
- Test: `tests/unit/domain/booking/test_listing.py`, `tests/unit/application/booking/test_list_bookings.py` — thêm; `tests/contract/test_booking_contract.py`, `tests/fakes/booking.py`, `tests/integration/test_booking_postgres.py` — sửa.

Frontend:
- `src/frontend/src/services/booking.ts` — sửa: kiểu mới và `listBookings`.
- `src/frontend/src/features/bookings/` — thêm: `historyModel.ts`, `BookingHistoryView.tsx`, `BookingCard.tsx`, `HistoryPagination.tsx`, `tone.ts`.
- `src/frontend/src/app/(storefront)/profile/page.tsx` — thêm: route `/profile`.
- `src/frontend/src/components/confirmation/BookingDetailSections.tsx`, `bookingDefaults.ts`, `useProductInfo.ts` — thêm: các khối chi tiết đơn, giá trị mặc định chung, nạp thông tin cơ sở từ catalog.
- `src/frontend/src/components/confirmation/ConfirmationView.tsx` — sửa: bố cục hai cột, đường dẫn, khung thanh toán chứa nút huỷ; giữ nguyên thẻ trạng thái, polling, huỷ, đặt lại.
- `src/frontend/src/components/common/Header.tsx` — sửa: hai lối vào `/profile`.
- Test: `tests/unit/bookingHistoryModel.test.ts`, `tests/unit/bookingHistoryView.test.tsx` — thêm; `tests/unit/confirmationView.test.tsx` — sửa (thêm mock catalog và 7 test chi tiết; thu hẹp một biểu thức kiểm "không có ngày sinh" vì trang nay có ngày đặt và hạn huỷ hợp lệ); `tests/e2e/routes.spec.ts` — sửa: thêm `/profile`.

Tài liệu:
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §3 hàng `/profile`, thêm §4.6a, mô tả bố cục §4.6.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: thêm §7.3a, §8.3 nêu `page`/`pageSize`.
- `src/backend/README.md`, `src/frontend/README.md` — sửa.
- `history/2026-10-07-de-xuat-lich-su-don-hang-va-het-cho.md` — entry trước đó của việc tạo đề xuất, không sửa.

## Quyết định

- Backend quyết định tab, lọc, đếm; Web không tự lọc. Quy tắc tab nằm ở `domain/booking/listing.py::tab_of` và dùng chung cho lọc, đếm, phân trang. Truy vấn lấy tóm tắt cả đơn của người dùng rồi phân loại bằng hàm miền, thay vì lặp quy tắc bằng SQL; đủ cho số đơn của một người dùng.
- Phân trang `page`/`pageSize` theo `docs/prd/api-contract.md` §1.3 và `/assistant/conversations`, khác `limit`/`offset` của danh sách catalog; đã ghi ở backend spec §8.3.
- Đơn `PENDING_PAYMENT` quá hạn giữ chỗ được xếp vào Đã huỷ ngay khi đọc, không chờ job đối soát; Web hiện "Hết hạn giữ chỗ".
- Thẻ đơn chỉ có Xem chi tiết, Tiếp tục thanh toán, Đặt lại. "Huỷ đơn" và "Huỷ giữ chỗ" nằm ở trang chi tiết (không đưa hộp thoại huỷ ra thẻ) — khác bản mẫu giao diện, chọn để không nhân đôi luồng huỷ.
- Địa chỉ, hạng sao, tiện ích đọc từ `GET /products/{id}` của hạng phòng và khách sạn cha, không mở rộng `BookingResponse`. Chỉ dùng địa chỉ thật của catalog; không lùi về tên điểm đến.
- Giờ nhận phòng "Sau 14:00", trả phòng "Trước 12:00" và số tổng đài giả lập `1900 0000` là hằng số ở `bookingDefaults.ts` (theo FR-BKG-15, chốt 2026-10-07).

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (114 schema, 91 fixture).
- Backend `RUN_POSTGRES_INTEGRATION=1 pytest src/backend/tests` (Postgres local đã seed): xem dòng kết quả cuối entry; test mới (domain, use case, contract, tích hợp Postgres) đều pass. Tám test của `test_assistant_contract.py` đỏ cả trên mã gốc (đã kiểm bằng `git stash`), không liên quan.
- Frontend: `tsc --noEmit` sạch; `eslint .` 0 lỗi, 2 cảnh báo sẵn có ở `ItineraryMap.tsx`; `vitest run tests/unit tests/api tests/contract`: 61 file, 627 test pass.
- Mở thật trên trình duyệt (Next dev, API mock): `/profile` (ba tab, điện thoại) và `/booking/{mã}` (máy tính, điện thoại) dựng đúng, không tràn ngang.
- Chưa chạy: Playwright e2e (cần `next build`), `db/verify.sql` (không đổi schema).

## Còn lại / rủi ro

- FR-BKG-16 (đã thu tiền nhưng hết chỗ) hoãn. Hiện hệ thống vẫn không kiểm lại chỗ sau thanh toán.
- Trạng thái xuất vé và mã đặt chỗ hãng (FR-BKG-12) chưa có trong `BookingResponse` nên trang chi tiết không hiện; PRD FR-BKG-15 nhắc tới chúng, cần quyết định riêng (mở rộng contract hoặc sửa PRD).
- Số tổng đài là số giả; cần số thật. Diện tích phòng không hiện.
- Lệch có sẵn, chưa xử lý: `docs/spec/hop-dong-tich-hop-frontend.md` §3 quy ước route cần đăng nhập chuyển `/login?redirect=` nhưng chưa được cài đặt; trang `/profile` dùng lời mời đăng nhập tại chỗ.
- Hồ sơ cá nhân và sở thích (phần còn lại của `/profile` theo FR-USR-02) chưa làm.
