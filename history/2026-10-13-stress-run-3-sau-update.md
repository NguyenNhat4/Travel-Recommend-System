# Stress test đợt 3: chạy lại sau các update (13/10/2026)

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (Haiku 5.5, thực hiện)
- Nhánh: release-mvp-v2 (repo chính); script stress nằm ở worktree `claude/stress-test-design-a749f4` (chưa commit)
- Trạng thái: dang dở (R9 xong và dừng khẩn khi staging sập; R10 và R11 chưa chạy; staging trả 200 lúc 23:52:13 với 1 backend HEALTHY, `z2wq` đang VERIFYING)
- Phạm vi: docs (báo cáo đợt 3) và kiểm tra vận hành (không đổi code, không đổi hạ tầng)

## Mục tiêu

Chạy lại stress test sau các update trên staging (image mới 21:37, autoscaler 90%, các commit infra và agent), phân tích và so sánh với đợt 1.

## File thay đổi

- `docs/spec/load-test/2026-10-13-run-3.md` — thêm: báo cáo đợt 3 (R9, chuỗi sự kiện, phân tích, việc còn lại).
- `history/2026-10-13-stress-run-3-sau-update.md` — thêm: entry này.
- `stress-results/run-20261013-run3/R9-read-100.json` và `.log` — thêm: dữ liệu thô của k6. Không commit (thư mục không nằm trong git).

Không đổi code, contract, cấu hình hạ tầng hay thư mục `docs/plan/`. Hai file chưa commit `docs/plan/2026-10-13-cache-va-presort-catalog.md` và `history/2026-10-13-ke-hoach-cache-va-presort-catalog.md` có trước đợt này, không do đợt này tạo ra, và không bị sửa.

## Quyết định

- **Chạy R9 (100 rps, 1 VM) trước.** Chỉ chạy đúng một mức đã có số liệu để so với đợt 1. R10 (500 rps) và R11 (tìm kiếm) không chạy khi staging chưa phục hồi, vì mỗi đợt tải lên một VM hiện tại sẽ chỉ kéo dài sự cố.
- **Dừng k6 ngay khi staging trả 503 và không có backend HEALTHY.** k6 đã dừng khẩn ở 5% lỗi lúc 23:46:37; lệnh `pkill` bổ sung để bảo đảm không còn tiến trình nào gửi tải.
- **Không đổi `cpu_target`.** Đây là thay đổi hạ tầng do người vận hành quyết định (commit `10aa9488`). Đề xuất trả về 0,55 nằm trong báo cáo đợt 3.

## Kiểm tra

- `git status` trước khi viết entry: chỉ có `docs/spec/load-test/` và `history/2026-10-13-stress-run-3-sau-update.md` (mới), cùng các file chưa commit có sẵn từ trước.
- R9: 941/1050 lỗi (89,6%), p95 25,8 s, k6 dừng khẩn ở 5%.
- Sau R9: `/health/ready` 503, backend HEALTHY 0–1 trong suốt quan sát, autohealing thay `vota-ha-app-z2wq`.

## Còn lại / rủi ro

- Staging chưa phục hồi tại thời điểm viết entry. Cần chờ 2 VM HEALTHY ổn định trước khi chạy tiếp.
- Chưa tách được nguyên nhân giữa autoscaler 90% và image mới: cần chạy lại với 55% và cùng image.
- R10 (500 rps) và R11 (tìm kiếm 100 rps) chưa chạy.
- Đề xuất cải tiến code (cache catalog, presort `popular`, pool kết nối DB) chưa được duyệt, chưa làm.
- Dữ liệu `stress-results/` không nằm trong git; cần quyết định có thêm vào `.gitignore` không.
