# UI3: dải lỗi, chọn sẵn ô, đường dẫn giữ trạng thái

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

UI3 của `docs/plan/2026-09-28-monitor-so-do-luong.md`: mở một lượt lỗi thì thấy ngay lỗi ở đâu mà không phải bấm gì; link gửi
cho người khác mở đúng chỗ.

## File thay đổi

- `src/data_collection/monitor.py` — sửa: thêm `graph_focus` (ô chọn sẵn và lỗi cho dải báo); `graph()` trả `focus`, `problem`.
- `src/data_collection/monitor_ui/index.html` — sửa:
  - dải báo lỗi ở đầu sơ đồ (bấm để chọn ô lỗi);
  - đường nối vào ô lỗi / mất tiến trình tô đỏ;
  - mở lượt không kèm ô thì chọn sẵn `focus`;
  - URL `#run=…&node=…&view=…` / `#page=…` (`stateHash`, `writeHash`, `applyHash`, nút Back);
  - link tới lượt đã bị xoá thì báo lỗi rồi về Tổng quan.
- `src/data_collection/tests/test_monitor_graph.py` — sửa: thêm test `focus` / `problem`.

## Quyết định

- Ô chọn sẵn:
  - có ô lỗi hoặc mất tiến trình → ô đầu tiên theo thứ tự cột; bị chặn xếp sau lỗi;
  - lượt đang chạy → ô đang chạy xa nhất;
  - còn lại → ô cuối cùng đã chạy.
- Không ô nào mang lỗi mà lượt có `error` (vd. lỗi trước khi vào bước nào) → dải báo "Cả lượt", không có ô để bấm.
- Đổi ô / tab thì `pushState`, nên nút Back quay lại ô trước.

## Kiểm tra

- `pytest tests/test_monitor_graph.py` (env `vsf`): test mới pass; cả bộ xem entry UI5.
- Trình duyệt, monitor thử 8798 (`data/local_crawl_demo`), lượt lỗi thật `full-20260925T090555Z-186774`:
  - mở `#run=…` → chọn sẵn "Trip KS: tìm ID"; URL thành `…&node=trip-hotels.discover&view=flow`;
  - dải "Lỗi ở: Trip KS: tìm ID"; 2 đường đỏ (vào ô đó và ô Index lỗi);
  - chọn ô Index rồi Back → về ô cũ;
  - tải lại `…&node=index&view=embed` → đúng ô, đúng tab Embedding;
  - `#run=full-20260101T000000Z-1` (không tồn tại) → thông báo lỗi, về Tổng quan.

## Còn lại / rủi ro

- Chưa commit.
