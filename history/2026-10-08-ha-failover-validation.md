# Xác minh triển khai Patroni staging-ha

- Ngày: 2026-10-08
- Tác giả: người dùng / Codex
- Nhánh: `khoa/ha-runtime-bootstrap-fix`
- Trạng thái: hoàn thành
- Phạm vi: infra / docs

## Mục tiêu

Tiếp tục handoff triển khai `staging-ha`: sửa đường clone Patroni theo từng node, đồng bộ password role `replicator` an toàn, reset/rejoin node, kiểm chứng replication/dữ liệu/ILB/failover thật và cập nhật tài liệu mà không can thiệp primary staging cũ, replica staging cũ, app staging hoặc CI/CD.

## File thay đổi

- `docs/guide/van-hanh-db-patroni.md` — sửa: ghi kết quả GCP thật, quy trình password qua stdin, reset/rejoin và giới hạn dữ liệu/RTO.
- `docs/plan/2026-10-07-ha-vung-crawler-rolling.md` — sửa: cập nhật trạng thái apply/runtime, đối chiếu dữ liệu, ILB, DNS và việc còn lại.
- `docs/prd/deployment-plan.md` — sửa: ghi ranh giới state `staging-ha`, điều kiện cutover và rollback có điều kiện.
- `docs/prd/update-archive/2026-10-08-staging-ha-patroni.md` — thêm: lưu đề xuất đã được người dùng chốt và áp dụng.
- `infra/terraform/environments/staging-ha/backend.tf` — thêm: backend/state GCS riêng cho `staging-ha`.
- `infra/terraform/environments/staging-ha/outputs.tf` — sửa: output ILB chịu được trạng thái resource chưa tạo.
- `infra/terraform/environments/staging-ha/patroni-node.sh.tftpl` — sửa: chỉ clone khi đĩa trống, chờ leader cho node `b`, sửa ownership theo UID/GID trong image.
- `infra/terraform/environments/staging-ha/patroni.tf` — sửa: chỉ truyền `patroni_clone_from_host` cho node `a`.
- `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` — sửa: ghi rõ clone host chỉ dùng cho node `a` và lần đầu.
- `infra/terraform/environments/staging-ha/tests/test_resilience.py` — thêm: kiểm tra clone theo node, wait-for-leader và ownership bind mount.
- `history/2026-10-08-ha-failover-validation.md` — thêm: entry này.

## Quyết định

- Vì `pg_basebackup` chỉ là bootstrap một lần, do đó chỉ node `a` nhận `patroni_clone_from_host` mà node `b` chờ leader qua DCS khi đĩa trống, để tránh hai cụm clone cạnh tranh.
- Vì root/state `staging-ha` tách khỏi `infra/staging`, do đó plan/apply của HA không sửa tài nguyên primary/replica/app staging cũ mà CI/CD hiện hữu vẫn giữ nguyên.
- Vì failover GCP đã chuyển leader sang node `b` và node `a` đã trở lại `sync_standby`/`streaming`, do đó cơ chế Patroni + ILB leader-only đã hoạt động; replication lag được ghi nhận là `0`.
- Vì clone/đồng bộ theo một điểm thời gian và `cdp.products` còn `157` dòng khác nội dung, do đó chưa cutover DNS và chưa mở ghi vào HA.
- Vì node replica gọi ILB thấy `in_recovery=true`, do đó đây là hairpin expected của backend leader-only, không dùng kết quả đó để kết luận ILB hỏng; tiêu chí ILB được kiểm từ HA app VM và health check `/primary`.
- Password `replicator` trên node `a` được đọc từ `/etc/vota/patroni.env` và truyền qua stdin; không ghi giá trị secret vào log, argv, history hoặc tài liệu.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s infra/terraform/environments/staging-ha/tests -p 'test_*.py' -v` — **51 tests, PASS**.
- `terraform -chdir=infra/terraform/environments/staging-ha validate` — **PASS**.
- `terraform -chdir=infra/terraform/environments/staging-ha plan -input=false -var-file=staging-ha.tfvars` — lần kiểm tra read-only gần nhất: `No changes. Your infrastructure matches the configuration.`
- `terraform -chdir=infra/terraform/environments/staging-ha plan -input=false -lock=false -no-color -var-file=staging-ha.tfvars` — lần kiểm tra read-only cuối: **No changes**.
- `git diff --check` — **PASS**.
- GCP instances — `vota-ha-pg-a` `10.148.0.35` ở `asia-southeast1-a`, `vota-ha-pg-b` `10.148.0.37` ở `asia-southeast1-b`, `vota-ha-pg-w` `10.148.0.36` ở `asia-southeast1-c`, đều `RUNNING`.
- `gcloud compute ssh ... vota-ha-pg-a ... 'curl /cluster; curl /primary; curl /replica'` — node `a` là `sync_standby`/`streaming`, timeline `3`, lag `0`, `/primary=503`, `/replica=200`.
- `gcloud compute ssh ... vota-ha-pg-b ... 'curl /cluster; curl /primary; curl /replica'` — node `b` là `leader`/`running`, timeline `3`, `/primary=200`, `/replica=503`.
- Patroni — node `b` là `leader`, node `a` là `sync_standby`/`streaming`, timeline `3`, lag `0`.
- ILB — `gcloud compute backend-services get-health vota-ha-pg-primary --region=asia-southeast1` trả VIP `10.148.0.34`, node `b` `HEALTHY`, node `a` `UNHEALTHY` theo thiết kế leader-only.
- App runtime — MIG/backend service `vota-ha-app` có `3/3` VM healthy.
- Failover GCP — thành công; chưa có timestamp start/end đủ tin cậy để công bố RTO chính xác.
- Đối chiếu dữ liệu — `cdp.products`: `old_rows=17679`, `ha_rows=17679`, `same=17522`, `different=157`, `missing_in_old=0`, `missing_in_ha=0`; hash `cdp.profiles` và `catalog.combo_items` khớp.
- DNS — `gcloud dns record-sets list --zone=vota-ha-internal ...` trả `db.vota.internal. A 10.148.0.2`; chưa cutover, chưa mở ghi HA.
- Boundary — không chạy root `infra/terraform/environments/staging`, không reset staging DB cũ, không restart staging app, không sửa `.github/workflows`.

## Còn lại / rủi ro

- Chưa chạy rolling-update drill, scale-in SSE thật, kiểm cảnh báo GCP/Ops Agent hoặc đo RTO bằng timestamp; các mục này không được giả định là đã đạt.
- Chưa xử lý chênh lệch `157` dòng `cdp.products`; giữ nguyên DNS staging cũ và không mở ghi HA cho tới khi có quyết định dữ liệu.
- Không được chạy thêm `terraform apply`, đổi `db.vota.internal` sang `10.148.0.34`, reset node đang là leader, chạy root `infra/terraform/environments/staging` hoặc sửa CI/CD trong phần việc này.
