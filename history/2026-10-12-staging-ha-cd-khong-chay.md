# Điều tra: CD staging-ha không chạy đến cuối

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: release-mvp-v2
- Trạng thái: dang dở (đã tìm ra nguyên nhân; chưa sửa, chờ người dùng chọn hướng xử lý)
- Phạm vi: docs (điều tra CI/CD; không đổi code, workflow, script hay state)

## Mục tiêu

Ghi nhận tình trạng phần CD của staging-ha không chạy đến cuối và tìm nguyên nhân. Người yêu cầu nghi ngờ cơ chế của các workflow.

Thời gian dưới đây lấy từ `gh` (UTC), kèm giờ VN (UTC+7).

## File thay đổi

- `history/2026-10-12-staging-ha-cd-khong-chay.md` — thêm: entry này. Không có file nào khác thay đổi.

## Phát hiện

Có ba cơ chế khiến CD không đi tới bước deploy, và một cơ chế khiến run xanh dù CD không chạy.

### 1. Khung giờ ban đêm: CD bị bỏ qua nhưng run vẫn xanh

- Commit `096a7fff` (2026-10-10) thêm job `window-guard` vào ba workflow CD staging-ha. Job đọc giờ VN; nếu ≥ 23:45 hoặc < 08:40 thì `allowed=false` và các job build, deploy bị `skipped`.
- `window-guard` chạy trên runner tự host `vota-staging-ha`. Commit ghi runner tắt theo lịch ban đêm, nên job này bị xếp hàng. Giờ được đo lúc job **bắt đầu chạy**, không phải lúc push.
- Ví dụ: push lúc 2026-10-10 18:21 UTC (01:21 VN ngày 11/10) tạo run backend `38075415954` và run frontend `38075415943`. `window-guard` chỉ bắt đầu lúc 01:35 UTC (08:35 VN), đọc giờ 08:35 nên `allowed=false`. Build và deploy `skipped`, nhưng run tổng thể kết thúc `success`.
- Không có cơ chế chạy lại. Thông báo "Chạy lại sau 08:40" chỉ nằm trong step summary.

### 2. Cổng phạm vi plan và lệch state Terraform

- `scripts/deploy-staging-ha-app.sh` dừng trước `apply` nếu plan có địa chỉ ngoài allowlist. Rollback chạy cùng script nên cùng bị dừng.
- Log lỗi thật:
  - Run `38217340802` (headSha `222f90c7`, 14:22 VN): `google_logging_metric.ha_alert_mute_job_failed|delete`.
  - Run `38216076601` (headSha `7e60273c`, 14:08 VN): `google_logging_metric.crawler_freshness_heartbeat[0]|delete`.
- Nguyên nhân: state Terraform dùng chung (prefix `infra/staging-ha`) đã được apply từ nhánh `Khoa15/adjust-monitor-staging-ha` bằng lệnh chạy trên máy local, không qua CI (xem `history/2026-10-12-monitor-ha-apply.md`). Commit đang deploy trên `release-mvp-v2` (`222f90c7`, `7e60273c`) không chứa `f664124c` là commit thêm các resource này. Plan vì vậy thấy resource có trong state nhưng không có trong cấu hình và đề xuất xoá. Entry monitor-ha-apply đã ghi là còn drift chưa đồng bộ.
- Run `7dd0a96f` (đã chứa `f664124c`) qua được cổng này lúc 15:52 VN, tại thời điểm ghi entry đang ở bước apply.

### 3. Khoá state Terraform mồ côi

- Run `38222592700` (headSha `a391454a`, 15:16 VN) lỗi `Error acquiring the state lock` sau khi chờ `-lock-timeout=10m`.
- Thông tin lock: `gs://…/infra/staging-ha/default.tflock`, Operation `OperationTypePlan`, tạo lúc 08:03:54 UTC (15:03 VN), người giữ là máy laptop đã chạy apply. Backend GCS của Terraform dùng số generation của object (`1791792234548077`) làm lock ID; trường `ID` trong nội dung lock là `ff92bcb7-…` và `force-unlock` không nhận ID đó.
- Đã kiểm tra: không có tiến trình terraform nào đang chạy trên máy này (chỉ có `terraform-ls` của VS Code). Đã xác nhận trên GCS: lock còn tồn tại sau khi run lỗi kết thúc.

### Đã loại trừ

- Bước `Apply pending DB migrations` lỗi `ensurepip`/`python3-venv` ở run `38214273801` (06:47 UTC). Đã sửa ở `7e60273c` (cài vào thư mục tạm, không dùng venv). Run hiện tại đã qua bước này.
- Crawler CD không gọi Terraform trực tiếp (`scripts/deploy-staging-ha-crawler.sh`), nên không tranh lock với backend. Giả thuyết này bị loại.
- Frontend run `38226976093` đang `queued` vì đợi group concurrency `staging-ha-app` do deploy backend giữ. Đây là hành vi đúng thiết kế, không phải lỗi.

