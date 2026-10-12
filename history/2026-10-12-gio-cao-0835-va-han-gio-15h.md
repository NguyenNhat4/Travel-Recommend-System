# Giờ cào mặc định 08:35, hạn giờ lượt 15/14 giờ

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người dùng yêu cầu đổi giờ cào sang 08:35 sáng. Từ 10/10 toàn bộ VM staging-ha (gồm `vota-ha-crawler`) chỉ bật 08:30–23:59
(`history/2026-10-10-lich-tat-mo-vm-2359-0830.md`), nên mặc định 02:00 không còn khớp: lượt theo lịch thực tế bắt đầu ở tick
đầu tiên sau khi VM bật. Lượt cào lớn mất 11–14 giờ, còn khung từ 08:35 tới 23:59 chỉ khoảng 15,4 giờ, nên hạ hạn giờ để lượt
tự kết thúc gọn (vẫn chuẩn hoá, nạp DB, index phần đã cào) trước khi VM tắt. Phục vụ FR-CAT-03 (catalog, lịch khả dụng làm mới
hằng ngày).

## File thay đổi

- `src/data_collection/fresh_settings.py` — sửa: `schedule.time` mặc định 02:00 → 08:35; `run.maxHours` 18 → 15;
  `crawl.maxHours` 16 → 14; help ghi lý do; ví dụ lỗi định dạng giờ đổi thành 08:35.
- `src/data_collection/tests/test_fresh_monitor.py` — sửa: `test_schedule_once_per_vietnam_day` dùng 08:45 (sau giờ mặc định
  mới) thay cho 02:15.
- `src/data_collection/README.md` — sửa: hạn giờ mặc định 15/14 giờ và giờ chạy mặc định 08:35.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: giờ chạy mặc định 08:35 VN.
- `history/2026-10-12-gio-cao-0835-va-han-gio-15h.md` — thêm: entry này.

## Quyết định

- Người dùng chọn đặt trên monitor production **và** sửa mặc định trong code, và chọn hạ `run.maxHours`/`crawl.maxHours` xuống
  15/14 giờ.
- Đã ghi cấu hình lên monitor production (https://monitor.praxis.io.vn, `POST /api/settings`) lúc khoảng 10:50 ngày 12/10:
  `schedule.time=08:35`, `run.maxHours=15`, `crawl.maxHours=14`. Đọc lại thấy cả ba có `source: file`, và `nextRun` =
  2026-10-13T08:35 (daily). Giá trị lưu trên monitor giữ qua các lần deploy; mặc định trong code chỉ có tác dụng khi chưa lưu.
- Giờ không có trong PRD (chỉ ở settings, README, guide), nên không cần đề xuất PRD.
- Không đổi job legacy (`cron_daily.sh`, `install-vota-cron.sh --job legacy`), cũng không đổi khung cào thêm 01:45–04:00 trong
  Terraform (`crawler_extra_start/stop_schedule`, của nhóm hạ tầng).

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python -m pytest data_collection/tests -q` (từ `src/`, env vsf2): lần đầu 1 failed (test lịch cứng
  02:15) / 646 passed / 27 skipped; sửa test xong, `test_fresh_monitor.py` 27 passed.
- Monitor production sau khi ghi: `schedule.time 08:35 file`, `run.maxHours 15.0 file`, `crawl.maxHours 14.0 file`.

## Còn lại / rủi ro

- Cron chỉ tick mỗi 15 phút (:00/:15/:30/:45), nên lượt theo lịch bắt đầu thật khoảng 08:45.
- Lượt bấm tay từ monitor chạy **bên trong container monitor**. CD crawler (`scripts/deploy-staging-ha-crawler.sh`) chạy
  `docker rm -f vota-fresh-catalog-monitor` nên giết luôn lượt đó: lượt `full-20261012T033631Z-3480` mất tiến trình lúc 10:46:44,
  ngay khi CD của PR #139 khởi động lại monitor (03:47:04Z). Chưa sửa, cần người dùng quyết định cách xử lý.
- Worktree còn thay đổi chưa commit của task monitor khác (`monitor.py`, `monitor_ui/index.html`, `test_monitor_progress.py`,
  `history/2026-10-09-monitor-buoc-con-chua-ghi-so-lieu.md`), không thuộc entry này.
