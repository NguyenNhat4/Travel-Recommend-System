# Monitor HA: độ trễ p95/p99 (LB, theo VM, theo route) và khung log trên dashboard

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (đã apply dashboard và metric; chưa commit; chưa có alert cho p99 hay search)
- Phạm vi: infra (staging-ha)
- Liên quan: `2026-10-12-monitor-ha-apply.md` (apply trước đó), `docs/spec/logging-schema.md` (trường `http.request`, `search.run`)

## Mục tiêu

Dashboard HA chưa trả lời được hai nhu cầu: độ trễ P95 và P99, và xem log ngay trên monitor. Bổ sung cả hai.

## File thay đổi

- `infra/terraform/environments/staging-ha/dashboard.tf` — viết lại: thêm metric `google_logging_metric.ha_api_latency`; dashboard có độ trễ LB (p95, p99), p95 và p99 theo VM, p95 theo route, bốn khung log (`logsPanel`), ba link Logs Explorer và ô giải thích cách đọc độ trễ.
- `infra/terraform/environments/staging-ha/tests/test_dashboard.py` — thêm 3 test: p99 có mặt đúng chỗ; metric loại `/stream` và `/health/`, có nhãn `route`; bốn khung log dùng chung bộ lọc với link.

## Quyết định

- Độ trễ API theo VM và theo route lấy từ log `http.request` (`jsonPayload.duration_ms`) qua metric **phân phối** (log-based distribution), để tính được p95/p99 đúng. LB không biết VM nào phục vụ, nên độ trễ LB chỉ cho toàn nhóm.
- Loại `/health/*` (probe) và `/stream` (SSE kéo dài theo LLM; NFR-PERF-02 đo bằng token đầu, không phải tổng thời gian). Độ trễ LB vẫn gồm SSE vì LB không lọc được.
- Nhãn `route` là route mẫu (`/api/v1/products/{product_id}`), đã kiểm trên 24 giờ log: cardinality thấp.
- Khung log: lỗi backend (`severity>=ERROR`), request > 1 s, container die/OOM (không tính helper), lượt cào (`service=crawler`, `severity>=WARNING`). Mỗi bộ lọc đã kiểm bằng `gcloud logging read` trước khi đưa vào Terraform.
- `logsPanel` không hiện cột tên VM. Vì vậy có link Logs Explorer với bộ lọc sẵn; cột `labels."compute.googleapis.com/resource_name"` là tên VM.
- Không thêm alert mới. Chưa có yêu cầu; nếu cần thì là quyết định riêng.

## Apply

- `terraform plan -target=google_logging_metric.ha_api_latency -target=google_monitoring_dashboard.ha`: 1 add, 1 change, 0 destroy. Apply thành công.
- Tiles trên dashboard đang chạy: 18; khung log: 4; ô có p99: 2.

## Kiểm

- Test staging-ha: alerts 12, dashboard 12, ha_telemetry 11, egress 6, health_checks 5, pgbouncer 9, resilience 23 — tất cả OK.
- `terraform fmt -check` sạch; `terraform validate`: "The configuration is valid."
- Metric có series theo VM (`instance_id`) và theo route: `/api/v1/search`, `/api/v1/products`, `/api/v1/products/{product_id}`, `/api/v1/destinations`.
- `ALIGN_PERCENTILE_95` và `ALIGN_PERCENTILE_99` trả giá trị (xem phát hiện bên dưới).
- Gửi khoảng 20 request đọc qua LB công khai để có dữ liệu mới. Đây là smoke nhẹ, không ghi dữ liệu.

## Phát hiện: độ trễ search vượt NFR nhiều lần

- Cửa sổ 60 phút gần nhất, route `/api/v1/search`: **p95 ≈ 3 990 ms, p99 ≈ 4 788 ms**. NFR-PERF-01 yêu cầu p95 ≤ 250 ms.
- Phía server (`duration_ms`) trùng với thời gian đo từ phía client, nên chậm nằm trong backend, không phải mạng.
- Log `search.run` cho thấy `engine_ms` ≈ 1 058 ms trong tổng 1 070 ms của một request. Phần lớn thời gian nằm trong engine tìm kiếm. Chưa phân tích từng bước (embedding, Weaviate, re-rank); cần thêm bước đo trước khi tối ưu.
- Đây là chỉ số thật của staging, không phải kết quả của monitor. Mẫu còn ít (vài chục request), nên con số còn dao động.

## Còn lại / rủi ro

- Mẫu thấp: p99 theo VM dao động mạnh khi ít request. Ô giải thích trên dashboard có nói rõ.
- Chưa có alert cho p99 hoặc cho search. Cần người quyết định ngưỡng và kênh.
- Phân tích nguyên nhân chậm của search: chưa làm.
- Các thay đổi drift không thuộc monitor (Patroni, bastion, DNS, lịch autoscaler) vẫn chưa được xử lý; xem `2026-10-12-monitor-ha-apply.md`.
- Chưa commit.
