# Đề xuất: điểm miễn phí gợi ý riêng, km tính cả sân bay, bản đồ theo thẻ khách sạn

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent, frontend

## Mục tiêu

Hội thoại Phú Quốc 3 ngày, đi từ Sài Gòn, đi 1 mình (LangSmith `nhat-10-7`, trace `01a11e8e-1f8a-7d70-b7fc-3f9b42e7d370`)
chỉ hiện một khách sạn. Người dùng muốn:
- tách điểm miễn phí khỏi lịch, gợi ý riêng 3–4 điểm phổ biến ở cuối;
- tính cả đường sân bay ↔ khách sạn vào km;
- thêm dấu "≈" và một dòng lưu ý cho số km;
- khi bấm thẻ khách sạn, bản đồ vẽ đường mọi ngày, chỉ hiện khách sạn đang xem, có hiệu ứng.

## File thay đổi

- `docs/prd/update/2026-10-09-diem-mien-phi-rieng-km-san-bay-ban-do.md` — thêm: đề xuất sửa AC-AGT-04 và
  `architecture.md` §3.

## Quyết định

- Nguyên nhân chỉ có một khách sạn: chạy lại `compose_plan` bằng state đầu vào của node `compose` trong trace. Venus vừa gần
  nhất (84,6 km) vừa rẻ nhất (1.918.000 đ); 6 khách sạn còn lại đều xa hơn và đắt hơn, nên `routing._options` không có
  phương án nào. Đúng luật hiện hành. Chẩn đoán đầu tiên trong phiên ("2 điểm chưa có giá chặn phương án") là sai: điểm
  không giá được `free_to_visit` tính 0 đ.
- Người dùng chốt qua câu hỏi trong phiên: tách hẳn điểm miễn phí ra khỏi lịch (không chỉ cộng km); chọn theo độ phổ biến;
  chặng sân bay tính vào việc chọn khách sạn. Đây là các lựa chọn cho nội dung đề xuất; bản thân đề xuất vẫn chờ chốt.
- Lệch PRD (AC-AGT-04, `architecture.md` §3) nên chỉ viết đề xuất, chưa sửa source (AGENTS.md §8).
- Đề xuất thay phần "điểm tự do vào lịch" của `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md`; các phần
  khác của đề xuất đó không đổi.

## Kiểm tra

- Không chạy test: chỉ thêm tài liệu. Số liệu trong đề xuất lấy từ trace LangSmith và từ việc chạy lại `compose_plan` bằng
  script tạm ngoài repo (không ghi gì vào repo).

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất. Sau khi chốt:
  1. Cập nhật PRD.
  2. Cập nhật contract.
  3. Sửa backend và frontend theo mục "Thay đổi source sau khi chốt".
- Bản đồ: chưa tái hiện lỗi "không vẽ hết đường" và "hiện nhiều khách sạn khi xem trước" trên trình duyệt. Đọc code thì lúc
  xem trước bản đồ chỉ nhận lịch của phương án đó, và đường chỉ vẽ cho ngày đang chọn, qua OSRM, không có đường thẳng dự
  phòng. Cần tái hiện trước khi sửa.

Bị thay thế bởi: 2026-10-09-loc-trung-km-san-bay-ngan-sach-the-ve.md
