# Đề xuất khách sạn cho đoàn đông: lọc theo một phòng, tính tiền theo số phòng

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: agent

## Mục tiêu

Lượt "bao nhieu cungx dudoc" (LangSmith `nhat-10-7`, 7 ngày Phú Quốc, 10 người lớn) chỉ hiện một khách sạn. Trace:
search khách sạn gửi `travelContext.guests = {adults: 10}`, contract hiểu là sức chứa một phòng nên trả `total: 0`;
compose chỉ còn 2 khách sạn từ Recommendation. Người dùng chọn hướng chia đoàn thành nhiều phòng, không cố định số
người mỗi phòng, và nhân tiền khách sạn theo số phòng.

## File thay đổi

- `docs/prd/update/2026-10-09-khach-san-theo-so-phong-cho-doan-dong.md` — đề xuất mới, `chờ chốt`.

## Quyết định

- Số phòng lấy từ `attributes.priceAdults` của từng khách sạn (2.728/2.782 khách sạn có, đều = 2 trên DB local
  09/10/2026), không hằng số trong code; lọc search theo `ceil(tổng khách / 9)` theo trần 9 phòng của FR-BKG-08.
- Nhân tiền theo số phòng lệch AC-AGT-04 nên đi qua đề xuất (AGENTS.md §8); chưa sửa source.

## Kiểm tra

- Số liệu catalog: query `cdp.products` ⨝ `catalog.product_meta` trên Postgres local — 9.487/9.854 hạng phòng có
  `maxOccupancy`; trung vị sức chứa phòng lớn nhất của 2.442 khách sạn = 2.
- Không có thay đổi code nên không chạy test.

## Việc còn lại

- Chờ người dùng chốt đề xuất (hai điểm mở: cách lọc cho gia đình nhỏ, trẻ em không tính phòng), rồi cập nhật PRD,
  contract (field số phòng), code, test, docs theo mục "Thay đổi source sau khi chốt".
