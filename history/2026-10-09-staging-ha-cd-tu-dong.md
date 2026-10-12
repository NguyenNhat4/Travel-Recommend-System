# CD tự động lên staging-ha và chuyển crawler sang VM staging-ha

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude Code (thực hiện)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra (staging-ha), CI/CD, docs

## Mục tiêu

Người vận hành yêu cầu chuyển toàn bộ triển khai (frontend, backend, crawler) từ VM staging cũ `vota-backend-crawler-recsys` sang staging-ha, với CD chạy tự động sau push vào `main`, không có bước kiểm tra thủ công.

## Lệch PRD (có chủ đích)

- Người vận hành chọn **không tạo đề xuất PRD** (Cách 1, 2026-10-09). Thay đổi này lệch `docs/prd/deployment-plan.md` §1.1 và §6.1 và **chưa có đề xuất đã chốt**. Đề xuất `docs/prd/update/2026-10-09-cd-staging-ha.md` vẫn ở trạng thái `chờ chốt`, không sửa.
- CD tự động từ push `main`, không có environment reviewer. Lệch Q2 trong `docs/plan/2026-10-09-cd-staging-ha.md` (plan ghi giai đoạn đầu là `workflow_dispatch`). Người vận hành yêu cầu rõ điều này.
- Crawler chạy trên VM riêng `vota-ha-crawler` trong staging-ha (người vận hành chọn). Không dùng MIG.

## File thay đổi

- `.github/workflows/staging-ha-cd.yml` — thêm: job `images` (build và publish backend, frontend, crawler; digest bất biến), `deploy_app` (Terraform qua `scripts/deploy-staging-ha-app.sh`), `deploy_crawler` (qua `scripts/deploy-staging-ha-crawler.sh`), `verify` (MIG stable, `/health/ready` qua `https://praxis.io.vn` liên tiếp 6 lần, VM crawler RUNNING, ghi `last-good`), `rollback` (chỉ khi `deploy_app` hoặc `verify` lỗi).
- `.github/workflows/backend-ci-cd.yml`, `.github/workflows/crawler-ci-cd.yml` — sửa: job `deploy` đặt `if: ${{ false }}`. Job quality, build, publish giữ nguyên.
- `.github/workflows/frontend-ci-cd.yml` — sửa: job `deploy_vm` đặt `if: ${{ false }}`.
- `infra/terraform/environments/staging-ha/crawler.tf` — thêm: biến `create_crawler_vm` (mặc định false), `crawler_zone`, `crawler_machine_type`; resource `google_compute_instance.crawler[0]` (tag `vota-crawler`, không IP public); output `crawler_instance_name`.
- `infra/terraform/environments/staging-ha/crawler-startup.sh` — thêm: cài docker, cron; tạo thư mục dữ liệu. Không cài cron, không chạy job.
- `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` — sửa: thêm `create_crawler_vm = false`.
- `infra/terraform/environments/staging-ha/staging-ha.tfvars` (gitignored, không commit) — thêm `create_crawler_vm = true`.
- `scripts/deploy-staging-ha-app.sh` — thêm: plan Terraform với digest, từ chối plan có thay đổi ngoài `google_compute_instance_template.app`, `google_compute_region_instance_group_manager.app` (update), `google_compute_instance.crawler[0]` (create), rồi apply đúng file plan.
- `scripts/deploy-staging-ha-crawler.sh` — thêm: đăng nhập Artifact Registry trên VM, copy runner, kiểm tra env file tồn tại, cài cron (`install-vota-cron.sh --job fresh`), khởi động monitor với `MONITOR_HOST=127.0.0.1` (VM cũ mở `0.0.0.0`, xem Quyết định).
- Cấu hình ngoài repo: GitHub secret `STAGING_HA_TFVARS` (nội dung `staging-ha.tfvars`, đặt bằng `gh secret set`); GCS object `gs://vinpearl-508801-staging-tfstate/deploy/staging-ha-last-good.json` (digest đang chạy, để rollback).
- Hạ tầng GCP đã thay đổi: tạo VM `vota-ha-crawler` (asia-southeast1-a, e2-medium, IP nội bộ `10.148.0.49`); copy `/etc/vota/fresh-catalog.env` từ VM cũ sang (so sha256 khớp); dừng container `vota-fresh-catalog-monitor`, `vota-frontend`, `vota-backend`, `vota-auth-redis` trên `vota-backend-crawler-recsys` (VM cũ vẫn RUNNING, không còn container).

## Quyết định

- **Monitor job cào** chỉ nghe `127.0.0.1` (mặc định của `run_daily_docker.sh`). VM cũ chạy `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1` và firewall `vota-monitor-8765` mở `0.0.0.0/0`, UI không có đăng nhập. Chuyển sang loopback để không mang rủi ro đó sang môi trường mới. Ai cần xem UI thì SSH tunnel.
- **Không chạy migration DB** từ CD. Workflow `images` **dừng** nếu commit chứa thay đổi trong `db/migrations/`, để không deploy code lệch schema. Đây là quyết định tạm, dựa trên Q3 trong `docs/plan/2026-10-09-cd-staging-ha.md` (chưa chốt). Job deploy cũ đã từng chạy migration trước khi deploy, nên lệnh này bỏ mất bước đó.
- **Rollback** đọc `last-good` từ bucket state và apply lại qua cùng script. Chỉ ghi `last-good` khi `verify` đạt.
- **Lỗi riêng của crawler không rollback app.** `rollback` chỉ chạy khi `deploy_app` hoặc `verify` lỗi.
- **Cutover crawler**: tắt container trên VM cũ trước khi VM mới nhận lịch cron, để không có hai bản cùng ghi catalog. Tại thời điểm cutover, crontab của VM cũ **không có** khối `VOTA CRAWLER` (đã kiểm), nên không có lịch nào bị gỡ.

