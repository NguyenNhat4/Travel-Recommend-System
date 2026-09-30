# Đề xuất: vé máy bay khứ hồi đặt được, không thêm `level`

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs (data, contract, frontend)

## Mục tiêu

Người yêu cầu hỏi có lấy thêm được vé một chiều và khứ hồi không ("hiện tại chỉ có unitPrice?"), rồi chốt:
- vé khứ hồi **phải đặt được**;
- **không thêm `level`**.

Lệch PRD (thêm loại đơn vị đặt chỗ), nên tạo đề xuất và dừng trước khi code (AGENTS.md §8).

## File thay đổi

- `docs/prd/update/2026-09-29-ve-khu-hoi-dat-duoc.md` — thêm: đề xuất, trạng thái `chờ chốt`:
  - mỗi hành trình khứ hồi = `taxonomy: flight`, `level: flight`, `tripType: "roundTrip"`, giá tổng một người lớn,
    `usingDate` = ngày đi;
  - sửa FR-CAT-01, FR-CAT-02 và `data-model.md` §3.1;
  - 4 mục cần chốt.
- `history/2026-09-29-de-xuat-ve-khu-hoi-dat-duoc.md` — thêm: entry này.

## Quyết định

- Kiểm tra dữ liệu (chỉ đọc):
  - trip.com trả 10 hành trình khứ hồi mỗi tuyến (chặng `out` có giá tổng, chặng `in` không giá, ghép theo thứ tự trang);
  - `collectors/trip.py` đã lưu `roundTripLegs` vào interim; `normalise.trip_route_products` bỏ qua;
  - kho `~/code/vsf/data-collection/data/interim/trip_flights.jsonl` có `roundTripLegs` ở 284/284 tuyến;
  - `data/products.jsonl`: 113 tuyến đều có `roundTripFrom`;
  - booking.com flights chỉ tìm `ONEWAY` và không chạy trong job.
- Giữ `level: flight`:
  - view `catalog.product_meta` và `domain/catalog/models.py` coi mọi level khác `route` của taxonomy flight là chuyến bay
    đặt được, không phải search unit; không phải sửa DDL / enum;
  - contract `ProductAttributes` có `additionalProperties: true`.
- **Không** ghi ngày về vào `app.cart_items.using_date_to` / `booking_items.using_date_to`: `postgres_booking._nights`
  đọc cột này ngược thành `nights` (chỉ dành cho khách sạn), giỏ sẽ hiện "số đêm" cho vé máy bay. Ngày về nằm trong sản
  phẩm (hành trình có ngày cố định), nên backend giỏ / đơn không phải sửa.

## Kiểm tra

- Chỉ viết tài liệu; không đổi code.
- Đã đọc:
  - `docs/prd/requirements.md` FR-CAT-01..03, `docs/prd/data-model.md` §3.1, `docs/prd/user-flow.md` §1.1 và §4.1;
  - `src/shared/contracts/schemas/catalog.yaml` (`level`), `schemas/booking.yaml` (giỏ);
  - `db/vota_schema.sql` (`catalog.product_meta`, `cart_items`, `booking_items`);
  - backend `domain/catalog/models.py`, `domain/booking/pricing.py`, `application/booking/cart.py`,
    `infrastructure/persistence/postgres_booking.py`;
  - `collectors/trip.py`, `normalise.trip_route_products`.

## Còn lại / rủi ro

- Chờ người yêu cầu chốt đề xuất và 4 mục "Cần chốt": khoá sản phẩm, giá một người lớn, `tripType: "oneWay"`, phạm vi
  hiển thị.
- Chốt xong: sửa PRD trước, rồi plan và code (AGENTS.md §8 bước 3).
- Chưa commit.
