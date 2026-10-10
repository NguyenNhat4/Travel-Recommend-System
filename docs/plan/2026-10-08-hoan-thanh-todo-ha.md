# Kế hoạch hoàn thành todo HA và logging (cập nhật 2026-10-08)

- Ngày: 2026-10-08
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Phục vụ: NFR-REL-02 (kế thừa từ đề xuất `docs/prd/update-archive/2026-10-08-staging-ha-patroni.md`, đã áp dụng); logging theo `docs/spec/logging-schema.md`
- Trạng thái: đang thực hiện
- Thay thế: các ghi chú kế hoạch rải rác trong `history/2026-10-08-*`. File plan `2026-10-07-ha-vung-crawler-rolling.md` vẫn là kế hoạch nền; file này là bản điều hành hiện tại.

## 1. Quyết định đã chốt

| # | Quyết định | Trạng thái |
|---|---|---|
| D1 | Merge `khoa/backend-db-unavailable-degraded` vào nhánh HA | Xong (`00dab1a`) |
| D2 | Email alert: `nguyentrongdangkhoa15@gmail.com` (trong `staging-ha.tfvars`, không commit) | Xong |
| D3 | Xoá `db.pool.exhausted` | Xong (`15b9582`) |
| D4 | Khi stream trợ lý bị đứt: báo lỗi có hướng dẫn, không tự nối lại | Xong (`2f98761`) |
| D5 | Quyền GCP: đã đủ | Xong |
| D6 | Secret `vota-ha-backend-env` do người vận hành nạp | Có phiên bản 5–9; nội dung chưa kiểm |
| R | Readiness HA: VM mất DB trả 503 để LB loại VM đó | Chốt (giữ hành vi HA) |
| A | Di trú DB theo hướng A: lấy dữ liệu từ primary cũ `10.148.0.2` sang cụm HA | Chốt, chưa thực hiện |
| M | Quy tắc số máy: DB = 1 primary + 1 replica + 1 witness (3 máy); app = **min 1, max 2 VM** | Chốt; đang áp dụng |

Lý do M: tổng máy DB hiện là 5 (3 HA + primary cũ + replica cũ của `staging`). Ngân sách kết nối với 4 VM app là 106 > `max_connections` 100 của primary cũ. Với 2 VM là 2 × 2 × 12 + 10 = 58, đạt.

Hệ quả đã chấp nhận: `min = 1` nghĩa là mất VM app duy nhất là mất dịch vụ app. Ràng buộc `min >= 2` và công thức `cpu_target <= (N-1)/N` đã được gỡ khỏi `variables.tf` có chủ đích.

## 2. Ràng buộc kỹ thuật đã biết

- Regional MIG trên 3 zone chỉ nhận `max_unavailable` = 0 hoặc ≥ 3; `max_unavailable_percent` không được phép. Vì vậy không thể thay từng VM một bằng cấu hình MIG. Rolling update cần `max_surge` ≥ 3 hoặc chấp nhận thay đồng thời.
- Hạn mức `CPUS_ALL_REGIONS` = 16, không tăng được.
- Primary cũ có `max_connections = 100`.

## 3. Trạng thái theo phase

### Phase 1 — việc trong repo: hoàn thành
- [x] 1.1 Commit node `a` clone, node `b` chờ leader (`9dece87`)
- [x] 1.2 Đổi tên `widgetProgress.ts` → `widgetProgressView.ts` (`15b9582`); vitest 717 test PASS
- [x] 1.3 Bỏ `db.pool.exhausted` (`15b9582`)
- [x] 1.4 Log-opts compose HA và script bootstrap DB (`15b9582`)
- [x] 1.5 Ghi trạng thái logging (`2f98761`)
- [x] 1.6 Merge D1 (`00dab1a`); test backend unit toàn bộ: 1834 PASS, 2 skip
- [x] 1.7 Test Patroni failover và clone trên Docker: PASS
- [x] D4 báo lỗi SSE (`2f98761`)

