# Thêm drift Patroni và dashboard vào allowlist của cổng deploy staging-ha

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu "tiếp tục fix") / Claude Code (agent)
- Nhánh: release-mvp-v2
- Trạng thái: dang dở (đã sửa cổng và kiểm plan đã lưu; chưa commit, chưa push, chưa apply)
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-10-12-staging-ha-cd-khong-chay.md` (điều tra nguyên nhân)

## Mục tiêu

CD staging-ha bị cổng plan trong `scripts/deploy-staging-ha-app.sh` chặn vì plan có 4 thay đổi chưa có trong allowlist. Các thay đổi này là chủ đích của commit `f664124c`, và đã được ghi trực tiếp lên `pg-a`/`pg-b` qua SSH. Mục tiêu: để CD áp chúng qua pipeline, không apply tay từ laptop.

## File thay đổi

- `scripts/deploy-staging-ha-app.sh` — sửa: thêm 4 dòng vào `allowed_changes` kèm comment:
  - `google_compute_instance.patroni["a"]|update`
  - `google_compute_instance.patroni["b"]|update`
  - `google_compute_instance.patroni["w"]|update`
  - `google_monitoring_dashboard.ha|update`

## Quyết định

- Chọn thêm allowlist, không revert cấu hình về state. Thay đổi là chủ đích của `f664124c` và đã có trên `pg-a`/`pg-b`; revert sẽ bỏ bộ lọc metric đang chạy mà repo không còn quản lý.
- Không apply Terraform từ laptop. Lần drift này xảy ra chính vì apply tay từ nhánh feature. Để CD apply qua pipeline.
- Không sửa `patroni_ops_agent.yaml` và `dashboard_json`.
- Đã gỡ lock state trước đó (`terraform force-unlock 1791792234548077`), xem entry điều tra.

## Kiểm tra

- `bash -n scripts/deploy-staging-ha-app.sh`: OK.
- Plan chỉ đọc tại cây hiện tại, tfvars của repo, last-good refs: `0 to add, 5 to change, 0 to destroy`. Plan không được apply.
- Mô phỏng cổng bằng đúng logic của script trên plan đã lưu: 5 thay đổi đều có trong allowlist, kết quả PASS. Lưu ý: CI dùng tfvars từ secret, có thể khác bản local; cần xác nhận khi CD chạy thật.
- Đã đọc `/cluster` của Patroni trên `pg-a` (chỉ đọc), xem phần còn lại.

## Còn lại / rủi ro

- **Replica `vota-ha-pg-b` đang lỗi:** timeline 2 trong khi leader `vota-ha-pg-a` ở timeline 5, `lag` khoảng 972 MB (đọc lúc 16:xx VN). DB HA hiện không có failover. Việc này thuộc DB (pg_rewind hoặc basebackup lại replica), chưa làm, cần người DB quyết định.
- **Firewall `patroni_clients`** thêm tag `ci-runner` để mở cổng 5432 cho `vota-ci-runner`. Đã có trong code từ trước, cần xác nhận đây là chủ đích.
- **Chưa commit, chưa push.** `scripts/deploy-staging-ha-app.sh` nằm trong `paths` của backend CD, nên push lên `release-mvp-v2` sẽ kích backend CD. Lần đó sẽ build và deploy backend `7dd0a96f` trở lên, có thể thay MIG template và gián đoạn (`max_surge` = 0).
- `origin/main` và `origin/release-mvp-v1` chưa có `f664124c` và chưa có allowlist này. CD staging-ha có trigger trên hai nhánh này, nên push lên đó sẽ lỗi như trước.
- Allowlist chỉ kiểm địa chỉ và loại action, không kiểm thuộc tính. Với `patroni[*]|update`, mọi thay đổi in-place đều được chấp nhận. Nên thu hẹp nếu có thể.
- Rollback vẫn chạy cả khi lỗi xảy ra trước `apply` (lock, cổng plan). Chưa sửa.
