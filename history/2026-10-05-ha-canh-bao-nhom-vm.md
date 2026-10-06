# Cảnh báo cho nhóm VM HA (việc 8)

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành
- Phạm vi: infra | docs

## Mục tiêu

Nhóm VM HA chưa được giám sát: các alert hiện có chỉ nhắm một app VM staging.

## File thay đổi

- `infra/terraform/environments/staging-ha/monitoring.tf` — thêm: 6 alert policy, uptime check qua LB, kênh email
- `infra/terraform/environments/staging-ha/variables.tf` — sửa: `alert_emails`, `notification_channel_ids`, `alert_p95_latency_ms`, `alert_5xx_ratio`
- `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` — sửa: ví dụ `alert_emails`
- `infra/terraform/environments/staging-ha/tests/test_alerts.py` — thêm: 9 test cấu trúc
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: use case và dòng việc 8

## Quyết định

- Đếm VM bằng số chuỗi `cpu/utilization` có tên bắt đầu bằng `<prefix>-app`, vì không có metric kích thước MIG đã xác nhận được tên và nhãn.
- Điều kiện vắng mặt kèm theo để bắt trường hợp nhóm bị xoá sạch (ngưỡng "nhỏ hơn" không kích hoạt khi không còn chuỗi nào).
- 5xx là tỷ lệ (`denominator_filter`), không phải số tuyệt đối.
- Use case: nhóm chạm trần 4 VM lúc 20:10, chậm và 5xx mà không ai được báo (plan §3b).

## Kiểm tra

- `terraform validate` staging-ha: pass; `test_alerts.py`: 9 passed; ba file test Terraform khác vẫn pass.
- Metric LB (`request_count`, `https_lb_rule`, `response_code_class`, `backend_latencies`) đối chiếu tài liệu Cloud Load Balancing qua tìm kiếm; `cpu/utilization` đã dùng ở `infra/monitoring`.
- Chưa kiểm: `redis.googleapis.com/stats/memory/usage_ratio`, lọc `instance_name=starts_with`, alert kích hoạt thật trên GCP (cần apply và tải thử).

## Còn lại / rủi ro

- Nếu `alert_emails` rỗng và không có channel, alert tồn tại nhưng không thông báo ai: đặt ít nhất một.
- Ngưỡng (2% 5xx, 800 ms, 80% Redis) là ước lượng ban đầu, cần chỉnh sau khi có số liệu thật.
