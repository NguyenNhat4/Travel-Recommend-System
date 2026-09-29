# UI1: API sơ đồ luồng và dải bước cho monitor

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

UI1 của `docs/plan/2026-09-28-monitor-so-do-luong.md`: server tính sẵn ô và đường nối của một lượt, cùng dải trạng thái
theo cột cho trang Lịch sử. Chưa đổi giao diện.

## File thay đổi

- `src/data_collection/monitor.py` — sửa (chỉ phần của UI1; file đã có thay đổi chưa commit từ các CP trước):
  - thêm `GRAPH_COLUMNS`, `GRAPH_SINGLE`, `GRAPH_MODES`, `NORMALISE_SOURCE`, `NORMALISE_ALL`, `STEP_LABELS`, `SEVERITY`;
  - thêm hàm `stem_lanes`, `graph_strip`;
  - thêm `FreshMonitor.graph` và `FreshMonitor._graph_nodes`;
  - `FreshMonitor.runs` thêm `strip`, `products`, `productsDelta`;
  - thêm route `GET /api/graph?run=`.
- `src/data_collection/tests/test_monitor_graph.py` — thêm: 11 test.
- `docs/plan/2026-09-28-monitor-so-do-luong.md` — sửa: dòng tiến độ.

## Quyết định

- Cột: Chuẩn bị → Cào → Chuẩn hoá → Gộp → Kiểm tra → Nạp DB → Index; mỗi nguồn trong `SOURCES` là một làn.
  Trip khách sạn có hai ô `discover` → `prices`.
- Ô chuẩn hoá lấy từ bước `normalise.source:*` và từ `normalised/*.meta.json`, nên checkpoint không có bước tương ứng
  vẫn hiện. Nguồn không khớp thư mục (vd. `trip_combos`) nối từ mọi làn cùng họ nguồn.
- Lượt không có chuẩn hoá theo nguồn (lượt trước CP5, lượt daily) có một ô chung `normalise.sources`,
  mang trạng thái của bước Gộp.
- `normalise.preview` không thành ô; ô Gộp có `drafts` là số lần gộp nháp.
- Bước thiếu: "Không thuộc lượt" nếu chế độ không có bước đó, "Đã tắt" nếu nguồn tắt trong cấu hình của lượt,
  "Chờ tới lượt" khi lượt đang chạy, "Không chạy" khi lượt đã kết thúc. Lượt mất tiến trình: ô đang chạy thành "Mất tiến trình".
- Bước chưa khai báo nằm ở cột "Bước khác" (không vào dải).
- Dải lấy trạng thái xấu nhất theo `SEVERITY`: "Không thuộc lượt" < "Đã tắt" < "Không chạy" < xong < … < lỗi.
- Dải của `/api/runs` không đếm interim (chỉ đọc `run.json` và meta) để trang Tổng quan poll không chậm đi.
- `productsDelta` so với lượt trước **cùng chế độ** có số sản phẩm.

## Kiểm tra

- `pytest tests/test_monitor_graph.py` (env `vsf`): **11 passed**.
- `pytest tests` (env `vsf`): **398 passed, 3 skipped**.
- `graph()` chạy trên mọi lượt trong `data/*/runs` (14 lượt), không lỗi:
  - lượt `full-20260928T024657Z-14811` có cột Cào lỗi ở `trip-flights`;
  - lượt `index-…` có mọi cột giữa là "Không thuộc lượt";
  - lượt cũ trước CP5 có một ô chuẩn hoá chung.
- Server tạm trên cổng ngẫu nhiên: `/api/graph?run=<lượt thật>` trả 200, mã lượt sai trả 400, `/api/runs` có `strip`.
- `git diff --check` trên `monitor.py`: sạch.

## Còn lại / rủi ro

- UI2–UI5 chưa làm. Monitor đang mở phải khởi động lại mới có `/api/graph`.
- Lượt daily xong mà nguồn Trip khách sạn tắt: các cột Chuẩn hoá tới Nạp DB là "Không chạy" dù lượt ok. Như vậy là đúng
  với những gì job làm, nhưng có thể gây hiểu nhầm trên UI; cần xem lại ở UI2/UI4.
- Chưa commit.
