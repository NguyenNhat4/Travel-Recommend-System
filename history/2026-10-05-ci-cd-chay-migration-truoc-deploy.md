# CI/CD tự áp migration trước khi deploy Backend

- Ngày: 2026-10-05
- Tác giả: người dùng / Claude
- Nhánh: worktree-ci-migrate-before-deploy
- Trạng thái: hoàn thành
- Phạm vi: backend (hạ tầng CI/CD)

## Mục tiêu

Log staging có `booking.guest_merge.failed` status 500 lặp lại; nghi ngờ migration `0007_booking_drafts` (nhánh `feat/booking`) chưa áp lên DB vì pipeline chưa có bước migration, dù `docs/prd/deployment-plan.md` §6.1 quy định "DB Migration" trước "Deploy Backend". Hiện thực đúng bước đó. (Người dùng đã tự áp 0007 bằng tay trên staging; thay đổi này đảm bảo các lần deploy sau tự migrate.)

## File thay đổi

- `Dockerfile.backend` — sửa: COPY `db/migrations` vào image để runner chạy trong image sắp deploy.
- `.dockerignore` — sửa: `db` bị loại hẳn khỏi build context, thêm ngoại lệ cho `db/migrations` (`.sql` và `run.py`).
- `scripts/deploy-backend-vm.sh` — sửa: thêm `--migrate-dsn-stdin` (đọc DSN một dòng từ stdin) và `--skip-migrate` (loại trừ nhau; thiếu cả hai khi không dry-run thì từ chối). Sau `pull`, trước `up --force-recreate`, chạy `SEED_DATABASE_URL=… docker run --rm --network host -e SEED_DATABASE_URL <image> python db/migrations/run.py`.
- `.github/workflows/backend-ci-cd.yml` — sửa: thêm `db/migrations/**` vào `paths` của push và pull_request; kiểm tên secret; bước deploy đọc DSN từ Secret Manager (`vota-migrate-database-url`, đổi bằng biến `GCE_MIGRATE_DB_SECRET`) rồi đẩy qua stdin của `gcloud compute ssh`.
- `scripts/tests/test-backend-vm-cd-sync.sh` — sửa: kiểm migration có mặt, chạy trước bước recreate, DSN đi qua stdin, đọc từ Secret Manager, không có `--env-file`.
- `docs/guide/env-secret-manager.md` — sửa: thêm mục tạo secret DSN migration và cấp quyền cho service account của CI.

## Quyết định

- Chạy migration trên VM ứng dụng (đã có tunnel tới DB riêng, `network_mode: host`), bằng chính image digest sắp deploy, nên không cần mở DB ra runner GitHub.
- DSN nằm trong GCP Secret Manager, CI đọc bằng danh tính Workload Identity (cùng cách `.github/actions/sync-env-from-secret-manager`; VM không cần quyền Secret Manager) rồi truyền qua stdin của SSH; không nằm trong argv của lệnh từ xa, không ghi file trên VM. `docker run -e NAME` không kèm giá trị nên DSN cũng không hiện trong `ps`. Thay cho hai phương án đã cân nhắc: file `/etc/vota/migrate.env` và GitHub secret.
- Khác các secret env khác (thiếu biến thì bỏ qua), bước này fail-closed: thiếu/rỗng/sai định dạng thì dừng deploy trước khi đụng VM, vì mục đích là bảo đảm luôn migrate.
- Role trong DSN cần quyền tạo bảng trong schema `app` (như `SEED_DATABASE_URL`), khác `DATABASE_URL` của backend (`db/migrations/README.md`).
- Migration lỗi thì dừng trước khi đụng container đang chạy, nên không cần rollback. Migration idempotent và chỉ thêm, nên rollback image sau đó vẫn chạy được (deployment-plan §6.2).
- Không lệch PRD: chỉ hiện thực bước đã ghi ở §6.1.

## Kiểm tra

- `bash -n scripts/deploy-backend-vm.sh`: pass.
- `bash scripts/tests/test-backend-vm-cd-sync.sh`: pass.
- Chạy thử các nhánh tham số: dry-run in dòng migration; thiếu cờ bị từ chối; hai cờ loại trừ; stdin không phải DSN bị từ chối; `--skip-migrate` không in dòng migration.
- `docker build -f Dockerfile.backend` thành công; trong image `ls db/migrations` thấy `0001`–`0006`, `README.md`, `run.py`.
- Chưa chạy workflow và chưa chạy trên VM thật.

## Còn lại / rủi ro

- **Phải làm trước khi merge**: tạo secret `vota-migrate-database-url` (một dòng `postgresql://USER:PASS@127.0.0.1:15432/vota`, cổng theo `GCE_DB_TUNNEL_PORT`) và cấp `secretmanager.secretAccessor` cho service account của CI (lệnh ở `docs/guide/env-secret-manager.md`). Thiếu thì job deploy dừng ở bước deploy, trước khi đụng backend. Quyền chưa nằm trong Terraform.
- `db/migrations/0007_booking_drafts.sql` chỉ có ở `feat/booking`; phải vào nhánh release. 0007 đã được áp tay, nên `run.py` sẽ bỏ qua nó nếu checksum khớp bản trong repo; lệch checksum sẽ báo lỗi.
- Nếu role trong DSN không đủ quyền tạo bảng trong schema `app`, migration sẽ lỗi và deploy dừng.
