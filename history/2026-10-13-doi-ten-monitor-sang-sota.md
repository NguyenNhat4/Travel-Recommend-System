# Đổi tên hiển thị của monitor job cào từ V-OTA sang Sota

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: fix/crawl-stall-watchdog (worktree `~/code/trp-crawl-stall`)
- Trạng thái: dang dở — đã sửa và xem trên monitor local, đã commit + push nhánh, chưa PR/deploy
- Phạm vi: data

## Mục tiêu

Người dùng: "Đổi tên vota thành sota luôn", rồi "đổi trong monitor thôi, app đã được đổi rồi" (app ghi "Sota" từ commit
550e54ea).

## File thay đổi

- `src/data_collection/monitor_ui/index.html` — sửa: `<title>` "V-OTA · Fresh catalog" → "Sota · Fresh catalog"; đầu trang
  `<h1>` "V-OTA / Fresh catalog" → "Sota / Fresh catalog".
- `history/2026-10-13-doi-ten-monitor-sang-sota.md` — thêm: entry này.

## Quyết định

- Chỉ đổi tên hiển thị, viết "Sota" như app (`src/frontend/src/components/common/Header.tsx`).
- Giữ tên kỹ thuật: database `vota` và collection `Product` trong câu "Chế độ local: … không đụng vota/Product" (tên thật của
  database), header `X-Requested-With: vota-monitor` (monitor kiểm header này cho mọi yêu cầu ghi), tên VM, role, image.
- Không lệch PRD: PRD không quy định tên hiển thị của monitor.

## Kiểm tra

- `grep -n "V-OTA\|X-OTA" src/data_collection/monitor.py src/data_collection/monitor_ui/index.html`: không còn.
- Monitor local (`monitor.py --read-only --port 8767`, thư mục state trống), 13/10 00:58: `document.title` = "Sota · Fresh catalog", `<h1>` = "Sota / Fresh catalog"; tab Cấu hình có `timeout.stallMinutes` = 30.

## Còn lại / rủi ro

- PR cùng nhánh khi người dùng bảo.