### Phase 2 — hạ tầng `staging-ha`: đang làm
- [x] 2.1 `terraform plan` đã xem xét
- [x] 2.2 Apply template mới có log-opts (`1 added, 1 changed, 1 destroyed`)
- [ ] Rolling update `vota-ha-app` chưa `isStable`. Nguyên nhân chưa xác định. Ba VM mới HEALTHY ở LB; MIG đang thu về theo `max_replicas = 2`.
- [x] Đổi `min_replicas` = 1, `max_replicas` = 2; gỡ ràng buộc (N-1)/N; apply (chỉ autoscaler và hai alert policy)
- [x] Dừng `vota-ha-app-5v5g`, `vota-ha-app-xstn`, `vota-ha-app-jlb1`, `vota-ha-pg-a`
- [ ] Dừng `vota-ha-pg-b`, `vota-ha-pg-w` (bị chặn; lệnh người vận hành tự chạy trong `history/2026-10-08-dung-vm-staging-ha-giai-phong-quota.md`)
- [x] 2.4 Kết nối và xác thực DB từ VM HA: OK (`vota_db_dev@db.vota.internal`)
- [x] 2.4 Ngân sách kết nối với 2 VM: 58 ≤ 100 (`ops/check-db-direct.sh` VMS mặc định đã đổi 4 → 2)
- [x] Đổi cụm DB HA sang 1 vCPU / 1 GB (`e2-custom-1-1024`): pg-a, pg-w, pg-b; switchover pg-b → pg-a có kế hoạch; etcd 3/3; `terraform plan` No changes (`history/2026-10-08-db-ha-1vcpu-1gb.md`)
- [ ] 2.5 Ops Agent trên VM app: bị chặn, app VM dùng Container-Optimized OS (không hỗ trợ). Metric memory của autoscaler không có dữ liệu. Ops Agent đang chạy trên `pg-a`, `pg-b`.
- [ ] 2.6 `terraform plan` cho `infra/monitoring`: bị chặn, cần bucket state (`backend.staging.hcl`) và `staging.tfvars` thật
- [ ] Đo `boot_to_ready_seconds`; chỉnh ngưỡng alert theo số đo
- [ ] Xác nhận nội dung secret `vota-ha-backend-env` (phiên bản 9) có đủ khoá theo `src/backend/app/core/config.py`

### Phase 3 — di trú DB, hướng A: chưa bắt đầu
Điều kiện trước khi làm:
- [ ] Người vận hành chọn thời điểm cửa sổ dừng ghi trên primary cũ `10.148.0.2`
- [ ] Xác định VM chạy cron crawler (repo không ghi rõ tên)
- [ ] Xác định `vota-backend-env` có đang ghi vào primary cũ không
- [ ] Rolling update app đã ổn định (hoặc chấp nhận trạng thái hiện tại)

Các bước (mỗi bước có lệnh cụ thể khi đến lượt):
1. Dừng ghi: cron crawler, backend ghi vào primary cũ
2. Đặt `patroni_clone_from_host = "10.148.0.2"`; xoá PGDATA cụm HA để clone lại (không hoàn tác được; cần xác nhận)
3. Clone lại; kiểm tra `cdp.products` khớp primary cũ
4. Cutover `db.vota.internal` → ILB `10.148.0.34`
5. `ops/check-db-direct.sh` sau cutover
6. Mở lại app và crawler; theo dõi `/health/ready`
7. Đường quay lại: DNS `db.vota.internal` về `10.148.0.2` (ghi nhận điểm dữ liệu trước khi quay lại)

### Phase 4 — kiểm chứng: chưa bắt đầu
- [ ] Stack Docker đầy đủ: đăng nhập → tìm kiếm → checkout → trợ lý
- [ ] Lượt cào thật; metric `exit_code=3` không đếm đôi
- [ ] Chi phí Cloud Logging sau 7 ngày
- [ ] Rolling-update drill và k6 (`ops/loadtest/`)

## 4. Việc người vận hành tự làm

- Dọn file tạm trên máy và VM `vota-ha-app-jg7z`:
  ```bash
  gcloud compute ssh vota-ha-app-jg7z --zone=asia-southeast1-c --project=vinpearl-508801 --tunnel-through-iap --command 'rm -f /tmp/vota_db_pw /tmp/vota_db_user /tmp/check-db-direct.sh'
  rm -f /tmp/vota_db_pw /tmp/vota_db_user
  ```
- Dừng `vota-ha-pg-b` và `vota-ha-pg-w` (nếu vẫn muốn): xem entry dừng VM.

## 5. Rủi ro còn mở

