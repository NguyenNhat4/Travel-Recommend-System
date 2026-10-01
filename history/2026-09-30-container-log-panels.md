# Thêm panel log theo container vào staging dashboard

- Ngày: 2026-09-30
- Tác giả: người dùng / Codex
- Nhánh: khoa/agent-watcher-containers
- Trạng thái: hoàn thành phần source và validation cục bộ; chưa apply Terraform/GCP trong task này
- Phạm vi: monitoring

## Mục tiêu

Người dùng chọn phương án thêm log theo từng service vào dashboard Cloud Monitoring. Bổ sung panel riêng cho backend, frontend, crawler, Redis và Weaviate để tiện xem log cạnh metric/SLO hiện có.

## File thay đổi

- `infra/monitoring/main.tf` — thêm 5 `logsPanel` widget với filter theo App VM và tên container.
- `infra/monitoring/tests/test_staging_layout.sh` — thêm assertion cho tiêu đề panel và các container filter.
- `infra/monitoring/README.md` — mô tả panel log và giới hạn metadata runtime.
- `history/2026-09-30-container-log-panels.md` — ghi nhận task.

## Quyết định

- Dùng native `LogsPanel` của Cloud Monitoring, không thêm Grafana hoặc stack logging mới.
- Giữ nguyên các metric, alert, SLO và widget monitoring đang có trong worktree.
- Crawler panel nhận cả `jsonPayload.container_name="vota-fresh-catalog"` và log message `fresh-catalog.` vì crawler còn ghi file log riêng.
- Các panel backend/frontend/Redis/Weaviate lọc theo `jsonPayload.container_name`; log Docker JSON thực tế có thể không được Ops Agent enrich tên Compose service, nên cần xác minh entry runtime sau khi triển khai.
- Không sửa PRD; thay đổi thuộc lớp vận hành và phù hợp NFR-PERF-01/NFR-REL-01 cùng deployment plan §5–6.

## Kiểm tra

- TDD RED: layout test fail vì thiếu 5 tiêu đề/filter panel.
- TDD GREEN: `bash infra/monitoring/tests/test_staging_layout.sh` — PASS, 2 unittest PASS.
- `terraform -chdir=infra/monitoring fmt -check -recursive` — PASS.
- `git diff --check` — PASS.
- `terraform -chdir=infra/monitoring validate -no-color` — INCONCLUSIVE: cached Google provider `darwin_amd64` không hoàn tất plugin handshake trên máy local.
- Chưa chạy Terraform plan/apply hoặc cài/restart Ops Agent trên VM.

## Còn lại / rủi ro

- Cần chạy plan/apply staging qua workflow/remote Terraform state sau khi review.
- Cần kiểm tra Logs Explorer để xác nhận log Docker app có `jsonPayload.container_name`; nếu không, các panel named container có thể chỉ hiện lifecycle entries hoặc rỗng.
- Redis và Weaviate không nằm trong Compose backend VM hiện tại; panel tương ứng chỉ có dữ liệu nếu các container đó thực sự chạy trên App VM và được gửi log về cùng project.
