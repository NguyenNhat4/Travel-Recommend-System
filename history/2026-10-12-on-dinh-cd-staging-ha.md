# Ổn định CD staging-ha: bỏ lịch tắt, tách Docker credentials theo job, runbook, cập nhật PRD

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu "khắc phục 13 vấn đề") / Claude Code (agent)
- Nhánh: khoa/on-dinh-cd-staging-ha
- Trạng thái: dang dở (code xong, test cấu trúc qua; chưa chạy trên CI)
- Phạm vi: infra (CI/CD staging-ha), docs
- Liên quan: `2026-10-12-cd-zero-downtime-slot.md`, `2026-10-12-khoi-phuc-concurrency-staging-ha.md`, `2026-10-12-allowlist-resource-policies.md`

## Việc đã làm ngoài mã (23:31 VN, theo chỉ đạo "services chạy 24/7")

Lần CD tối nay áp `resource_policies` (PR #178 cho phép trong allowlist) nên lịch tắt 23:59 / bật 08:30 đã được gắn lại vào bastion, crawler và 3 node Patroni, trong khi staging-ha phải chạy 24/7. Đã gỡ trực tiếp bằng `gcloud compute instances remove-resource-policies` cho 5 VM (`vota-ha-pg-a/b/w`, `vota-ha-bastion`, `vota-ha-crawler`); thao tác tại chỗ, không khởi động lại VM. Kiểm tra: cả 7 VM `vota-ha-*` `RUNNING`, cột `RESOURCE_POLICIES` rỗng. Job Cloud Scheduler tắt app (`resize-zero`, `autoscaler-off`, `crawler-extra-*`) đang `PAUSED`; `alert-mute-on/off` còn `ENABLED` (chỉ tắt cảnh báo ban đêm).

## File thay đổi

- `infra/terraform/environments/staging-ha/{bastion,crawler,patroni,weaviate}.tf` — sửa: bỏ dòng `resource_policies`, ghi chú 24/7. Các resource policy trong `scheduler.tf`/`crawler.tf` giữ nguyên (không gắn), tránh kế hoạch xoá resource bị cổng plan chặn.
- `.github/workflows/staging-ha-backend-build.yml`, `staging-ha-frontend-build.yml`, `staging-ha-crawler-cd.yml` — sửa: bước "Isolate Docker credentials per job" đặt `DOCKER_CONFIG` riêng cho từng job, trước bước đăng nhập registry.
- `scripts/deploy-staging-ha-app.sh` — sửa: thông báo của cổng plan trỏ tới runbook.
- `docs/prd/deployment-plan.md` — sửa §6.1 bước 3: mô tả cơ chế slot/không gián đoạn, thay quyết định "chấp nhận downtime" 2026-10-09. Theo chỉ đạo trực tiếp, không qua đề xuất `docs/prd/update/`.
- `docs/guide/van-hanh-cd-staging-ha.md` — thêm: runbook (cơ chế, sự cố thường gặp, kiểm tra nhanh, giới hạn).
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — thêm: `AlwaysOn`, `DockerCredentialsPerJob`.

## Nguyên nhân của lỗi 403 khi đẩy image frontend (giả thuyết mạnh, chưa kiểm trực tiếp)

Mọi runner (`vota-ci-runner-2/3/5/6`...) chạy trên cùng VM `vota-ci-runner`, cùng HOME `/home/runner`, nên cùng `~/.docker/config.json`. `docker/login-action` ghi đăng nhập vào file đó và bước post của nó `docker logout` xoá; build backend và frontend chạy song song (22:16–22:17) nên `docker logout` của job này xoá đăng nhập đang dùng của job kia. Lần sau không lặp lại là vì lần đó hai job không chồng nhau.

## Kiểm tra

- `terraform fmt -check`: OK. YAML ba workflow: OK. `bash -n`: OK. `pytest infra/terraform/environments/staging-ha/tests`: 113 passed.
- `terraform plan` chỉ đọc trên nhánh này (tfvars của repo, last-good refs): `1 to add, 2 to change, 1 to destroy` = template (create,delete), MIG (update), dashboard (update); không còn thay đổi `resource_policies`. Cổng plan mô phỏng: PASS.
- Chưa chạy trên CI thật; chưa kiểm cơ chế `DOCKER_CONFIG` riêng trên hai build song song.

## Còn lại / cần quyết định

- WAL archive hoặc tăng `max_slot_wal_keep_size` cho Patroni: thay đổi cấu hình DB, chưa làm.
- PR #186 (khôi phục concurrency): chưa merge; merge khi không có deploy nào đang chạy.
- Fleet lệch image: cần một deploy sạch (lệnh nền đang chờ run `…7524` xong rồi dispatch).
- `google_monitoring_dashboard.ha` luôn hiện một thay đổi `update` trong mọi plan; nguyên nhân chưa tìm.
- Hai job `alert-mute-on/off` vẫn bật; bỏ nếu cũng muốn nhận cảnh báo ban đêm.