- Mất VM app duy nhất là mất dịch vụ app (chấp nhận theo M).
- Xoá PGDATA cụm HA ở Phase 3 không hoàn tác được.
- `vota-ha-pg-b` (leader) đang RUNNING; nếu dừng cùng `vota-ha-pg-w`, cụm HA không đủ quorum. Cụm HA hiện không nhận traffic.
- Secret chưa kiểm nội dung.
- Đề xuất PRD đã áp dụng ghi đường dẫn `infra/staging-ha`; đường dẫn đúng là `infra/terraform/environments/staging-ha`.

## 6. Cập nhật cuối phiên 2026-10-08

Đã xong:
- Phase 3 (di trú DB hướng A): clone từ primary cũ, kiểm số dòng và checksum khớp, cutover `db.vota.internal` → `10.148.0.34`, crawler và app đọc/ghi qua cụm HA. Chi tiết: `history/2026-10-08-phase3-di-tru-db.md`.
- Gỡ `patroni_clone_from_host` khỏi tfvars (sớm hơn runbook, để tránh clone lại từ primary cũ). `terraform plan`: No changes.
- Đo `boot_to_ready` của VM app: khoảng 170 giây từ lúc VM start đến `startup.complete` của backend (15:16:06 → 15:18:56 UTC, `vota-ha-app-1z6c`). Đây là số đo một lần, chưa phải phân phối.
- Smoke test sau cutover: `/health/ready` 200 trên app VM, `/search` 200 với dữ liệu thật, backend crawler đọc được `products=17679`.
- Lịch nhắc kiểm chi phí Cloud Logging sau 7 ngày: `ha-logging-cost-check-7d`, chạy 2026-10-15 09:17 (+07).

Còn mở (kèm lý do):
- 2.5 Ops Agent trên VM app: không cài được vì app VM dùng Container-Optimized OS. Autoscaler vẫn scale theo CPU. Metric memory giữ nguyên theo quyết định của người vận hành.
- 2.6 `terraform plan` cho `infra/monitoring`: cần bucket state và `staging.tfvars` thật (uptime host, email). Repo không có các giá trị này.
- Hai khóa `STRIPE_WEBHOOK_SECRET` trùng trong secret `vota-ha-backend-env` (dòng 69 và 79) có giá trị khác nhau (hash prefix `3ada3460…` và `e236462d…`). Cần người vận hành xác nhận giá trị đúng, vì không kiểm tra được từ repo.
- Cổng monitor `8765` trên crawler mở `0.0.0.0/0` (firewall `vota-monitor-8765`), và đang nhận kết nối bị reset từ IP ngoài. Cần quyết định có thu hẹp nguồn không.
- Rolling-update drill và k6 (`ops/loadtest/`): chưa chạy. Quota CPU 16/16 vẫn là rủi ro cho surge khi rolling update.
- Nghỉ hưu primary cũ: để sau khi cụm ổn định vài ngày. Primary hiện đang read-only, làm hàng rào chống split-brain.

Không tạo PR, không commit theo yêu cầu.

- [x] 2.6 monitoring plan xong (0 add, 24 change cosmetic, 0 destroy); xem history/2026-10-08-monitoring-staging-plan.md

## 7. Cập nhật 2026-10-09: Giai đoạn 1–5 của lộ trình

Đã xong:
- App VM chuyển sang Debian 12 + Ops Agent (phương án A). Autoscaler đọc được `agent.googleapis.com/memory/percent_used`, `statusDetails` trống. Chi tiết: `history/2026-10-09-app-debian-ops-agent-va-hoan-tat-todo-ha.md`.
- `boot_to_ready` đo trên Debian: ~230 giây (tạo VM → `startup.recsys.ready`), đặt 300 giây.
- `infra/monitoring`: apply 24 thay đổi cosmetic. Còn churn `dashboard_json` của provider, không ảnh hưởng.
- Test API frontend: 43/43 pass. Smoke test LB công khai: 200.

Còn mở:
- E2E có xác thực (đăng nhập, checkout, trợ lý) trên staging: cần tài khoản test thật từ người vận hành.
- Lượt cào thật: lượt 08/10 bị ngắt do dừng VM crawler (đã ghi nhận). Kiểm lại ở lượt 10/10 (lịch `ha-crawler-run-verify-2026-10-10`).
- Chi phí Cloud Logging 7 ngày: lịch `ha-logging-cost-check-7d` (15/10).
- Rolling-update drill với k6: xem history 09/10.
- Nghỉ hưu primary cũ `10.148.0.2`: sau khi cụm ổn định; replica staging vẫn stream từ primary cũ.
