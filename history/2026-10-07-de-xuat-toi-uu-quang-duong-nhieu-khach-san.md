# Đề xuất: tối ưu tổng quãng đường, cho phép đổi khách sạn giữa chuyến

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: history/2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md

## Mục tiêu

Người dùng muốn lịch trình tối ưu đúng quãng đường phải đi mỗi ngày:
- ngày 1: điểm sáng → điểm chiều → khách sạn;
- các ngày sau: khách sạn đêm trước → các điểm → khách sạn đêm đó.

Muốn vậy thì phải thay luật kinh nghiệm của AC-AGT-04 bằng hàm mục tiêu, và cho phép nhiều khách sạn trong một chuyến.
Đây là thay đổi lệch PRD và lệch contract (`stay` chỉ có một khách sạn), nên theo AGENTS.md §8 phải có đề xuất được chốt
trước.

## File thay đổi

- `docs/prd/update/2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md` — thêm, trạng thái `chờ chốt`.

## Quyết định

- **Ngày 1 và ngày cuối không tính chặng sân bay.** Đây đúng là định nghĩa người dùng đưa ra, và catalog cũng chưa có
  toạ độ sân bay.
- **Tối ưu chính xác thay vì heuristic.** Bài toán nhỏ (≤ 7 ngày, ≤ 2 điểm/ngày, khoảng 10 ứng viên mỗi loại):
  - ghép cặp giải bằng quy hoạch động trên tập con;
  - chuỗi khách sạn giải bằng quy hoạch động theo ngày.
- **Các tham số đổi khách sạn do agent đề xuất, chờ người dùng chốt:**
  - chuyến từ 4 ngày;
  - tối đa 1 lần đổi;
  - mỗi khách sạn ít nhất 2 đêm;
  - phạt 15 km mỗi lần đổi.

  Không có phạt thì thuật toán sẽ đổi khách sạn gần như mỗi đêm.
- **Số điểm được xếp cố định bằng sức chứa của lịch.** Nếu không cố định, cách giảm km dễ nhất là bỏ bớt điểm.
- **Contract chỉ cộng thêm `stays[]`, giữ `stay`**, để không phá client cũ (AGENTS.md §3).

## Kiểm tra

- Không chạy lệnh nào: thay đổi chỉ là tài liệu đề xuất.

## Còn lại / rủi ro

- **Đang dừng ở bước 1 của AGENTS.md §8: chờ người dùng chốt đề xuất và các tham số.**
- Thay đổi của AC-AGT-04 bản đầu (history `2026-10-07-lich-trinh-it-di-chuyen.md`) vẫn chưa commit. Đề xuất này xây trên
  bản đó.