## Kiểm tra

- `gh run list` và `gh run view --json jobs` trên `staging-ha-backend-cd.yml`, `staging-ha-frontend-cd.yml`, `staging-ha-crawler-cd.yml`; `gh run view --log-failed` cho các run lỗi.
- `git merge-base --is-ancestor` để xác định commit nào chứa `f664124c` và `096a7fff`.
- `git log -S ha_alert_mute_job_failed` và `git grep` trên cây hiện tại.
- Không chạy `terraform`, không đổi GCP hay state.

## Quyết định

- Không sửa workflow, script hay state trong lần này. Chờ người dùng chọn hướng xử lý.

## Còn lại / rủi ro

Hướng xử lý đề xuất, chưa thực hiện:

1. **Cổng khung giờ:** hiện bỏ qua âm thầm và báo xanh. Có thể (a) đổi thành lỗi có chủ đích để run đỏ, (b) hoãn deploy tới 08:40 bằng schedule, hoặc (c) đo giờ theo lúc push thay vì lúc job chạy. Cần người dùng quyết định.
2. **Lệch state:** cần một nguồn sự thật. Hoặc mọi commit deploy phải khớp state, hoặc state chỉ được apply qua CI. Drift đã ghi trong `history/2026-10-12-monitor-ha-apply.md` phải được đồng bộ trước khi các nhánh release tiếp tục deploy.
3. **Rollback:** rollback dùng cùng cổng plan và cùng lock nên không cứu được các lỗi trên. Cần một đường rollback không đi qua cổng plan, hoặc chỉ chạy khi lỗi xảy ra sau apply.
4. **Lock mồ côi:** xem mục cập nhật bên dưới — đã gỡ.
5. **Run đang chạy:** `38223117490` (headSha `7dd0a96f`) đang ở bước apply lúc 15:52 VN. Kết quả chưa biết khi ghi entry.

## Cập nhật: đã gỡ lock, còn drift chặn CD

- Run `38223117490` (`7dd0a96f`): bước `Apply backend image` chờ lock 10 phút (08:53:22 → 09:03:41 UTC), lỗi `Error acquiring the state lock`. Rollback chờ lock và lỗi cùng lý do (09:13:55 UTC). Không có thay đổi nào được apply.
- Đã gỡ lock: `terraform force-unlock 1791792234548077` (chạy với `TF_DATA_DIR` ngoài repo, `-lockfile=readonly`) sau khi xác nhận không có tiến trình terraform trên máy và generation của lock object khớp. `default.tfstate` không bị ghi.
- Plan chỉ đọc (`plan` không apply) tại cây hiện tại, với tfvars của repo và last-good refs: `0 to add, 5 to change, 0 to destroy`. Ngoài allowlist của `scripts/deploy-staging-ha-app.sh`:
  - `google_compute_instance.patroni["a"]`, `["b"]`, `["w"]`: chỉ `metadata.startup-script` thay đổi (thêm `metrics_filter` loại `agent.googleapis.com/processes/*`, từ commit `f664124c`).
  - `google_monitoring_dashboard.ha`: chỉ `dashboard_json` thay đổi.
  - Không có thay đổi làm dừng VM (`machine_type`, `scheduling`, `status`).
- Phần `patroni_ops_agent.yaml` đã được ghi trực tiếp lên `pg-a`, `pg-b` qua SSH, ngoài Terraform (xem `2026-10-12-monitor-cat-processes-3-vm.md`), nên state Terraform chưa khớp cấu hình sống. Entry đó ghi rõ: không apply Terraform cho Patroni cho đến khi drift này được xử lý.
- Kết luận: gỡ lock chưa đủ để CD xanh. Cổng plan vẫn sẽ chặn ở lần deploy kế tiếp, cho đến khi drift Patroni/dashboard được giải quyết.
- Run frontend `38226976093` (`74671e98`) đang `queued`; khi chạy sẽ gặp cùng cổng.
- Nhánh `origin/main` và `origin/release-mvp-v1` **không chứa** `f664124c`, nhưng CD staging-ha có trigger trên cả hai. Lần push tiếp theo lên các nhánh này sẽ plan ra việc xoá resource monitor và bị cổng chặn. `origin/release-mvp-v3` không tồn tại.
- Đề xuất cho rollback: không chạy khi lỗi xảy ra trước `apply` (lock, guard), vì khi đó không có gì để hoàn tác và rollback chỉ thêm một lần chờ lock.
- Quyết định còn lại, chưa thực hiện: (a) apply 4 thay đổi trên bằng Terraform và thêm địa chỉ vào allowlist, hoặc (b) đưa `patroni_ops_agent.yaml` và dashboard về trạng thái của state. Cả hai đều chạm DB staging hoặc đổi cấu hình giám sát; chưa làm vì chưa có chấp thuận.
