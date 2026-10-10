# Đề xuất: cân giữa quãng đường và tiền bằng cách quy đổi km ra tiền

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: history/2026-10-08-khach-san-theo-ngan-sach-va-phuong-an-khac.md

## Mục tiêu

Đo lường cho thấy luật "chênh dưới 2 km thì so giá" của AC-AGT-04 chọn khách sạn đắt gấp nhiều lần (trung vị 1,8–5,9 lần,
tối đa 69 lần) chỉ để bớt vài km. Người dùng chọn hướng quy đổi km ra tiền. Đây là thay đổi AC-AGT-04 nên phải có đề xuất
được chốt (AGENTS.md §8).

## File thay đổi

- `docs/prd/update/2026-10-07-quy-doi-km-ra-tien.md` — thêm, trạng thái `chờ chốt`.

## Quyết định

- **Đề xuất đơn giá 200.000 ₫/km**, dựa trên mô phỏng trên catalog staging ngày 07/10/2026 (nạp về Postgres local; seed 42;
  30 mẫu mỗi ô):
  - ở 200k: km tăng 5–40%, tiền khách sạn giảm 47–80% so với luật hiện tại;
  - ở 10–50k (giá taxi): gần như luôn lấy khách sạn rẻ nhất, km tăng gấp 2–3 lần.
- Danh sách khách sạn đem ra so có thêm 3 khách sạn rẻ nhất; nếu không, khách sạn rẻ ở xa không bao giờ được xét.
- Mô phỏng dùng một bản sửa thử của `routing.py` trong scratchpad, không sửa code trong repo.

## Kiểm tra

- Mô phỏng tất định, số liệu đầy đủ ghi trong đề xuất. Chưa chạy test vì chưa sửa code.

## Còn lại / rủi ro

- **Chờ người dùng chốt đề xuất và đơn giá.**
- Huế và Vũng Tàu không thay đổi ở mọi mức, vì gần như mọi điểm tham quan ở đó mang toạ độ tâm thành phố.
