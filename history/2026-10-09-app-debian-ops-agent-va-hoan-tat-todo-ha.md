# App VM chuyển sang Debian 12 + Ops Agent; hoàn tất todo HA (Giai đoạn 1–5)

- Ngày: 2026-10-09
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở (xem "Còn lại"; drill và các số đo cần kiểm lại sau)
- Phạm vi: infra (`infra/terraform/environments/staging-ha`, `infra/monitoring`), GCP `vinpearl-508801`. Không đổi mã ứng dụng.
- Liên quan: `history/2026-10-08-db-ha-1vcpu-1gb.md`, `history/2026-10-08-phase3-di-tru-db.md`, `history/2026-10-08-monitoring-staging-plan.md`, `docs/plan/2026-10-08-hoan-thanh-todo-ha.md`

## Mục tiêu

Hoàn thành các todo còn mở của plan HA, theo lộ trình đã đề xuất. Trọng tâm: autoscaler `vota-ha-app` cần metric memory của VM (`agent.googleapis.com/memory/percent_used`), mà Ops Agent không chạy được trên Container-Optimized OS. Người vận hành yêu cầu giữ metric memory, không bỏ khỏi autoscaler.

## Quyết định: đổi boot image sang Debian 12 (phương án A)

- `variables.tf`: `boot_image` = `projects/debian-cloud/global/images/family/debian-12` (trước là `cos-stable`).
- `startup.sh.tftpl` viết lại cho Debian:
  - cài `docker.io`, `jq`, `curl`, `iptables`, `python3` qua apt; `systemctl enable --now docker`;
  - cài Ops Agent từ repo chính thức (`add-google-cloud-ops-agent-repo.sh --also-install`), bỏ qua nếu đã active;
  - thay `docker-credential-gcr` bằng `docker login` với access token của service account (`oauth2accesstoken`);
  - giữ nguyên logic lấy secret, JWT, frontend.env, pgbouncer, compose.
- Service account app (`365721936833-compute@`) đã có `monitoring.metricWriter` và `logging.logWriter`, không cần đổi IAM.

## Kiểm chứng trên VM thử

VM `vota-ha-app-debian-test` (Debian 12, `e2-standard-2`, cùng mạng/SA với MIG, không có tag `vota-ha-app`, không vào LB) tạo bằng startup đã render từ Terraform:
- `/health/ready` = 200, `{"status":"ok","ready":true,"recsys":true,"db":true}`; `/api/v1/search` = 200.
- Ops Agent `active`; metric `agent.googleapis.com/memory/percent_used` có time series (các state buffered/cached/free/used).
- Thời gian tạo VM → sẵn sàng khoảng 237 giây. VM thử đã xoá sau khi kiểm tra.

## Thay đổi MIG `vota-ha-app`

- `max_surge_fixed` giữ = 3. Đã thử hai phương án khác và bị API từ chối:
  - `max_surge_fixed = 1`: regional MIG 3 zone chỉ nhận 0 hoặc ≥ 3 (API 400).
  - `max_surge_percent = 100`: chỉ dùng được khi size MIG ≥ 10 (API 400).
- Rollout cần tạm 4 VM app (1 cũ + 3 surge) = 8 vCPU. Quota `CPUS_ALL_REGIONS` 16 nên đã **dừng VM `vota-backend-crawler-recsys`** (2 vCPU) trong lúc rollout. Lượt cào lúc đó bị ngắt (xem "Sự cố").
- Rolling update `vota-ha-app` sang template Debian: VM `1z6c` (COS) thay bằng `gsc1` (Debian). `isStable = True`, `versionTarget reached = True`, LB HEALTHY 1/1.
- `boot_to_ready_seconds`: 360 → 300. Validation đổi từ `>= 360` sang `>= 240` theo số đo: `gsc1` tạo VM → `startup.recsys.ready` = 229 giây (lần 2, tính từ start VM = 219 giây). Ghi chú biến trong `variables.tf` cập nhật theo số đo.

## Autoscaler

- Trạng thái sau rollout: `ACTIVE`, `statusDetails` trống (cảnh báo `MISSING_CUSTOM_METRIC_DATA_POINTS` đã hết). Đọc qua REST API vì gcloud bản này không có lệnh autoscalers.
- Cấu hình giữ nguyên: min 1, max 2, CPU target 0.55, memory target 60%.

## Monitoring (`infra/monitoring`)

- `terraform apply` 24 thay đổi in-place (`notification_channels` không đổi nội dung; dashboard `staging_overview` chuẩn hoá `xPos/yPos/lowerBound/style`). 0 add, 0 destroy.
- Plan sau apply còn 1 thay đổi: `dashboard_json` (etag và `style` của provider). Đây là churn do provider chuẩn hoá JSON dashboard, lặp lại mỗi lần plan. Không ảnh hưởng gì; ghi nhận, không xử lý thêm.
- Thêm `infra/monitoring/backend.staging.hcl` vào `.gitignore` (README yêu cầu không commit).

## Sự cố: lượt cào bị ngắt do dừng VM crawler

