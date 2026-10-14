# CD staging-ha chặn sau merge #216: dashboard lệch chuẩn hoá của API và tiêu đề 5xx

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/fix-cd-canh-bao-dashboard
- Trạng thái: dang dở (code và test xong, plan chỉ đọc đã kiểm; chưa commit tại thời điểm viết; chưa merge)
- Phạm vi: infra (staging-ha), scripts (allowlist CD)
- Liên quan: `2026-10-14-monitor-tach-dashboard-va-ten-vm.md` (PR #216, đã merge và apply tay)

## Sự cố

Run `staging-ha-infra-cd` sau merge #216 (`f222a8b3`) thất bại ở cổng plan: `Plan có thay đổi ngoài phạm vi cho phép: google_monitoring_dashboard.ha_alerts|update`. Không có gì được apply lên GCP (cổng dừng trước apply).

Nguyên nhân gồm hai phần:

1. **Cấu hình khác dạng API lưu lại.** API bỏ các tọa độ bằng 0 (`xPos`, `yPos`, `lowerBound`) và thêm `style = {}` cho ô text, `targetAxis = "Y1"` cho `dataSets` của biểu đồ xy. Cấu hình viết khác nên mỗi lần plan thấy lệch dù không có thay đổi thật. Sáu dashboard đều lệch, `ha` (đã trong allowlist `|update`) lệch âm thầm, `ha_alerts` (chưa trong allowlist) bị chặn.
2. **Tiêu đề ô 5xx.** `${var.alert_5xx_ratio * 100}` ra `1.9999…` do sai số thập phân, không phải `2`.

## Thay đổi

- `infra/terraform/environments/staging-ha/dashboard.tf`: bỏ `xPos`/`yPos` = 0, bỏ `lowerBound = 0`, thêm `style = {}` cho bảy ô text, thêm `targetAxis = "Y1"` cho mười tám `dataSets`. Không đổi nội dung, vị trí hay ngưỡng nào.
- `infra/terraform/environments/staging-ha/alerts_dashboard.tf`: viết đúng dạng API lưu (bỏ tọa độ 0; `style = {}`); tiêu đề 5xx dùng `format("%.0f", …)` ra `2%`.
- `infra/terraform/environments/staging-ha/tests/test_dashboard.py`: thêm hai test (dạng cấu hình khớp API; tiêu đề 5xx không có số thực thừa).
- `scripts/deploy-staging-ha-app.sh`: thêm `google_monitoring_dashboard.ha_alerts|update` có chú thích. Đây là thay đổi thật một lần (tiêu đề), không nới cổng chung.

## Kiểm tra

- `test_dashboard.py` 22 OK; `test_alerts.py` OK.
- `terraform fmt -check -recursive`: sạch. `terraform validate`: "The configuration is valid."
- Plan chỉ đọc `-target` cả sáu dashboard **trước** sửa: 6 đổi (toàn bộ là lệch chuẩn hoá, trừ tiêu đề 5xx của `ha_alerts`).
- Plan chỉ đọc **sau** sửa: `Plan: 0 to add, 1 to change, 0 to destroy`, chỉ `google_monitoring_dashboard.ha_alerts` (tiêu đề 5xx). Năm dashboard còn lại và `ha` không còn lệch.

## Còn lại

- Sau khi merge, CD sẽ đổi tiêu đề 5xx của `ha_alerts` (được phép bởi allowlist) và chạy xanh. Cần người merge PR.
- Cảnh báo `vota-staging:` (staging cũ) và lỗi `lượt cào một phần` vẫn như đã ghi trong entry trước.
