# Monitor job cào chỉ đọc công khai tại monitor.praxis.io.vn (deploy thủ công)

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude Code (thực hiện)
- Nhánh: khoa/staging-ha-monitor-readonly (worktree từ origin/release-mvp-v2 @ f23574ed); thay đổi local chưa commit
- Trạng thái: dang dở
- Phạm vi: infra (staging-ha), src/data_collection (crawler), scripts
- Bị thay thế bởi: 2026-10-09-monitor-staging-du-chuc-nang.md (phần chế độ chỉ đọc; deploy không còn `MONITOR_READ_ONLY=1`)

## Mục tiêu

Dashboard job cào (`monitor.py`, cổng 8765 của VM `vota-ha-crawler`) truy cập được từ internet tại `monitor.praxis.io.vn`, chỉ đọc, không có đăng nhập. Người vận hành chọn phương án này sau khi được cảnh báo rằng monitor bản không chỉ đọc có các endpoint POST điều khiển job.

## Lệch PRD (có chủ đích)

- Dashboard công khai không có xác thực, chưa có đề xuất PRD đã chốt. `docs/prd/deployment-plan.md` không ghi nhận đường truy cập này.
- Người vận hành chọn không tạo đề xuất PRD (cùng lựa chọn với CD staging-ha).

## File thay đổi (worktree khoa/staging-ha-monitor-readonly)

- `src/data_collection/monitor.py` — thêm: cờ `--read-only`; `do_POST` trả 405 khi bật; in `[chỉ đọc]` khi khởi động.
- `src/data_collection/run_daily_docker.sh` — thêm: biến `MONITOR_READ_ONLY` (mặc định 0), truyền `--read-only` vào `monitor.py`.
- `scripts/deploy-staging-ha-crawler.sh` — sửa: monitor chạy `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1 MONITOR_READ_ONLY=1`; thư mục dữ liệu `chown 10001:10001` (container chạy UID 10001), thư mục log thuộc user SSH.
- `scripts/deploy-staging-ha-app.sh` — thêm: các resource LB monitor và `google_compute_url_map.app|update` vào danh sách cho phép.
- `infra/terraform/environments/staging-ha/crawler.tf`, `crawler-startup.sh` — thêm: VM crawler `vota-ha-crawler`.
- `infra/terraform/environments/staging-ha/crawler_monitor.tf` — thêm: instance group, health check TCP 8765, backend service, firewall cho dải LB Google, biến `monitor_host`, `crawler_monitor_public`.
- `infra/terraform/environments/staging-ha/main.tf` — thêm: host rule `monitor.praxis.io.vn` trên URL map `vota-ha-app`; block origin HTTPS (cert Cloudflare Origin CA, https proxy, forwarding rule 443) đã có trong working tree local.
- `infra/terraform/environments/staging-ha/variables.tf`, `secrets.tf` — thêm: biến và data source origin TLS.
- `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` — thêm: `create_crawler_vm`, `crawler_monitor_public`.

## Deploy thực tế (không qua CI)

- Build image từ worktree với `docker buildx build --platform linux/amd64 -f Dockerfile.fresh-catalog --push`.
- Tag: `asia-southeast1-docker.pkg.dev/vinpearl-508801/v-ota/vota-fresh-catalog:readonly-f23574ed-202610091347`
- Digest: `sha256:936d84fd726243640c53e1ac1d3f069b64dd28a7505c9a6b11b0476a6db2185c`
- Deploy: `GCP_PROJECT_ID=vinpearl-508801 CRAWLER_INSTANCE=vota-ha-crawler CRAWLER_ZONE=asia-southeast1-a CRAWLER_REF=<digest> bash scripts/deploy-staging-ha-crawler.sh` → `DEPLOY_RC=0`.
- `terraform apply` (đã áp dụng trước đó): `4 added, 1 changed, 0 destroyed` (LB monitor, URL map).

## Kiểm tra

- Local: `monitor.py --read-only`: GET 200, POST 405. `test_monitor_storage.py`, `test_monitor_backend_calls.py`: 7 passed. `test_runner_fresh_monitor.py` fail có sẵn do `stat -c` (GNU) trên macOS, không liên quan thay đổi này.
- `terraform validate` trong worktree: pass.
- VM: monitor `vota-fresh-catalog-monitor` Up; `ss` cho thấy `0.0.0.0:8765`; `curl` trên loopback và IP nội bộ 200.
- Backend LB `vota-ha-crawler-monitor`: HEALTHY (sau khi health check TCP đạt 2 lần liên tiếp).
- `https://monitor.praxis.io.vn/`: GET 200, tiêu đề `V-OTA · Fresh catalog`; POST `/api/stop` 405.
- DNS `monitor.praxis.io.vn`: Cloudflare proxy (đã do người vận hành cấu hình).

## Rủi ro và việc còn lại

- **CI/CD lần sau sẽ ghi đè và có thể làm hỏng monitor** nếu merge `release-mvp-v2` như hiện tại:
  - `scripts/deploy-staging-ha-crawler.sh` trên remote vẫn chạy monitor loopback, không có `MONITOR_READ_ONLY`, và vẫn `chown` thư mục dữ liệu sang user SSH → cron lỗi `exit=3` như lần đầu.
  - Secret `STAGING_HA_TFVARS` chưa có `crawler_monitor_public = true`, nên plan sẽ tính xoá LB monitor (guard chặn, CD lỗi).
  - Config trên remote không khớp hạ tầng đang chạy: plan tính tạo 55 resource (Patroni, Redis, DNS `db`...). Biến `origin_tls_enabled` chưa khai báo trên remote.
  - Drift `ssh-keys` trên VM crawler: apply sẽ xoá key do `gcloud compute ssh` thêm vào.
- Image deploy thủ công không qua CI. Cần thay bằng image CI build khi code được merge.
- Chưa commit, chưa push, chưa mở PR. Chưa tắt VM cũ `vota-backend-crawler-recsys` (còn RUNNING, không có container).
- Chưa tạo PRD cho dashboard công khai (đã chọn không tạo).
- Cần quyết định: đưa block origin HTTPS vào PR cùng monitor; cập nhật secret `STAGING_HA_TFVARS`; sau đó merge `release-mvp-v2`.
