# UI4: trang Lịch sử có dải trạng thái từng bước

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

UI4 của `docs/plan/2026-09-28-monitor-so-do-luong.md`: so được các lượt trên một màn hình, thấy lượt bất thường mà không mở lượt nào.

## File thay đổi

- `src/data_collection/monitor.py` — sửa: thêm `graph_strip_detail`; `/api/runs` trả thêm `stripDetail` (từng ô: nhãn, trạng
  thái; bỏ ô không thuộc lượt / đã tắt).
- `src/data_collection/monitor_ui/index.html` — sửa:
  - trang Lịch sử (`historyPage`): mỗi lượt một dòng với dải 7 ô màu, thời gian, số sản phẩm, chênh lệch so với lượt trước
    cùng chế độ, lọc theo chế độ / trạng thái, chú thích màu;
  - di chuột lên ô hiện từng nguồn; bấm ô thì mở lượt, chọn ô xấu nhất của cột đó (`openRun(..., col)`).
- `src/data_collection/tests/test_monitor_graph.py` — sửa: thêm test `stripDetail`.

## Quyết định

- Hàm trang đặt tên `historyPage`, không dùng `history`, để không đè `window.history` mà đường dẫn của UI3 dùng.
- Tiêu đề cột ngắn ("Các bước"); thứ tự 7 ô ghi ở dòng chú thích (tiêu đề dài đè lên cột bên cạnh).

## Kiểm tra

- Trình duyệt, monitor thử 8798:
  - 9 lượt, 49 ô; di chuột ô Cào lỗi hiện "Trip KS: tìm ID: Lỗi / Trip KS: giá phòng: Không chạy";
  - lọc daily → 2/9;
  - bấm ô Cào đỏ của `full-20260925T090555Z-186774` → mở lượt, chọn `trip-hotels.discover` (lỗi);
  - 375 px: không cuộn ngang (`scrollWidth` 375).
- Cả bộ test: xem entry UI5.

## Còn lại / rủi ro

- Chưa commit.
