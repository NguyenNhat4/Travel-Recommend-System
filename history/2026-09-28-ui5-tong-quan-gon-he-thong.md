# UI5: Tổng quan gọn, nút chạy lượt trên thanh trên, trang Hệ thống

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

UI5 của `docs/plan/2026-09-28-monitor-so-do-luong.md`: Tổng quan vừa một màn hình. Chỉ chuyển chỗ, không bỏ thông tin nào.

## File thay đổi

- `src/data_collection/monitor_ui/index.html` — sửa:
  - thanh trên: Tổng quan · Lịch sử · Hệ thống · Cấu hình;
  - nút chạy lượt (4 chế độ) và Dừng luôn hiện, trạng thái lấy từ `/api/live` mỗi 5 giây ở mọi trang; hỏi xác nhận trước khi chạy;
  - Tổng quan:
    - thẻ "Hiện tại" với sơ đồ thu nhỏ của lượt đang chạy hoặc lượt gần nhất (bấm ô → mở lượt ở ô đó), kèm dải lỗi;
    - lượt theo lịch kế tiếp, ngày cào lớn gần nhất;
    - "Cảnh báo và SLA" và bảng cảnh báo (CP7, CP8);
  - trang Hệ thống: nơi ghi dữ liệu, biến kết nối, dung lượng dữ liệu giữ lại, log runner, Khách sạn Trip (trước là mục riêng);
  - bỏ `runsTable` (thay bằng bảng Lịch sử của UI4);
  - `#page=hotels` cũ vẫn mở trang Hệ thống.
- `src/data_collection/README.md` — sửa: ghi giao diện mới, chạy lại từ bước lỗi, chạy liên tục, cảnh báo / SLA; thêm lệnh
  `run resume`.
- `docs/plan/2026-09-28-monitor-so-do-luong.md` — sửa: tiến độ.

## Quyết định

- Đề xuất trong plan (gộp Khách sạn Trip vào Hệ thống; thanh trên mới) được áp dụng vì người yêu cầu yêu cầu làm hết rồi review.
- **Thêm so với plan:** hỏi xác nhận trước khi chạy lượt, vì nút giờ luôn hiện ở mọi trang nên dễ bấm nhầm.
- "Lượt gần nhất" trên Tổng quan cũ được thay bằng trang Lịch sử; bốn ô số cũ: "Hiện tại" → thẻ Hiện tại, "Lượt theo lịch" giữ,
  "Khách sạn Trip" → tiêu đề thẻ ở Hệ thống, "Dữ liệu giữ lại" → Hệ thống.

## Kiểm tra

- `pytest tests` (env `vsf`): **466 passed, 5 skipped**. `git diff --check`: sạch.
- Trình duyệt:
  - monitor thử 8798 (`local_crawl_demo`): Tổng quan có sơ đồ thu nhỏ lượt gần nhất + dải lỗi; bấm ô Index → mở lượt ở ô Index;
    Hệ thống đủ 5 thẻ, `#page=system`;
  - monitor thử 8797 với lượt giả đang chạy (scratchpad, không cào thật): 4 nút chạy bị tắt, Dừng bật, thanh trên hiện
    "Đang chạy · full-…4242"; sơ đồ thu nhỏ 17 ô;
  - 375 px: Tổng quan, Lịch sử, Hệ thống không cuộn ngang;
  - script bấm mọi ô × mọi tab con của 7 lượt demo + 3 nút cấp lượt + 4 trang: không exception. Lỗi 400 trong console chỉ từ
    `/api/normalise|products|db|embed` của lượt chưa có file tương ứng; panel báo lỗi đó (như trước).
- Monitor thử và lượt giả đã tắt; monitor 8765 của người yêu cầu không bị động tới.

## Còn lại / rủi ro

- `index.html` 487 dòng (ngưỡng tách JS trong plan ~600).
- Chưa commit.
