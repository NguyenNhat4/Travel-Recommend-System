# UI2: sơ đồ luồng và panel theo ô thay cho 9 tab của lượt

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

UI2 của `docs/plan/2026-09-28-monitor-so-do-luong.md`: mở một lượt thì thấy sơ đồ các bước (dữ liệu từ `/api/graph` của UI1);
bấm một ô thì panel bên dưới chỉ hiện những gì thuộc bước đó, thay cho thanh 9 tab ngang nhau.

## File thay đổi

- `src/data_collection/monitor_ui/index.html` — sửa:
  - thêm CSS cho sơ đồ, ô và dạng danh sách dọc trên màn hình < 700 px;
  - bỏ `TABS`, viết lại `openRun`;
  - thêm `graphHtml`, `drawEdges` (SVG), `panelHead`, `renderPanel`, `selectNode`, `runView`, `refreshGraph`, `tabDetail`, `tabErrors`;
  - `tabSources` lọc theo thư mục của làn;
  - các action `run`, `list`, `stop` giữ ô đang chọn; thêm action `runView`;
  - bấm vào ô `[data-node]`; vẽ lại đường nối khi đổi kích thước cửa sổ.
- `src/data_collection/monitor.py` — sửa:
  - `graph()`: mỗi làn có thêm `dirs`;
  - ô Gộp: `in` là tổng `recordsRead` (vốn là số theo từng nguồn; trước đây UI hiện NaN);
  - ô đơn (Chuẩn bị, Gộp…) dùng nhãn ngắn; nhãn dài của bước xem ở panel "Chi tiết bước";
  - `_stage_entries('errors')`: chưa có `normalise_stages/errors.jsonl` thì đọc `normalised/*.errors.jsonl`.
- `src/data_collection/tests/test_monitor_graph.py` — sửa:
  - thêm 2 test (dirs của làn; bản ghi lỗi theo nguồn trước bước Gộp);
  - `recordsRead` dạng từng nguồn.
- `docs/plan/2026-09-28-monitor-so-do-luong.md` — sửa: dòng tiến độ.

## Quyết định

- Panel theo loại ô:

  | Ô | Tab con của panel |
  |---|---|
  | Cào | Tiến độ & tốc độ, Raw / interim (chỉ nguồn của làn), Theo thành phố, Log |
  | Chuẩn hoá theo nguồn | Bản ghi lỗi (lọc theo nguồn), Chuẩn hoá, Log |
  | Chuẩn hoá chung | Chuẩn hoá, Log |
  | Gộp | Chuẩn hoá, Catalog cuối, Theo thành phố, Log |
  | Kiểm tra | Báo cáo, Log |
  | Nạp DB | Trước → sau, Log |
  | Index | Embedding, Log |
  | Chuẩn bị, Bước khác | Chi tiết bước, Log |

  Các hàm vẽ tab cũ được dùng lại nguyên, như plan đã chấp nhận ở UI2.
- Log trong panel được lọc sẵn:
  - ô cào theo nhóm site;
  - ô chuẩn hoá theo nguồn theo chữ `[normalise:<nguồn>]`;
  - các ô còn lại theo nhóm `job`.
- Đầu lượt có các nút "Log toàn lượt", "Tiến độ & tốc độ", "Báo cáo" cho phần không thuộc ô nào; mọi tab cũ vẫn tới được.
- Lượt đang chạy: sơ đồ và phần đầu panel làm mới mỗi 3 giây, không vẽ lại nội dung tab (form chỉnh tốc độ không mất chữ đang gõ).
  Lượt vừa kết thúc thì tải lại cả lượt một lần.
- "Không chạy" trong ô hiện màu xám thay vì đỏ: bước chưa chạy không phải là lỗi. Các bảng khác giữ màu cũ.
- **Khác plan:**
  - màn hình hẹp: bấm ô thì trang cuộn xuống panel, thay vì chèn panel ngay dưới ô như plan viết. Lý do: sơ đồ được vẽ lại
    mỗi 3 giây khi lượt chạy, panel chèn giữa sơ đồ sẽ bị xoá theo;
  - mở lượt chưa chọn sẵn ô nào (panel hiện hướng dẫn "Bấm một ô…"); chọn sẵn ô là việc của UI3.

## Kiểm tra

- `pytest tests/test_monitor_graph.py` (env `vsf`): **13 passed**. `pytest tests`: **400 passed, 3 skipped**.
- `git diff --check` trên `monitor.py`, `index.html`: sạch.
- Trình duyệt, monitor thử ở cổng 8799 (`data/local_crawl`) và 8798 (`data/local_crawl_demo`); monitor 8765 không bị động tới:
  - script bấm lần lượt **mọi ô × mọi tab con** của 12 lượt (5 + 7) và 3 nút cấp lượt: không exception, không tab nào kẹt "Đang tải…", console không lỗi;
  - lượt lỗi `full-20260928T024657Z-14811`: ô "Trip vé máy bay" viền đỏ "Lỗi", các bước sau "Không chạy";
  - lượt dừng `full-20260928T042452Z-100788`: 4 ô chuẩn hoá theo nguồn; ô booking.com khách sạn hiện "6 → 29", tab Bản ghi lỗi mở được trước bước Gộp;
  - lượt ok `full-20260925T091848Z-201309`: đủ 7 cột xanh, ô Gộp "459 → 631 · nháp 3";
  - 375 px: sơ đồ thành danh sách dọc theo cột, trang không cuộn ngang (`scrollWidth` 375).
- Chưa kiểm với một lượt **đang chạy** thật (làm mới 3 giây, chuyển sang kết thúc).

## Còn lại / rủi ro

- UI3 (dải lỗi, chọn sẵn ô, đường dẫn), UI4, UI5 chưa làm.
- Tab "Tiến độ & tốc độ" của ô cào vẫn hiện mọi nguồn (hàm cũ), chưa lọc theo làn.
- Chưa kiểm lượt đang chạy thật. Monitor 8765 phải khởi động lại để có giao diện mới.
- `index.html` 381 dòng (ngưỡng tách JS trong plan: ~600).
- Chưa commit.
