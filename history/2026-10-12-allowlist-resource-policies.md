# Thêm bastion và crawler (resource_policies) vào allowlist của cổng deploy staging-ha

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/allowlist-resource-policies
- Trạng thái: hoàn thành (sửa cổng); apply thật xảy ra ở lần CD kế tiếp
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-10-12-cd-zero-downtime-slot.md`, `2026-10-12-staging-ha-cd-allowlist-patroni.md`

## Mục tiêu

Lần deploy đầu sau PR #176: Frontend CD thành công, nhưng Backend CD `38264278540` lỗi ở cổng plan của `scripts/deploy-staging-ha-app.sh` vì plan có `google_compute_instance.bastion[0]|update`, chưa có trong allowlist. Rollback cũng dừng ở cùng cổng; chưa có gì được apply.

## Nguyên nhân

Commit `a8ef14f3` (lịch tắt 23:59, bật 08:30) khai `resource_policies` cho bastion, crawler và Patroni. Các policy (`vota-ha-{bastion,crawler,patroni}-schedule`) đã có trong GCP nhưng state của VM có `resource_policies = []`. Plan đọc-chỉ (tfvars của repo, last-good refs) cho `0 add, 6 change, 0 destroy`; chỉ thuộc tính `resource_policies` đổi trên 5 VM, và `dashboard_json` của dashboard. Patroni a/b/w và dashboard đã có trong allowlist từ trước.

## File thay đổi

- `scripts/deploy-staging-ha-app.sh` — sửa: thêm `google_compute_instance.bastion[0]|update` và `google_compute_instance.crawler[0]|update`, kèm chú thích.

## Quyết định

- Thêm vào allowlist, theo yêu cầu. Thay đổi lên VM là đúng ý của commit `a8ef14f3`, không phải thay đổi mới.

## Kiểm tra

- `bash -n`: OK. Mô phỏng cổng bằng logic của script trên plan đã lưu: 6 thay đổi đều nằm trong allowlist, PASS.
- `pytest infra/terraform/environments/staging-ha/tests`: pass.

## Còn lại / rủi ro

- **Hệ quả khi CD apply:** bastion, crawler và 3 node Patroni (cả `pg-a`, `pg-b` và witness) sẽ được gắn lịch và bị **tắt lúc 23:59 mỗi đêm**, bật lại 08:30. DB staging sẽ ngừng qua đêm. Đây là ý của `a8ef14f3` nhưng chưa từng được áp dụng lên các VM này; cần chắc rằng app và Weaviate/Redis chịu được DB tắt ban đêm.
- VM `fn9m` đã sang slot, `9bbx` vẫn kiểu cũ (Backend CD chưa roll được): fleet đang lệch image tới khi Backend CD chạy lại.
