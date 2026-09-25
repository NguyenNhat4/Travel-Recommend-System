# Sửa `catalog.products` thành `cdp.products` trong PRD

- Ngày: 2026-09-24
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-24 (áp dụng cùng ngày: PRD và sơ đồ spec booking)
- PRD bị ảnh hưởng: `docs/prd/data-model.md` §1 (sơ đồ lưu trữ), §2.2 (entity `APP_BOOKING_ITEMS`); `docs/prd/test-plan.md` §2.4
- Mã FR/NFR: NFR-REL-01, FR-BKG-01…04

## Lý do

PRD đang tự mâu thuẫn về nơi đặt bảng sản phẩm:

- `data-model.md` §2.1 (ERD), `architecture.md` §2 (Quy tắc phụ thuộc, mục 3) và `deployment-plan.md` §2 đều ghi bảng sản phẩm là `cdp.products`.
- Ba chỗ khác lại nhắc tới `catalog.products`: sơ đồ ASCII ở `data-model.md` §1, chú thích cột `product_id` của `APP_BOOKING_ITEMS` ở `data-model.md` §2.2, và tiêu chí Grounding Rate ở `test-plan.md` §2.4.

DDL (`db/vota_schema.sql`) không có `catalog.products`. Bảng sản phẩm là `cdp.products`, mirror đúng 13 trường của CDP thật (handbook §6). Schema `catalog` chỉ chứa dữ liệu dựng lại được từ bảng đó: view `product_meta`, `product_parents`, `search_rows` và bảng `combo_items`. Code và bộ đánh giá đều đọc `cdp.products`:

- `src/backend/app/infrastructure/persistence/postgres_catalog.py`
- `src/backend/app/infrastructure/vectors/postgres_store.py`
- `src/evaluation/agent/grounding.py`

Nếu để nguyên, người đọc PRD sẽ tìm một bảng không tồn tại, và tiêu chí grounding trỏ vào bảng không kiểm được. Đề xuất này chỉ sửa chữ trong PRD cho khớp ERD §2.1 và DDL. Không đổi thiết kế, DDL hay hành vi.

## Nội dung đề xuất

**1. `data-model.md` §1, sơ đồ lưu trữ:** chuyển `products` từ cột `catalog` sang cột `cdp`. Cột `app` giữ nguyên.

Hiện tại:

```
|  [Schema: cdp]           [Schema: catalog]           [Schema: app]      |
|  - profiles              - products (view/table)     - users            |
|  - events                - product_meta (view)       - bookings         |
|                          - combo_items               - booking_items    |
```

Thay bằng:

```
|  [Schema: cdp]           [Schema: catalog]           [Schema: app]      |
|  - products              - product_meta (view)       - users            |
|  - profiles              - combo_items               - bookings         |
|  - events                                            - booking_items    |
```

**2. `data-model.md` §2.2, entity `APP_BOOKING_ITEMS`:**

- Hiện tại: `string product_id "Tham chiếu logic tới catalog.products"`
- Thay bằng: `string product_id "Tham chiếu logic tới cdp.products"`

**3. `test-plan.md` §2.4, Grounding Rate:**

- Hiện tại: "Tất cả các ID sản phẩm được render thành thẻ đặt chỗ phải tồn tại thực trong bảng `catalog.products`."
- Thay bằng: "Tất cả các ID sản phẩm được render thành thẻ đặt chỗ phải tồn tại thực trong bảng `cdp.products`."

## Thay đổi source sau khi chốt

Sửa các sơ đồ trong `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` có nhắc tới bảng sản phẩm:

- **§3, sơ đồ thành phần.** Nút `P` hiện chỉ liệt kê bảng `app.*`, còn nút CDP duy nhất ghi "chỉ qua CdpClient". Người đọc dễ hiểu nhầm rằng Backend đọc sản phẩm qua `CdpClient`, trong khi thực tế Backend đọc bằng chính kết nối `DATABASE_URL` (role `vota_app` được SELECT `cdp.products`, `architecture.md` §2).
  - Hiện tại: `P[("🗄️ Postgres app.*<br/>carts, bookings,<br/>booking_items, payments")]`
  - Thay bằng: `P[("🗄️ Postgres app.*<br/>carts, bookings,<br/>booking_items, payments<br/>+ đọc cdp.products")]`
- **§6.1, sequence đặt chỗ thành công.** Participant `P` là "Postgres app" nhưng bước đọc ghi "catalog", nên dễ hiểu là catalog nằm trong `app`.
  - Hiện tại: `F->>P: Đọc giỏ, catalog, đơn PENDING_PAYMENT của user`
  - Thay bằng: `F->>P: Đọc giỏ, đơn PENDING_PAYMENT của user (app.*)<br/>và sản phẩm (cdp.products, chỉ đọc)`
- **§6.2, activity tạo đơn giữ chỗ:**
  - Nút `D2`: `D2[("catalog.products")]` → `D2[("cdp.products<br/>chỉ đọc")]`.
  - Thêm hai cạnh còn thiếu tới `D2`:
    - `F6 -.-> D2`: bước kiểm `usingDate` đọc `available_from/to` của sản phẩm.
    - `F7 -.-> D2`: bước "Tính tổng từ catalog" đọc giá sản phẩm.

Sơ đồ ở các mục 7–9 của spec booking chỉ đọc/ghi `app.*` và `cdp.events`, không đụng bảng sản phẩm, nên giữ nguyên. Chữ "catalog" trong văn xuôi của spec (ví dụ "Backend tính từ catalog") là khái niệm danh mục sản phẩm, không phải tên schema, nên cũng giữ nguyên.

Đã soát `docs/spec/auth/so-do-luong-xac-thuc.md`: các sơ đồ chỉ nhắc `app.users`, `app.refresh_tokens`, `app.login_attempts`, `app.mfa_*`, `app.carts`, `app.bookings`, `cdp.profiles` và Redis, không có bảng sản phẩm. Không cần sửa.

Code, contract, DDL: không cần sửa, vì đã dùng `cdp.products`.

## Ngoài phạm vi đề xuất này

- Trong DDL bản clone, `app.booking_items.product_id` và `app.cart_items.product_id` là **FK thật** tới `cdp.products`. Theo `docs/spec/DATABASE_SCHEMA.md` §5, FK này được giữ để bắt lỗi sớm và sẽ bỏ khi lên CDP production. Chú thích "tham chiếu logic" ở mục 2 đúng với production nhưng chưa đúng với bản clone. Tiêu đề quy tắc ở `data-model.md` §1 ("Không tạo Khóa Ngoại chéo giữa các Schema độc lập") cũng rộng hơn nội dung của nó, vì nội dung chỉ nói về `cdp.events.event_id`. Có làm rõ hai chỗ này hay không thì cần một đề xuất riêng.
- Sơ đồ §1 còn lệch với DDL ở các chỗ khác và đề xuất này không sửa:
  - Cột `catalog` thiếu `product_parents` và `search_rows`.
  - Cột `app` ghi `messages`, còn DDL dùng `conversation_messages`.
  - Cột `app` thiếu `carts`, `cart_items`, `itineraries`, `recommendation_logs` và `search_logs`.
