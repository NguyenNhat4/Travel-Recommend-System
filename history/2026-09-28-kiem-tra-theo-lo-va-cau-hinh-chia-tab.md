# Ô Kiểm tra khi nạp theo phần, bật chạy liên tục local, Cấu hình chia tab + nút một lần bấm

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người yêu cầu thấy lượt `full-20260928T100701Z-339934` có Gộp / Kiểm tra / Nạp DB / Index "đứng" trong lúc Vinpearl còn cào,
và muốn các bước sau vẫn chạy. Lượt đó chạy với `stream.enabled/db/index = False`. Người yêu cầu yêu cầu:
- ô Kiểm tra không còn "Chờ tới lượt" khi đang nạp theo phần;
- bật sẵn công tắc;
- UI ít phải bấm nhiều nút, chia nhỏ.

## File thay đổi

- `src/data_collection/monitor.py` — sửa:
  - khi bước `stream.db` đang chạy và chưa có bước `validate`, ô Kiểm tra là "Đang chạy" kèm `note`
    ("kiểm từng dòng theo lô nạp DB; kiểm cả catalog ở cuối lượt");
  - `overview()` trả `stream` (3 công tắc).
- `src/data_collection/fresh_settings.py` — sửa: thêm nhóm cấu hình "Chạy liên tục" (`stream`), chuyển 8 trường `stream.*`
  từ nhóm "Chiến thuật từng nguồn" sang. Mặc định không đổi (tắt).
- `src/data_collection/monitor_ui/index.html` — sửa:
  - trang Cấu hình chia tab theo nhóm, một form chung, "Lưu" gửi thay đổi của mọi tab;
  - nút một lần bấm "Bật đủ" / "Tắt" chạy liên tục (chuẩn hoá + nạp DB + index) ở đầu trang Cấu hình và trên Tổng quan;
  - ô sơ đồ hiện `note`.
- `src/data_collection/tests/test_monitor_graph.py`, `tests/test_stream_feed.py` — sửa: thêm test ô Kiểm tra và nhóm cấu hình.
- Cấu hình local (không nằm trong Git): `src/data_collection/data/local_crawl/state/settings.json` —
  `stream.enabled`, `stream.db`, `stream.index` = true (ghi bằng `fresh_settings.save`), áp dụng từ lượt kế tiếp.

## Quyết định

- "Chia nhỏ để share các tag khác" được hiểu là: chia trang Cấu hình thành tab theo nhóm, và tách nhóm "Chạy liên tục" riêng
  có nút một lần bấm. Đây là cách hiểu của agent.
- Mặc định trong code vẫn tắt (plan: bật mặc định sau khi người yêu cầu kiểm một lượt thật). Chỉ cấu hình local của
  người yêu cầu được bật.
- Kiểm tra cả catalog vẫn chạy ở cuối lượt (cần đủ mọi nguồn); ô Kiểm tra chỉ phản ánh việc kiểm từng dòng trong mỗi lô nạp.

## Kiểm tra

- `pytest tests` (env `vsf`): **468 passed, 5 skipped**. `git diff --check`: sạch.
- `fresh_settings.load(data/local_crawl/state)`: 3 công tắc = true; chu kỳ 15 / 30 / 60 / 300 s.
- Trình duyệt, monitor thử 8796 với **bản sao** `local_crawl_demo/state` trong scratchpad (không đổi cấu hình demo thật):
  - 8 tab, mở tab "Chạy liên tục" thấy 8 trường;
  - "Bật đủ" → 3 công tắc true; "Tắt" → false;
  - sửa `runs.keep` ở tab Lưu trữ, chuyển tab rồi Lưu → lưu 9;
  - nút trên Tổng quan đổi trạng thái sau một lần bấm.

## Còn lại / rủi ro

- Chưa thấy ô Kiểm tra "Đang chạy" trên lượt thật; cần lượt kế tiếp (đã bật chạy liên tục). Chưa commit.