- Lượt `full-20261008T190007Z-22` (bắt đầu 19:00 UTC 08/10) đang ở bước `trip-hotels.prices`. Heartbeat cuối 01:49 UTC, đúng lúc tôi dừng VM crawler để giải phóng quota. Lượt chết, `full.last_success` vẫn là 07/10.
- Monitor ghi nhận lượt là `stale` (HEARTBEAT_STALE 90 giây). Khoá file và khoá advisory DB được giải phóng khi process chết. Lượt theo lịch kế tiếp sẽ ghi đè `running.json`.
- Dữ liệu: bước `trip-hotels.prices` có thể đã ghi một phần. Lượt sau sẽ làm lại; cần kiểm tra trong lượt 10/10 (đã đặt lịch kiểm tra `ha-crawler-run-verify-2026-10-10`).
- Lỗi `sourceRef/sameAs conflict` ở bước `db` (04/10, 05/10) có trước sự cố này, chưa xử lý.

## Phase 5: kiểm thử

- `npm run test:api` (src/frontend): 7 file, 43 test, tất cả pass.
- Smoke test không xác thực qua LB công khai `34.111.252.145`: `/health/ready`, `/api/v1/search`, `/api/v1/search/suggestions`, `/api/v1/products` đều 200 với dữ liệu thật.
- **Chưa làm được:** E2E đăng nhập → checkout → trợ lý trên staging. Playwright trong repo chỉ mock backend (`page.route`), không test luồng thật. Luồng có xác thực cần tài khoản test thật; không đăng nhập staging bằng mật khẩu seed (chính sách: chỉ cho phép trên localhost).
- Lượt cào thật: xem sự cố ở trên; kiểm tra metric `exit_code=3` đợi lượt 10/10.
- Rolling-update drill với k6: xem mục "Kết quả drill" bên dưới.
- Chi phí Cloud Logging 7 ngày: lịch nhắc `ha-logging-cost-check-7d` (15/10 09:17 +07).

## Còn lại

- Kết quả drill, lượt cào 10/10, chi phí Logging 7 ngày.
- E2E có xác thực: cần tài khoản test thật từ người vận hành.
- Ops Agent trên app VM: đã giải quyết bằng Debian; không còn cần.
- Nghỉ hưu primary cũ `10.148.0.2`: để sau khi cụm ổn định; replica staging vẫn stream từ primary cũ.
- Firewall `vota-monitor-8765` (0.0.0.0/0) và `default-allow-ssh`: giữ nguyên theo chỉ đạo, chưa xử lý.

## Kết quả drill rolling update (2026-10-09)

Chạy `ops/loadtest/ha-rolling-update-drill.sh --yes` (k6 nền, rolling-action replace MIG `vota-ha-app`, mỗi 10 giây đếm backend HEALTHY của LB):

- **Lần 1 (150 VU, `k6-ha.js`, MIN_HEALTHY=1):** thất bại. Một VM e2-standard-2 không chịu nổi 150 VU: error rate 11,26% (ngưỡng <1%), p95 28,66 s (ngưỡng 800 ms). Trong lúc thay, HEALTHY xuống 0 trong một mẫu (~10 giây), có thể do health check của LB bị timeout khi VM quá tải. Chưa xác minh thêm.
- **Lần 0:** không chạy được. Lệnh `gcloud compute instance-groups managed rolling-action replace` không có cờ `--min-ready` ở track GA; đã bỏ cờ (min_ready_sec lấy từ Terraform, 300 giây).
- **Lần 2 (20 VU, `k6-ha-1vm.js`, MIN_HEALTHY=1):** HEALTHY tối thiểu **1** (không có khoảng trống). Lỗi **0,00%** trên 5.776 request. Tiêu chí sẵn sàng đạt. p95 = **4,01 s**, vượt ngưỡng 800 ms. Nguyên nhân đã biết: `/search` gọi Weaviate Cloud ở `eu-central-1` từ VM `asia-southeast1` (xem `docs/spec/bench/search-eval-results.md`), không do rolling update. Ngưỡng độ trễ không đạt được với kiến trúc hiện tại; chưa đổi ngưỡng.

Ghi chú về autoscaler trong lúc drill: k6 150 VU làm autoscaler scale-out lên 2 VM (VM `k2f9`). Autoscaler giữ 2 VM dù CPU đã xuống ~5%, `recommendedSize` vẫn 2 và không có statusDetails. Chưa tìm được nguyên nhân. Đã đặt tạm `max_replicas = 1` qua Terraform để chạy drill (quota: surge 3 cần 8 vCPU), rồi trả về 2 và apply lại (`No changes`).

Thay đổi script/profile (repo): `ops/loadtest/ha-rolling-update-drill.sh` (bỏ cờ `--min-ready`; thêm biến `K6_SCRIPT`), `ops/loadtest/k6-ha-1vm.js` (profile 20 VU).

Việc còn: tìm nguyên nhân autoscaler giữ 2 VM khi CPU thấp; xử lý độ trễ `/search` (vùng Weaviate Cloud hoặc chuyển Weaviate sang cùng vùng); chạy lại drill ở chế độ MIN_HEALTHY=2 khi có quota.
