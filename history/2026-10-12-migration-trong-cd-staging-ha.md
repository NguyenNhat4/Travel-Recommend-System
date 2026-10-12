# Migration DB chạy trong CD staging-HA bằng role vota_migrator

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), theo lựa chọn của người vận hành (mục 1 role DDL riêng, mục 2 runner vào DB)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành (còn việc theo dõi lần CD đầu tiên, xem "Còn lại")
- Phạm vi: infra

## Mục tiêu

Guard ở `staging-ha-backend-build.yml` chặn mọi commit có thay đổi `db/migrations` vì CD chưa chạy migration. Migration `0010_combo_only_va_price_share.sql` (PR #162) đang làm build fail. Cần CD tự áp migration còn thiếu trước khi deploy.

## Thay đổi trên DB và Secret Manager (đã thực hiện ngoài git)

- Role mới `vota_owner` (NOLOGIN) và `vota_migrator` (LOGIN, thuộc `vota_owner`). Mật khẩu sinh ngẫu nhiên, chỉ lưu trong Secret Manager.
- `ALTER SCHEMA app/catalog OWNER TO vota_owner`; mọi bảng, view, sequence và foreign table trong `app` và `catalog` đổi owner sang `vota_owner` (trước đó owner là `postgres` hoặc `vota_db_dev`). Quyền đã cấp (ví dụ `GRANT ... TO vota_app`) không đổi.
- `GRANT CREATE ON DATABASE vota TO vota_owner` (runner chạy `CREATE SCHEMA IF NOT EXISTS app` và bị từ chối nếu thiếu).
- `GRANT USAGE ON SCHEMA cdp` và `GRANT SELECT ON cdp.products` cho `vota_owner`.
- Secret Manager `vota-ha-migrate-database-url` (version 1): DSN `postgresql://vota_migrator:…@db.vota.internal:5432/vota?sslmode=prefer`. Quyền `secretAccessor` cho `github-ci-cd-v-ota-backend@vinpearl-508801.iam.gserviceaccount.com`.
- Secret cũ `vota-migrate-database-url` (dùng cho deploy VM) không đổi.
- Kiểm tra: `vota_migrator` đăng nhập được qua TCP trên leader; migration `0010` chạy thành công trong transaction và đã ROLLBACK, không đổi dữ liệu.

## File thay đổi

- `.github/workflows/staging-ha-backend-cd.yml` — thêm bước `Apply pending DB migrations` trong job deploy, trước `Apply backend image`: đọc DSN từ Secret Manager, tạo venv và cài `psycopg`, chạy `db/migrations/run.py --status` rồi `run.py` (chỉ áp migration chưa có trong `app.schema_migrations`).
- `.github/workflows/staging-ha-backend-build.yml` — bỏ bước `Refuse to deploy a schema change without a migration step`.

## Quyết định

- Migration chạy trước apply để code mới không chạy trên schema cũ. Nếu migration lỗi, job deploy dừng trước khi đổi MIG.
- DSN không đi qua argv và không in ra log (được mask). Biến `SEED_DATABASE_URL` export trong cùng bước vì `GITHUB_ENV` chỉ có hiệu lực ở bước sau.
- Dùng role có quyền hạn hẹp, không dùng superuser `postgres` hay `vota_db_dev`.

## Kiểm tra

- YAML của hai workflow parse được (`yaml.safe_load`).
- Probe thủ công: `vota_migrator` chạy `CREATE SCHEMA IF NOT EXISTS app`, `CREATE TABLE IF NOT EXISTS app.schema_migrations`, `INSERT` vào bảng tracking, và toàn bộ `0010_combo_only_va_price_share.sql` trong một transaction rồi ROLLBACK: thành công.

## Còn lại / rủi ro

- Lần CD đầu tiên sau khi push sẽ áp `0010` lên DB staging-HA. Migration này thay view `catalog.product_meta` và thêm cột `price_share` (đã tồn tại trong DB nên nhánh `ADD COLUMN IF NOT EXISTS` bỏ qua).
- Giả định `github-ci-cd-v-ota-backend` là `GCP_CI_SERVICE_ACCOUNT`; giá trị secret GitHub không đọc được để xác minh.
- Runner `vota-ci-runner` cần `python3 -m venv` và truy cập `db.vota.internal:5432` (firewall đã thêm tag `ci-runner` ở commit trước).
- Migration chưa được cài qua Terraform; secret và role nằm ngoài IaC.
- Các object mới do `vota_owner` tạo ra không tự thừa hưởng quyền cho `vota_app`; migration sau cần tự `GRANT`.
- Lần chạy đầu cần theo dõi job `Apply pending DB migrations`. Nếu lỗi, job dừng trước khi deploy, không cần rollback DB vì migration nằm trong transaction.
