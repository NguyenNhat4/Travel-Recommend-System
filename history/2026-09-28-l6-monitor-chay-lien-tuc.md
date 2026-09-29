# L6: monitor cho các việc chạy liên tục, nút chỉnh sống, đổi tên "bản nháp"

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

L6 của `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`:
- sơ đồ thấy dữ liệu chảy qua các bước trong lúc cào;
- nút chỉnh chu kỳ / tạm dừng / chạy ngay khi lượt đang chạy (người yêu cầu thêm 2026-09-28);
- "bản nháp" đổi thành "catalog đang gộp".

## File thay đổi

- `src/data_collection/collectors/live_control.py` — sửa: thêm `STREAM` (4 việc: chu kỳ tối thiểu/tối đa, khoá cấu hình)
  và `_validate_stream` (`interval`, `paused`, `kick` → `kickAt`). Khoá nguồn cào không đổi.
- `src/data_collection/stream_feed.py` — sửa: `Ticker` đọc `kickAt` mới thì chạy ngay; `on_result`; `start(target)`.
- `src/data_collection/normalise_stream.py` — sửa: vòng lặp dùng `Ticker` (đọc `stream.normalise` từ live_control).
- `src/data_collection/fresh_catalog.py` — sửa: mỗi việc chạy trong bước `stream.<việc>` của `run.json` (đang chạy suốt phần
  cào; detail: số lô, lô gần nhất, số dòng ghi DB), ghi `run.json` sau mỗi lô.
- `src/data_collection/monitor.py` — sửa:
  - `STREAM_STEPS`: bước `stream.*` gắn vào ô Gộp / Nạp DB / Index (`node.stream`), không thành "Bước khác";
  - ô Nạp DB / Index "Đang chạy" khi chưa có bước chính thức;
  - `GET /api/feed?run=&kind=db|index`;
  - `live()` trả thêm `stream` (bật/tắt theo cấu hình lượt, chu kỳ gốc / đang chỉnh, tạm dừng, `kickAt`).
- `src/data_collection/monitor_ui/index.html` — sửa:
  - dòng "theo phần: N lô · M dòng ghi" trên ô;
  - tab "Các lô theo phần" cho Nạp DB / Index;
  - tab cấp lượt "Chạy liên tục" với 4 hàng điều khiển;
  - trong panel ô Gộp / Nạp DB / Index / Chuẩn hoá theo nguồn: nút Áp dụng / Về cấu hình lượt / Tạm dừng–Chạy tiếp /
    Chạy ngay ("Chuẩn hoá ngay"; ẩn khi đang tạm dừng);
  - đổi mọi chữ "bản nháp / nháp" hiển thị thành "catalog đang gộp", nhãn "Đang gộp dần";
  - không vẽ lại phần đầu panel khi đang gõ trong ô chu kỳ.
- `src/data_collection/tests/test_monitor_graph.py`, `tests/test_stream_feed.py` — sửa: thêm test.

## Quyết định

- Dùng lại cơ chế `live_control` của tốc độ cào (một file, đọc lại mỗi 0,5 s, bị xoá đầu và cuối lượt): thay đổi áp từ lô
  kế tiếp, chỉ cho lượt đang chạy.
- "Chuẩn hoá ngay" chạy một lần đọc phần mới cho **mọi** nguồn chưa chốt, không riêng một nguồn. Lý do: rẻ, mỗi lần đọc
  không có gì mới gần như 0 s.
- `stream.enabled` **vẫn mặc định tắt** (plan: bật mặc định sau khi người yêu cầu kiểm một lượt thật).

## Kiểm tra

- `pytest tests` (env `vsf`): **445 passed, 5 skipped** (5 skip: 2 test Postgres thật cần `STREAM_TEST_ADMIN_URL`, đã chạy
  riêng và pass; 3 skip có từ trước).
- Test đơn vị:
  - `live_control` kiểm `stream.*` (biên, kiểu, trường lạ);
  - monitor ghi file → `Ticker` của job đọc được kick / tạm dừng / chu kỳ; file của lượt khác không áp;
  - `graph()` gắn `stream.*` đúng ô; bước chính thức thắng bước theo phần;
  - `live()` trả hàng `stream`.
- Trình duyệt, monitor thử cổng 8797 trên **lượt giả đang chạy** trong scratchpad (tiến trình giữ khoá + nhịp sống; dữ liệu
  lấy từ lượt thật `full-20260928T080824Z-245196`), không cào thật:
  - ô Gộp "Đang gộp dần · theo phần: 5 lô", Nạp DB "Đang chạy · 3 lô · 41 dòng ghi", Index "1 lô";
  - panel Nạp DB: đặt chu kỳ 20 s, Tạm dừng, Chạy ngay → `/api/live` trả `override 20, paused true, kickAt`;
  - tab "Các lô theo phần" hiện 4 lô, có lô lỗi kết nối.

## Còn lại / rủi ro

- Chưa chạy trong lượt cào thật. Chưa commit.
