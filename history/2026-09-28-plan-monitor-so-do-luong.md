# Plan monitor: hiển thị mỗi lượt thành sơ đồ luồng

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: docs (data)

## Mục tiêu

Người yêu cầu thấy monitor rối: mỗi lượt có quá nhiều tab, khó thấy lỗi ở đâu, khó so các lượt, trang Tổng quan dài.
Người yêu cầu chọn bố cục "sơ đồ luồng một lượt" và yêu cầu viết plan trước khi làm.

## File thay đổi

- `docs/plan/2026-09-28-monitor-so-do-luong.md` — thêm: plan 5 checkpoint:
  - UI1: API sơ đồ và dải bước;
  - UI2: sơ đồ và panel thay cho 9 tab;
  - UI3: dải lỗi, chọn sẵn ô, đường dẫn;
  - UI4: Lịch sử có dải bước;
  - UI5: Tổng quan gọn, trang Hệ thống.

## Quyết định

- Bố cục do người yêu cầu chọn: sơ đồ luồng một lượt (giống Graph view của Airflow). Agent thêm dải bước ở trang
  Lịch sử (giống Grid view) để giải quyết "khó so các lượt", vì sơ đồ chỉ hiện một lượt.
- Sơ đồ tính ở server (`FreshMonitor.graph`) để test được bằng Python; UI không cần biết tên bước.
- Chỉ đọc `run.json` / `steps.json`; không đổi job, API cũ giữ nguyên.
- Làm plan này trước CP6–CP8 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` (theo đề xuất agent,
  người yêu cầu đồng ý).
- Các điểm agent tự đề xuất, người yêu cầu có thể đổi:
  - gộp trang Khách sạn Trip vào trang Hệ thống;
  - thanh trên mới gồm Tổng quan · Lịch sử · Hệ thống · Cấu hình;
  - quy tắc chọn sẵn ô khi mở lượt;
  - tách JS khi `index.html` vượt khoảng 600 dòng.

## Kiểm tra

- Chỉ viết tài liệu; không chạy test. Đã đối chiếu tên bước với `run.json` của các lượt trong `data/local_crawl/runs`,
  với `SOURCES` trong `monitor.py` và với danh sách route API.

## Còn lại / rủi ro

- UI1–UI5 chưa làm; chờ người yêu cầu duyệt plan.
