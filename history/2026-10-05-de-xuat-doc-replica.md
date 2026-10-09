# Đề xuất định tuyến đọc replica

- Ngày: 2026-10-05
- Tác giả: người dùng / Codex
- Nhánh: bench_search_recomSys
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Rà yêu cầu chuyển đọc sang replica, ghi primary, đồng thời bảo toàn ranh giới CDP và tính nhất quán nghiệp vụ.

## File thay đổi

- `docs/prd/update/2026-10-05-tach-ket-noi-doc-replica.md` — thêm đề xuất chờ chốt.
- `history/2026-10-05-de-xuat-doc-replica.md` — thêm lịch sử task.

## Quyết định

- Đối chiếu PRD README, architecture §2, deployment-plan và yêu cầu NFR/AC; kiểm Settings wiring trong main.py và kết nối crawler. Chưa có cấu hình replica trong các vị trí đã tìm.
- PRD chưa quy định định tuyến replica, nên theo AGENTS.md §8 tạo đề xuất trước khi sửa source. Không sửa PRD, code, env hay dữ liệu DB.
- Không chuyển toàn bộ SELECT: đọc trong giao dịch và đọc ngay sau ghi cần primary; kết nối app và CDP vẫn tách role.
- Giữ nguyên các thay đổi đang có của người dùng trong working tree.

## Kiểm tra

- Tìm kiếm bằng rg các kết nối DB trong PRD, backend và crawler; xác định các điểm wiring ở main.py.
- Thử mở SSH tunnel replica được người dùng cung cấp: exit 255, Connection refused ở cổng 22 trước xác thực; chưa kết nối PostgreSQL.
- Đối chiếu tài liệu PostgreSQL 16 về hot standby và streaming replication: replica có thể trễ; promote/failover là bước riêng.
- Chưa chạy test code/DB verify vì không thay source hoặc dữ liệu; chưa kiểm chứng replica đang hoạt động.

## Còn lại / rủi ro

- Người dùng chốt đề xuất; sau đó cập nhật PRD trước triển khai theo AGENTS.md §8 và đọc đủ tài liệu từng workstream trước code.
- Cần SSH replica hoạt động và kiểm tra role, recovery, replication lag. Primary cũ cũng chưa kết nối được trong task làm giàu CDP.
- Công việc làm giàu lịch sử CDP còn chưa hoàn thành; replica chỉ giúp đọc, không thay thế endpoint primary để ghi.
