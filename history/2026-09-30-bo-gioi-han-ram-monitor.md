# Bỏ giới hạn RAM mặc định của monitor (giết lượt Cào lớn)

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Sửa lỗi do `2026-09-30-monitor-tu-bat-lai-gioi-han-ram.md` gây ra (thay quyết định `--memory 1g` mặc định ở entry đó; giữ
`--restart unless-stopped`). Người yêu cầu gửi ảnh lượt `full-20260930T102033Z-1035`: "Thất bại · Lỗi ở: Cả lượt · timeout ·
Tiến trình kết thúc bất thường: -9".

## File thay đổi

- `src/data_collection/run_daily_docker.sh` — sửa: `fresh-monitor` không đặt `--memory` mặc định; chỉ đặt khi có
  `MONITOR_MEMORY`.
- `src/data_collection/tests/test_runner_fresh_monitor.py` — sửa: mặc định không có `--memory`; `MONITOR_MEMORY` vẫn áp dụng.
- `docs/guide/trien-khai-job-cao-du-lieu.md`, `src/data_collection/README.md` — sửa: mô tả mới.
- `history/2026-09-30-bo-gioi-han-ram-monitor.md` — thêm: entry này.

## Quyết định

- Chẩn đoán (API monitor, chỉ đọc): PR #58 merge 09:54Z, CD crawler xong 09:57:59Z → monitor chạy với `--memory 1g`. Lượt
  `full` `trigger=monitor` bắt đầu 10:20:33Z, kết thúc 10:30:13Z, lỗi "-9" (SIGKILL). Lượt bấm trên monitor là tiến trình con
  trong container monitor (`monitor.py` gọi `fresh_catalog.py`), nên tính chung giới hạn 1 GB; lượt `full` có Chromium +
  chạy liên tục (chuẩn hoá / gộp / nạp DB / index song song) vượt 1 GB → bị giết. Không có CD nào chạy lúc 10:20–10:30.
  Chưa xác nhận bằng `dmesg` trên VM (không có quyền), nhưng thời điểm và mã -9 khớp.
- Lượt theo lịch (cron → `fresh-run` container riêng) không có giới hạn, không bị ảnh hưởng.

## Kiểm tra

- `test_runner_fresh_monitor.py`: 3 passed; `bash -n run_daily_docker.sh`: ok.

## Còn lại / rủi ro

- 451 dòng đã nạp theo phần (chạy liên tục) của lượt thất bại vẫn ở DB (đúng thiết kế chạy liên tục).
- Hết RAM toàn VM vẫn có thể xảy ra (4 GB): nên thêm swap / nâng RAM; cân nhắc tắt "Chạy liên tục".
- Chưa commit.
