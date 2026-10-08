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
- [ ] 2.5 Ops Agent trên VM staging: chưa làm
- [ ] 2.6 `terraform plan` cho `infra/monitoring` (import `_Default`): chưa làm
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
