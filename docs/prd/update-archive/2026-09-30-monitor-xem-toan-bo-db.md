# Monitor job cào: xem toàn bộ DB `vota`, có liên kết giữa các bảng

- Ngày: 2026-09-30
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-09-30 ("CHốt")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §2 NFR-SEC-01, NFR-SEC-02; `docs/prd/deployment-plan.md` §5 (giám sát);
  `docs/prd/data-model.md` (ranh giới quyền đọc `cdp.*`)
- Mã FR/NFR: mới — cần cấp mã (công cụ vận hành); liên quan NFR-SEC-01, NFR-SEC-02

## Lý do

Muốn biết DB staging đang có gì (vé đang bán, vé mô phỏng, đơn, user thử) hiện phải mở SSH tunnel rồi viết SQL. Monitor job cào
(`http://<IP VM>:8765`) chỉ xem được từng lượt chạy, không xem được DB đang sống. Người yêu cầu muốn xem **toàn bộ DB, có
móc nối giữa các bảng**, không giới hạn phạm vi; đăng nhập cho monitor sẽ thêm sau.

PRD hiện không cho phép:

- NFR-SEC-02: "Các phân hệ nghiệp vụ không được phép cấp quyền truy cập trực tiếp vào vùng dữ liệu nhạy cảm của CDP qua SQL.
  Mọi thao tác bắt buộc qua cổng dịch vụ (Port/Adapter pattern)." Monitor đọc `cdp.profiles`, `cdp.events` bằng SQL là
  trái câu này.
- `deployment-plan.md` §5 chỉ có health check và metrics, không có công cụ xem dữ liệu.

## Nội dung đề xuất

`docs/prd/requirements.md` NFR-SEC-02, sau gạch đầu dòng đầu tiên → thêm:

> - Ngoại lệ duy nhất: công cụ vận hành "xem DB" trên monitor job cào được **đọc** mọi bảng của database `vota` (`cdp`,
>   `catalog`, `app`) bằng SQL, chỉ trong transaction chỉ đọc; không ghi, không có ô nhập SQL tự do. Code nghiệp vụ vẫn chỉ đi
>   qua `CdpClient`.

`docs/prd/requirements.md` NFR-SEC-01 → thêm:

> Công cụ xem DB luôn che các cột bí mật: tên cột chứa `password`, `token`, `secret` hoặc `hash` (hiện có
> `app.users.password_hash`, `app.refresh_tokens.token_hash`) hiện "(ẩn)".

`docs/prd/deployment-plan.md` §5 → thêm mục:

> - **Xem DB trên monitor job cào (tab "DB"):** danh sách schema / bảng kèm số dòng; xem từng bảng có phân trang, lọc, sắp xếp;
>   xem một dòng kèm **liên kết** theo khoá ngoại: bấm sang dòng được trỏ tới (vd. `booking_items.product_id` → sản phẩm) và
>   xem các dòng trỏ về nó (vd. sản phẩm → `booking_items`, `cart_items`, `combo_items`; hồ sơ CDP → `events`, `users`,
>   `bookings`). Quan hệ lấy từ khoá ngoại khai báo trong PostgreSQL (tự theo migration mới), cộng hai quan hệ theo quy ước
>   không có khoá ngoại: `attributes.parentProductId` (vé / phòng → tuyến / khách sạn) và `demo:business:<sourceRef>` (vé mô
>   phỏng → vé gốc). Dùng kết nối DB sẵn có của job, mỗi yêu cầu trong transaction chỉ đọc, `statement_timeout` 5 giây.
>   Chỉ database `vota`; database `insider` không có (monitor không có kết nối tới nó).

## Ảnh hưởng

- Có lợi: xem được mọi dữ liệu staging từ trình duyệt, không cần tunnel hay SQL.
- **Rủi ro — cần biết trước khi chốt:** monitor hiện **public, chưa có đăng nhập**. Chốt đề xuất này thì ai có link đều xem
  được email, số điện thoại, tên liên hệ trong đơn, lịch sử chat với trợ lý và toàn bộ hành vi CDP của mọi user trên staging.
  Người yêu cầu chấp nhận và sẽ thêm đăng nhập sau. Trong lúc chờ, nên giới hạn IP nguồn trong rule firewall cổng 8765
  (`--source-ranges`).
- Kết nối của job là tài khoản seed (có quyền ghi); an toàn nhờ transaction chỉ đọc và chỉ có truy vấn cố định, không nhờ quyền
  của role.

## Thay đổi source sau khi chốt

- `src/data_collection/monitor.py`: các endpoint `/api/dbx/tables`, `/api/dbx/rows`, `/api/dbx/row` (đọc metadata
  `information_schema` / `pg_constraint`, truy vấn có tham số, tên bảng / cột chỉ nhận từ metadata).
- `src/data_collection/monitor_ui/index.html`: tab "DB".
- Test `src/data_collection/tests/`: che cột bí mật, chỉ đọc (ghi bị từ chối), tên bảng / cột lạ bị từ chối, liên kết hai chiều;
  test PostgreSQL trên database nháp.
- `docs/guide/trien-khai-job-cao-du-lieu.md` (mục monitor), `src/data_collection/README.md`.
