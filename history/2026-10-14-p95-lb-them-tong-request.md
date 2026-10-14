# Cảnh báo p95 độ trễ LB: thêm điều kiện tổng request để p95 đủ mẫu

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/canh-bao-tai-nguyen-db-crawler (PR #211, follow-up)
- Trạng thái: hoàn thành (đã apply lên GCP `vinpearl-508801`)
- Phạm vi: infra (staging-ha)
- Liên quan: `2026-10-14-canh-bao-tai-nguyen-db-va-crawler.md` (cùng PR), `docs/spec/load-test/2026-10-14-stress-doc-lien-tuc.md` (stress 00:10–09:30 giờ VN)

## Mục tiêu

Cảnh báo "p95 độ trễ backend cao" (LB, ngưỡng 800 ms trong 10 phút) kêu trên p95 của vài request. Yêu cầu: thêm tổng request để p95 có đủ mẫu.

## Số liệu căn cứ (chỉ đọc, 14/10 UTC)

- 02:24–02:25: p95 16,7 s và 14,2 s với khoảng 1.300 request/phút. Đây là sự cố thật, và điều kiện mới không chặn nó.
- 03:19–03:20: chỉ 78–127 request/phút nhưng p95 nhảy tới 3.168 ms. Đây là nhiễu do quá ít mẫu: vài request chậm đủ làm p95 vọt.
- 72 giờ, cửa sổ 10 phút: trung vị 175 request, 5% cửa sổ thấp nhất dưới 46, 234/432 cửa sổ dưới 300.

Ngưỡng 100 request/10 phút: đủ để p95 dựa trên ít nhất 100 mẫu. Thấp hơn 50 thì p95 không còn ý nghĩa.

## File thay đổi

- `infra/terraform/environments/staging-ha/monitoring.tf`: policy `lb_latency` đổi `combiner` từ `OR` sang `AND`; thêm điều kiện thứ hai "Tổng request LB trong 10 phút > N" (`local.lb_rule_filter_prefix`, ALIGN_SUM, REDUCE_SUM, cửa sổ 600 s, duration 600 s); cập nhật mô tả.
- `infra/terraform/environments/staging-ha/variables.tf`: thêm `alert_p95_min_requests` (mặc định 100), mô tả tiếng Việt.
- `infra/terraform/environments/staging-ha/tests/test_alerts.py`: thêm test `test_latency_alert_needs_enough_requests_to_trust_p95`.
- `history/2026-10-14-p95-lb-them-tong-request.md`: entry này.

Allowlist CD đã có `google_monitoring_alert_policy.lb_latency|update`, không cần sửa.

## Quyết định

- **AND thay vì điều kiện riêng**: để điều kiện tổng request là điều kiện bắt buộc cùng lúc với p95, không phải một alert khác.
- **Tổng request gồm cả probe** của kiểm tra uptime (`vota-ha HA sẵn sàng qua LB`). Probe ít (vài request/phút), nên không đổi ngưỡng; ghi lại để tra cứu.
- **Không đổi ngưỡng 800 ms.** NFR-PERF-01 yêu cầu p95 search ≤ 250 ms, nhưng alert này áp cho mọi route, gồm cả SSE. Đây là lệch đã biết, chưa đổi vì cần quyết định ngưỡng và phạm vi route.
- **Không đổi PRD**: đây là chi tiết vận hành, theo tiền lệ các entry monitor trước.

## Đã apply

- `terraform plan -target=google_monitoring_alert_policy.lb_latency`: **0 to add, 1 to change, 0 to destroy**. Thay đổi trong plan: `combiner OR → AND`, thêm `conditions`, cập nhật `documentation`.
- `terraform apply` từ plan đã lưu: **0 added, 1 changed, 0 destroyed**.
- Đọc lại từ API: combiner `AND`, hai điều kiện (p95 > 800 ms 10 phút; tổng request > 100 trong 10 phút), kênh không đổi.

## Kiểm tra

- `python3 tests/test_alerts.py`: 28 test OK (gồm test mới).
- `python3 tests/test_*.py`: tất cả OK, trừ `test_slot_deploy.py` (2 lỗi `mapfile` của `roll-staging-ha-app-slots.sh`, có sẵn trên nhánh gốc).
- `terraform fmt -check -recursive`: sạch.
- `bash -n scripts/deploy-staging-ha-app.sh`: OK.

## Còn lại

- Quyết định ngưỡng và phạm vi route của p95: 800 ms cho mọi route (hiện tại) hay tách search 250 ms theo NFR-PERF-01.
- Sự cố 03:29–03:34 UTC (503 trên `GET /api/v1/products/{id}`, p95 đến 22 s): đợt tải không rõ nguồn từ `ramp.sh` trên `stress-gen-1` (xem báo cáo stress, mục 5). Chưa xác định người khởi động.
