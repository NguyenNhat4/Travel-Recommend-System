# Monitor: sơ đồ quan hệ DB, luồng dữ liệu web / agent và hoạt động realtime

- Ngày: 2026-09-30
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-09-30 ("Tôi muốn dùng cách đo của stageMs, 3, đã ok, TÔi muốn làm tiếp trên nhánh test/crawl này luôn"; "làm giai đoạn 2"). Giai đoạn 2 đo ở tầng use case qua port (agent gọi trong tiến trình, không qua HTTP) và dùng `StageTimer`/`stageMs` của nhánh `feat/search-stage-timing`; người phụ trách backend đã đồng ý (theo người yêu cầu).
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §5 (giám sát); giai đoạn 2 thêm `docs/prd/architecture.md` §2 (backend
  xuất sự kiện yêu cầu)
- Mã FR/NFR: mới — cần cấp mã (công cụ vận hành); liên quan NFR-SEC-01, NFR-SEC-02

## Lý do

Người yêu cầu: "monitor trạng thái của DB, có được sơ đồ các mối quan hệ của các bảng, dễ nhìn, trực quan, data cho agent và
web sẽ lấy từ đâu, có fetch được trạng thái lúc nó gọi không... tôi muốn realtime".

Tab "DB" (đã áp dụng, `update-archive/2026-09-30-monitor-xem-toan-bo-db.md`) chỉ xem dữ liệu dạng bảng, không có sơ đồ,
không có luồng dữ liệu, không realtime.

Hiện trạng đã kiểm trong code (30/09/2026):

- Backend nạp catalog (`cdp.products`, `catalog.product_meta`) vào bộ nhớ, làm mới mỗi `CATALOG_REFRESH_SECONDS` (900 giây).
  Web và agent xem / tìm sản phẩm **không truy vấn DB lúc gọi**; tìm ngữ nghĩa đi Weaviate `Product`.
- Backend ghi DB khi: giỏ (`app.carts`, `cart_items`), đơn / thanh toán (`app.bookings`, `booking_items`, `payments`), đăng
  nhập (`app.users`, `refresh_tokens`, `login_attempts`), hội thoại agent (`app.conversations`, `conversation_messages`), sự
  kiện CDP qua `CdpClient` (`cdp.events`, `cdp.profiles`).
- `app.search_logs`, `app.recommendation_logs` có trong DDL nhưng **không nơi nào ghi**.
- PRD `deployment-plan.md` §5 yêu cầu `GET /metrics` (độ trễ API, lỗi 5xx, thời gian trợ lý) — backend **chưa có**.

## Nội dung đề xuất

`docs/prd/deployment-plan.md` §5, sau mục "Xem DB trên monitor" → thêm:

> - **Sơ đồ và hoạt động DB realtime trên monitor (tab "DB", giai đoạn 1 — không đổi backend):**
>   - *Sơ đồ quan hệ:* mỗi bảng / view của `cdp`, `catalog`, `app` là một ô (nhóm theo schema) kèm số dòng; đường nối là khoá
>     ngoại (nét liền) và quan hệ quy ước (nét đứt: sản phẩm cha–con, vé mô phỏng–vé gốc); bấm ô mở bảng.
>   - *Luồng dữ liệu:* sơ đồ ai đọc / ghi bảng nào — job cào → `cdp.products`, `catalog.combo_items`; backend nạp catalog vào
>     bộ nhớ (chu kỳ 15 phút) → web / agent; agent → công cụ backend → catalog trong bộ nhớ + Weaviate; web / agent → giỏ,
>     đơn, thanh toán, đăng nhập, hội thoại (`app.*`); sự kiện hành vi qua `CdpClient` → `cdp.events`, `cdp.profiles`. Bảng
>     ánh xạ đọc / ghi giữ trong một file khai báo của monitor, đối chiếu code backend.
>   - *Realtime (làm mới 2 giây, server-sent events):* số dòng đọc / thêm / sửa / xoá mỗi giây của từng bảng (chênh lệch
>     `pg_stat_user_tables`), tô lên sơ đồ; kết nối đang mở theo role (`pg_stat_activity`: backend, `CdpClient`, job cào,
>     monitor), trạng thái và câu SQL đang chạy (cắt 200 ký tự, tham số dạng `$1`); dòng mới nhất của các bảng ghi nhiều
>     (`cdp.events`, `app.bookings`, `app.cart_items`, `app.conversation_messages`), che cột bí mật như tab DB.
>   - Giới hạn: vì catalog nằm trong bộ nhớ backend, **lượt xem / tìm sản phẩm của web và agent không hiện** ở giai đoạn 1;
>     chỉ thấy các thao tác ghi và lần nạp catalog.
> - **Giai đoạn 2 (đổi backend):** backend có `GET /metrics` đúng mục này (độ trễ, lỗi, thời gian trợ lý theo route) và một
>   luồng sự kiện yêu cầu nội bộ (route, người gọi web / agent, số sản phẩm trả về, thời gian, không có dữ liệu cá nhân hay
>   bí mật); monitor đọc để hiện **từng lần gọi** của web / agent realtime trên sơ đồ luồng dữ liệu.

## Ảnh hưởng

- Có lợi: nhìn một trang thấy cấu trúc DB, ai dùng bảng nào, và DB đang được đọc / ghi ra sao ngay lúc đó.
- Giai đoạn 1 chỉ đổi monitor (đọc thống kê của PostgreSQL, cần quyền xem `pg_stat_activity` đầy đủ — tài khoản seed của
  job có). Giai đoạn 2 đổi backend (workstream Backend): cần người phụ trách backend đồng ý; không đổi contract public nếu
  endpoint chỉ nội bộ.
- Rủi ro: monitor public chưa đăng nhập, nay thêm câu SQL đang chạy và dòng mới nhất (email, tin nhắn) — cùng rủi ro tab DB.

## Thay đổi source sau khi chốt

Giai đoạn 1:

- `src/data_collection/db_browser.py`: sơ đồ (bảng, khoá ngoại, quy ước, số dòng), ảnh chụp hoạt động (`pg_stat_user_tables`,
  `pg_stat_activity`, dòng mới nhất).
- `src/data_collection/db_lineage.json` (mới): khai báo ai đọc / ghi bảng nào.
- `src/data_collection/monitor.py`: `/api/dbx/graph`, `/api/dbx/activity/stream` (SSE).
- `src/data_collection/monitor_ui/index.html`: tab DB thêm "Sơ đồ", "Luồng dữ liệu", "Realtime" (SVG, không thư viện ngoài).
- Test: đơn vị + PostgreSQL nháp (chênh lệch thống kê khi ghi thử, SSE, che cột bí mật).
- `docs/guide/trien-khai-job-cao-du-lieu.md`.

Giai đoạn 2: `src/backend/app` (middleware đo, `/metrics`, luồng sự kiện), test backend, `docs/spec/hop-dong-tich-hop-backend.md`.
