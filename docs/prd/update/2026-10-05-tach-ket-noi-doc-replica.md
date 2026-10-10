# Tách kết nối đọc replica và ghi primary

- Ngày: 2026-10-05
- Người đề xuất: người dùng / Codex
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §2; `docs/prd/deployment-plan.md` §1, §2, §5, §6
- Mã FR/NFR: NFR-PERF-01, NFR-REL-02, NFR-SEC-02; bảo toàn AC-BKG-01–04, AC-REC-02, AC-SEC-01

## Lý do

Người dùng thông báo hạ tầng có PostgreSQL primary/replica và yêu cầu chuyển tác vụ đọc sang replica. PRD hiện chỉ có DATABASE_URL, CDP_DATABASE_URL và SEED_DATABASE_URL; chưa quy định độ trễ đồng bộ hay định tuyến đọc. Chuyển mọi SELECT sang replica có thể khiến đăng nhập, giỏ hàng, xác nhận thanh toán hoặc gợi ý ngay sau mua đọc dữ liệu cũ.

Chưa xác minh hạ tầng: thử SSH tới host replica được cung cấp ngày 05/10 trả Connection refused tại cổng 22, trước xác thực. Chưa kiểm tra pg_is_in_recovery(), quyền role hoặc replication lag. Tài liệu này không chứa thông tin đăng nhập.

## Nội dung đề xuất

### architecture.md §2 — ranh giới kết nối

Hiện tại: “Kết nối DATABASE_URL (cho app) chỉ SELECT được cdp.products … Adapter LocalCdpClient phải sử dụng một chuỗi kết nối riêng biệt CDP_DATABASE_URL với tài khoản cdp_writer.”

Thay bằng quy định giữ nguyên ranh giới role và bổ sung:

- DATABASE_URL và CDP_DATABASE_URL trỏ primary cho thao tác ghi và đọc cần nhất quán với giao dịch.
- REPLICA_DATABASE_URL dành cho đọc catalog và truy vấn tổng hợp chấp nhận độ trễ đồng bộ, giữ quyền app như DATABASE_URL; không được đọc cdp.events/profiles.
- CDP_REPLICA_DATABASE_URL dành riêng adapter CDP đọc lịch sử phục vụ RecSys, dùng role cdp_reader. Không tái sử dụng tài khoản có quyền rộng cho backend.
- Không cấu hình replica thì dùng primary tương ứng để tương thích local. Khi đã cấu hình replica nhưng kết nối lỗi, báo lỗi theo cơ chế hiện có; không tự chuyển vai trò DB hay âm thầm đổi đích.
- Đăng nhập, token, giỏ hàng, booking, thanh toán, bù trừ CDP và hội thoại tiếp tục đọc/ghi primary. Gợi ý cần phản ánh ngay purchase/cancel cũng đọc primary; chỉ chuyển lịch sử RecSys sang replica khi đường gọi xác định được yêu cầu nhất quán.
- Agent tiếp tục gọi các port/tool của backend, không tự mở kết nối DB.

### deployment-plan.md §1–2 — topology và cấu hình

Hiện tại: staging là “PostgreSQL Cloud”; bảng cấu hình chỉ nêu kết nối chính, CDP và seed.

Thay bằng: staging gồm primary và read replica. Bổ sung hai biến replica nêu trên với role tách biệt. Crawler/seed/migration ghi primary; các truy vấn phục vụ quyết định cập nhật hoặc kiểm tra ngay sau nạp cũng đọc primary. Job index nối tiếp lần nạp phải thấy catalog vừa ghi nên giữ primary; index độc lập và báo cáo có thể đọc replica. Cấu hình mẫu chỉ dùng placeholder, không chứa mật khẩu. Địa chỉ loopback của tunnel trên host không dùng nguyên dạng bên trong container.

### deployment-plan.md §5–6 — kiểm tra và sự cố

Hiện tại: health checks kiểm kết nối PostgreSQL và CDP; chưa mô tả replica/failover.

Bổ sung: kiểm tra riêng primary/replica được cấu hình; ghi nhận vai trò qua pg_is_in_recovery(), tình trạng WAL receive/replay và quyền SELECT của từng role. Không suy ra lag bằng thời gian từ transaction cuối đơn lẻ khi primary không có ghi mới.

Có replica không đồng nghĩa tự động failover. Khi primary hỏng, phần đọc từ replica có thể tiếp tục nếu các phụ thuộc khác hoạt động; phần ghi chờ vận hành cô lập primary cũ, quyết định promote và cập nhật endpoint. Triển khai tự động failover và cam kết RPO/RTO chưa thuộc thay đổi này.

## Thay đổi source sau khi chốt

- `src/backend/app/core/`: Settings cho URL replica tùy chọn, không log DSN.
- `src/backend/app/main.py`: nối đúng URL vào adapter theo nghiệp vụ; không phân loại chỉ dựa vào SELECT.
- `src/backend/app/infrastructure/persistence/`, `infrastructure/cdp/`, `infrastructure/vectors/`: rà transaction và đường đọc catalog/lịch sử/index.
- `src/data_collection/fresh_catalog.py`, `fresh_settings.py`, `fresh-catalog.env.example`: tách đọc độc lập với đọc trong quy trình nạp/index; giữ ghi primary.
- Cấu hình compose/env mẫu, README backend và tài liệu tích hợp CDP/database liên quan.
- Test định tuyến, thiếu replica, replica lỗi, role isolation, và đọc ngay sau ghi cho booking/auth/CDP. Không thay schema hay API công khai.

## Liên hệ công việc làm giàu CDP

Rà lịch sử hành vi có thể đọc replica sau khi xác minh trạng thái đồng bộ. Bổ sung dữ liệu chỉ ghi primary; đo lại trên snapshot đã đóng băng sau khi replica bắt kịp. Chưa có thay đổi dữ liệu CDP trong đề xuất này.