## Kiểm tra

- `terraform plan` (đọc, trước thay đổi): `No changes`.
- `terraform validate`: `Success! The configuration is valid.`
- `terraform plan` sau khi thêm crawler: `Plan: 1 to add, 0 to change, 0 to destroy` (chỉ `google_compute_instance.crawler[0]`).
- `terraform apply -target='google_compute_instance.crawler[0]'`: `1 added, 0 changed, 0 destroyed`. Đã dùng `-target` vì chỉ muốn tạo VM crawler, không đụng template app.
- `python3 -m` test trong `infra/terraform/environments/staging-ha/tests/`: `test_alerts.py`, `test_egress_and_secrets.py`, `test_health_checks.py`, `test_pgbouncer_setup.py`, `test_resilience.py` — mọi file rc=0.
- Parse YAML của 4 workflow: OK. `bash -n` cho hai script mới: OK.
- Checksum env file sau khi copy: khớp (`9e49e20c…163f35`), quyền `600 root`.
- `gcloud compute instance-groups managed describe vota-ha-app`: `isStable: true` (trước thay đổi).
- Chưa chạy được: `actionlint`, `shellcheck` (không có trên máy).
- Triển khai crawler lên `vota-ha-crawler` (lần cuối): `scripts/deploy-staging-ha-crawler.sh` exit 0; monitor `vota-fresh-catalog-monitor` Up; `curl http://127.0.0.1:8765/` trên VM trả 200; crontab có khối `VOTA CRAWLER` (`*/15`).
- Lỗi đã gặp và sửa trong script trong lúc chạy: (1) thiếu đăng nhập Artifact Registry trên VM mới → thêm bước login; (2) thư mục `/srv/vota/*` do startup tạo bằng root → chown cho user SSH; (3) `/etc/vota/fresh-catalog.env` mode 600 root, cron chạy dưới user SSH → chown + chmod 600 cho user đó (giống VM cũ). Lần đầu chạy lại tôi đọc nhầm exit code qua pipeline; các lần sau kiểm tra trực tiếp.
- Lượt cron đầu tiên (05:00 UTC) **thất bại**, exit 3: container chạy UID 10001 nhưng thư mục `/srv/vota/fresh-catalog-data` đã bị chown sang user SSH, nên `/data/state` báo `Permission denied`. Đã sửa script: thư mục dữ liệu thuộc `10001:10001`, log thuộc user SSH. Đã áp dụng trên VM; `fresh-run status` đọc được, lịch kế tiếp là `full` lúc 12:06 (+07). Lượt cron sau đó chưa được kiểm tra.
- Monitor UI: `V-OTA · Fresh catalog` trả 200 trên loopback của VM và qua SSH tunnel tạm (`-L 18765:127.0.0.1:8765`) từ máy vận hành.
- Dashboard Cloud Monitoring `vota-staging infrastructure` tồn tại (`projects/365721936833/dashboards/61ca957e-…`). Chưa kiểm tra các widget có trỏ tới VM crawler mới hay không.

## Còn lại / rủi ro

- **CD chưa chạy thật.** Workflow chỉ chạy trên push vào `main`. Cần commit, đưa vào `main` (PR) để kích hoạt. Chưa commit (theo quy tắc chỉ commit khi được yêu cầu).
- **Lần CD đầu sẽ rolling update MIG app**: template đang dùng tag, workflow dùng digest, nên template đổi. `max_surge` 3 cần tạm 4 VM app (8 vCPU). Quota asia-southeast1 = 16, cần kiểm trước khi chạy.
- **Crawler mới chưa được xác nhận chạy tick**: monitor đang khởi động (xem lượt kiểm tra sau). Lịch cron `*/15` đã cài.
- **Migration DB**: workflow từ chối deploy nếu có `db/migrations/`. Cần quyết định Q3 để có đường chạy migration tự động.
- **Workflow khác vẫn SSH vào VM cũ**: `monitoring-agent-cd-staging.yml` dùng `GCE_INSTANCE`. Repo variable `GCE_APP_INSTANCE` vẫn trỏ `vota-backend-crawler-recsys`. Chưa sửa.
- **Monitoring**: uptime check và alert crawler (`crawler_monitoring.tf`) dựa trên log crawler, không kiểm tra VM cũ. Chưa kiểm lại sau cutover.
- **VM cũ `vota-backend-crawler-recsys`** vẫn RUNNING nhưng không còn container. Chưa dừng, cần xác nhận riêng.
- Secret `STAGING_HA_TFVARS` đặt từ file local; cần người vận hành xác nhận ai được đọc secret này.
