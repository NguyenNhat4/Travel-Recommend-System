# Bước ① Hành khách: thông tin giấy tờ cho vé máy bay (FR-BKG-13)

- Ngày: 2026-09-30
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend, backend, contract, data, docs

## Mục tiêu

Trang checkout mới có họ, tên và ngày sinh trẻ em; thiếu các thông tin hãng bay yêu cầu. Làm đủ FR-BKG-13 (đã chốt trong PRD, đề xuất `2026-09-29-ve-may-bay-giay-to-tuy-than` nằm ở `update-archive`) ở bước ① theo mock "Thông tin cho vé máy bay": danh xưng, ngày sinh người lớn, quốc tịch, CCCD/hộ chiếu, số giấy tờ, hạn hộ chiếu, người lớn đi kèm em bé, dòng "Tên in trên vé". Người dùng chọn phạm vi chỉ bước ① (không làm thẻ chuyến bay ở bước ②).

## File thay đổi

- `src/shared/contracts/schemas/booking.yaml`, `src/shared/contracts/openapi.yaml` — sửa: contract 1.11.0, thêm `TravelerTitle`, `TravelerNationality`, `TravelerDocType`, `TravelerDocuments`, `BookingTravelerDocuments`; `CheckoutTraveler.documents`, `BookingTraveler.documents`.
- `src/shared/contracts/tests/validate_contract.py` — sửa: ví dụ hợp lệ và không hợp lệ cho `documents`.
- `src/shared/contracts/tests/booking-rules-cases.json` — sửa: thêm giấy tờ hợp lệ cho mọi hành khách của ca cũ, thêm 15 ca R-DOC-01…09, ca R-FLT-01 hai em bé thêm `ESCORT_OVERLOADED`.
- `db/vota_schema.sql`, `db/init/01_vota.sql` — sửa: cột `app.booking_travelers.documents jsonb`.
- `db/migrations/0006_traveler_documents.sql` — thêm: migration idempotent.
- `docs/spec/DATABASE_SCHEMA.md` — sửa: ERD, mô tả bảng, cột `documents`.
- `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` — sửa: §3.3, mục lục, thêm Phụ lục B (luật R-DOC-01…09, API, backend, frontend, phần chưa làm).
- `src/backend/app/domain/booking/party.py`, `party_rules.py` — sửa: `TravelerDocuments`, luật giấy tờ, ngày sinh người lớn, em bé đi kèm; `flight_dates_of`.
- `src/backend/app/api/v1/schemas/booking.py`, `routes/booking.py` — sửa: nhận `documents` (kiểu chuỗi để sai giá trị thành lỗi theo trường, không phải `422`).
- `src/backend/app/application/booking/__init__.py`, `messages.py`, `views.py` — sửa: xuất `DocumentsInput`, câu thông báo mới, trả `documents` với 4 số cuối.
- `src/backend/app/infrastructure/persistence/postgres_booking.py` — sửa: ghi và đọc `documents`.
- `src/backend/tests/unit/domain/booking/test_party_rules.py`, `tests/unit/application/booking/test_checkout_travelers.py`, `tests/integration/test_booking_postgres.py` — sửa: harness theo bộ ca dùng chung, test use case, round-trip Postgres.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract.
- `src/frontend/src/components/checkout/checkoutRules.ts`, `allocation.ts`, `serverErrors.ts`, `useCheckout.ts`, `TravelersStep.tsx` — sửa: luật cùng bộ với Backend, bản nháp hành khách có `flight`, payload `documents`, ánh xạ lỗi, khối giao diện.
- `src/frontend/tests/unit/checkoutRules.test.ts`, `checkoutAllocation.test.ts`, `checkoutServerErrors.test.ts`, `checkoutView.test.tsx` — sửa: theo bộ ca dùng chung, test payload, ánh xạ lỗi, giao diện (AC-BKG-11, AC-BKG-12).
- `history/2026-09-30-thong-tin-giay-to-hanh-khach-ve-may-bay.md` — thêm: entry này.

## Quyết định

- Không cần đề xuất PRD mới: FR-BKG-13, AC-BKG-11/12 và cột `documents` đã áp dụng trong PRD (`requirements.md`, `data-model.md`).
- Ngày sinh người lớn (bắt buộc khi có vé bay) lấy theo mock đã duyệt và dòng "frontend: ngày sinh người lớn" của đề xuất đã chốt. Chữ FR-BKG-13 không liệt kê trường này; `data-model.md` chỉ ghi ngày sinh "bắt buộc với trẻ em". Không đổi DDL (`birth_date` đã nhận người lớn). **Cần người dùng xác nhận** và nếu muốn thì bổ sung câu chữ FR-BKG-13 qua đề xuất.
- Request cũ không có `documents` mà giỏ có vé bay bị `400 VALIDATION_ERROR` (đúng FR-BKG-13 "bắt buộc"). Contract vẫn để `documents` tuỳ chọn trong schema.
- Em bé xác định theo mọi ngày bay của đơn (dưới 2 tuổi ở bất kỳ chặng nào); người lớn đi kèm phải bay cùng chặng và tối đa 1 em bé mỗi người lớn (bước ②).
- Ngày hết hạn hộ chiếu phải sau ngày bay cuối cùng (`docExpiry <= ngày bay cuối` bị từ chối).
- Số giấy tờ đầy đủ chỉ nằm ở `app.booking_travelers.documents`; response chỉ có `docNumberLast4`; không có trong log, CDP, Insider, Stripe.
- Ca dùng chung cũ: thêm giấy tờ hợp lệ bằng biến đổi văn bản để diff nhỏ, giữ định dạng file.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (102 schemas).
- `make db-migrate`: áp `0006_traveler_documents.sql` lên Postgres local; `make verify-db`: không có dòng FAIL.
- `RUN_POSTGRES_INTEGRATION=1 .venv/bin/python -m pytest src/backend/tests/integration/test_booking_postgres.py`: 4 passed.
- `pytest src/backend/tests/unit/domain/booking src/backend/tests/unit/application/booking`: pass (62 ở application/booking; 133 ca ở domain/booking).
- `pytest src/backend/tests -x --ignore=src/backend/tests/integration`: 899 passed.
- Frontend: `tsc --noEmit` sạch; `vitest run`: 417 passed ở lần chạy cuối. Một lần chạy khác fail 1 ca trong `productDetailView.test.tsx` (không liên quan, lần chạy lại pass; nghi ca phụ thuộc thời gian khi máy tải nặng).

## Còn lại / rủi ro

- Thẻ chuyến bay ở bước ② theo mock (hạng vé, hành khách 3/3, chỗ ngồi, bảo hiểm, hành lý, suất ăn, thành tiền từng chặng): chưa làm, thuộc FR-BKG-10/11.
- `ConfirmationView` chưa hiển thị danh xưng, loại giấy tờ, 4 số cuối dù API đã trả.
- `docs/prd/user-flow.md` §4.4 chưa có wireframe khối thông tin bay (PRD chỉ đổi qua đề xuất).
- Chưa kiểm bằng trình duyệt thật (chỉ test đơn vị và jsdom).
