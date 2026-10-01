# UI2b: hiện bước con bên trong Chuẩn hoá và Gộp, trạng thái gộp nháp trên sơ đồ

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người yêu cầu xem lượt `full-20260928T080824Z-245196` và thấy ô Gộp "Chờ tới lượt · nháp 4", nên tưởng Gộp đang nghẽn.
Người yêu cầu cũng muốn thấy bên trong Chuẩn hoá và Gộp làm những gì. UI2b được thêm vào
`docs/plan/2026-09-28-monitor-so-do-luong.md` và người yêu cầu đồng ý làm ngay.

## File thay đổi

- `src/data_collection/monitor.py` — sửa:
  - thêm `SUBSTEP_INFO`: một câu mô tả việc từng bước con làm;
  - thêm `running_substep`;
  - thêm `FreshMonitor.substeps` và route `GET /api/substeps?run=&node=&variant=`;
  - ô Gộp có `draft` (lần, trạng thái, số dòng, nhóm site, nguồn, lúc). Lượt đang chạy mà chưa có bản chính thức thì trạng thái "draft";
  - ô đang chạy có `substep` (bước con hiện tại);
  - `SEVERITY` thêm `draft`.
- `src/data_collection/normalise_stream.py` — sửa:
  - meta ghi thêm `steps`: thời gian và số dòng của 4 bước con trong lô cuối (đọc phần mới, bỏ trùng, ánh xạ bản ghi mới, ghi checkpoint);
  - meta ghi thêm `history`: 40 lô gần nhất;
  - meta được ghi lại riêng sau bước ghi checkpoint để có thời gian của chính bước đó.
- `src/data_collection/monitor_ui/index.html` — sửa:
  - tab "Các bước bên trong" đứng đầu panel ô chuẩn hoá theo nguồn và ô Gộp: luồng dọc các bước con, mỗi bước có mô tả,
    giây (thanh so sánh), vào → ra, RAM, lỗi và traceback;
  - ô Gộp có nút chọn bản nháp / bản chính thức, bảng mọi lần gộp nháp, và bảng các lô khi chạy liên tục;
  - ô Gộp hiện "nháp N · M dòng · xong: nhóm…"; ô đang chạy hiện "đang: <bước con>";
  - thêm nhãn "Đang gộp nháp"; phần đầu panel có dòng tóm tắt bản nháp mới nhất; "Không chạy" màu xám.
- `src/data_collection/tests/test_monitor_graph.py` — sửa: thêm 3 test và hàm `put` tạo thư mục cha.
- `src/data_collection/tests/test_normalise_stream.py` — sửa: thêm 1 test cho bước con và lịch sử lô.
- `docs/plan/2026-09-28-monitor-so-do-luong.md` — sửa: thêm mục UI2b, cập nhật tiến độ.

## Quyết định

- Bước Gộp **không** nghẽn ở phần tính toán. Trong lượt trên:
  - 4 lần gộp nháp mất 27,2 / 1,3 / 0,7 / 0,4 s; mỗi bước con 0,001–0,02 s;
  - bản chính thức đợi Vinpearl cào xong. Như vậy là đúng, vì gộp trùng cần mọi nguồn.

  Cái sai là cách hiển thị: ô Gộp chỉ theo dõi bản chính thức. Thời gian chuẩn hoá 9,8 s và lần gộp nháp đầu 27 s chủ yếu
  là khởi động tiến trình con và import thư viện.
- Chỉ bản nháp mới nhất còn số liệu bước con, vì thư mục `preview/` được thay mỗi lần. Các lần nháp cũ còn dòng tóm tắt
  trong `run.json`.
- "Đang gộp nháp" chỉ hiện khi lượt còn chạy. Lượt đã dừng thì ô Gộp là "Không chạy", kèm dòng tóm tắt bản nháp.
- Mô tả bước con do agent viết từ code `normalise.py` (`merge_catalog`, `_normalise`, `normalise_stream`). Người yêu cầu cần đọc lại.

## Kiểm tra

- `pytest tests/test_monitor_graph.py tests/test_normalise_stream.py` (env `vsf`): **37 passed**.
  `pytest tests`: **424 passed, 3 skipped**. `git diff --check`: sạch.
- Trình duyệt, monitor thử 8799 (`data/local_crawl`) và 8798 (`data/local_crawl_demo`):
  - lượt `full-20260928T080824Z-245196`: ô Gộp "nháp 4 · 59 dòng · xong: agoda, booking, trip"; panel hiện 9 bước con có
    mô tả (tổng 0,072 s); ô booking.com khách sạn hiện 2 bước con (đọc interim 6 dòng, ánh xạ 6 → 29);
  - script bấm mọi ô × mọi tab con của 12 lượt: không exception, không tab kẹt "Đang tải…";
  - lượt demo (trước CP1) báo "Chưa có số liệu bước con".
- Chưa kiểm trên lượt đang chạy thật (cập nhật mỗi 3 s, "Đang gộp nháp", bước con đang chạy), cũng chưa kiểm với chạy liên tục bật.

## Còn lại / rủi ro

- UI3–UI5; L2 phần 2, L3–L6 của plan chạy liên tục. Chưa commit.
- `index.html` 401 dòng (ngưỡng tách JS ~600).
