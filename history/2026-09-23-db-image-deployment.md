# Đóng gói và triển khai PostgreSQL DB image

- Ngày: 2026-09-23
- Tác giả: người yêu cầu / Codex
- Nhánh: dev
- Trạng thái: hoàn thành
- Phạm vi: backend

> Entry này hợp nhất các ghi chép trong `2026-09-23-db-image-bootstrap.md`,
> `2026-09-23-external-vector-db.md`, `2026-09-23-postgres16-image.md` và
> `2026-09-23-bootstrap-role-repair.md`. Quyết định sau cùng là PostgreSQL 16,
> không dùng pgvector; vector do dịch vụ bên ngoài quản lý.

## Mục tiêu

Đóng gói PostgreSQL cùng DDL hiện hành vào Artifact Registry và cung cấp script
có thể chạy trên Debian/Ubuntu Compute Engine VM mới. Database phải giữ dữ liệu
bằng named volume, chỉ bind PostgreSQL vào IP private của VM, và bootstrap schema
phải chạy được cả trên volume mới lẫn database/schema đã tồn tại.

## Quyết định cuối cùng

- Image DB dùng `postgres:16-bookworm`.
- Không cài hoặc yêu cầu pgvector trên VM DB; embedding và ANN index do dịch vụ
  vector bên ngoài quản lý, nối bằng `product_id`.
- PostgreSQL giữ catalog, metadata, CDP, app và Insider.
- Fresh init không gọi `CREATE EXTENSION vector`, không tạo cột `vector(D)` và
  không tạo HNSW index.
- DDL trong `db/init/` vẫn là nguồn sự thật; không đưa `03_roles_dev.sql` vào
  image production.
- Secret PostgreSQL được tạo trên VM với quyền `0600`, không bake vào image.
- Container publish `DB_PRIVATE_IP:5432:5432`; firewall GCP phải giới hạn nguồn
  truy cập ở VPC/backend.
- Named volume mặc định của image cuối là `vota-pg16`; không dùng volume
  PostgreSQL 18/pgvector nếu chưa backup và migrate.
- Bootstrap schema không drop dữ liệu và có bước idempotent tạo các role nền
  `vota_app`, `cdp_reader`, `cdp_writer`, membership và grants.
- Seed catalog/history là bước riêng, không tự chạy khi khởi động DB VM.

## File thay đổi

- `Dockerfile.db` — dùng PostgreSQL 16, copy DDL và lệnh bootstrap vào image.
- `docker-compose.yml` — dùng `postgres:16-bookworm`.
- `ops/bootstrap-db-schema.sh` — bootstrap idempotent cho database/schema mới
  hoặc đã tồn tại; sửa role nền bị thiếu.
- `ops/bootstrap-db-vm.sh` — cài Docker, đăng nhập Artifact Registry bằng VM
  service account, tạo secret/volume/network, chạy container DB và bootstrap.
- `ops/tests/test_db_image.sh` — kiểm tra tĩnh image/bootstrap, base image
  PostgreSQL 16 và bước repair role; không chứa password.
- `.dockerignore` — cho phép Docker build context nhận DDL và script vận hành.
- `db/init/01_vota.sql` — bỏ extension `vector`, bảng
  `catalog.product_vectors` và HNSW index.
- `db/vota_schema.sql` — cập nhật schema không còn phụ thuộc pgvector.
- `src/data_collection/seed/database.py` — bỏ truncate/count bảng vector
  PostgreSQL.
- `src/data_collection/seed/report.py` — bỏ báo cáo bảng vector PostgreSQL.
- `README.md` — cập nhật ranh giới lưu vector bên ngoài.
- `src/backend/README.md` — cập nhật ranh giới lưu vector bên ngoài.
- `src/backend/requirements.txt` — cập nhật dependency liên quan vector.
- `src/backend/app/application/ports/unit_index.py` — cập nhật port vector.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — cập nhật adapter
  vector bên ngoài.
- `src/data_collection/README.md` — cập nhật hướng dẫn dữ liệu/vector.
- `docs/spec/DATABASE_SCHEMA.md` — cập nhật schema DB.
- `docs/spec/MOCK_DATA_SPEC.md` — cập nhật mock data không dùng bảng vector.
- `docs/spec/PRODUCT_SCHEMA.md` — cập nhật product/vector boundary.
- `docs/spec/architecture-repo.md` — cập nhật kiến trúc lưu vector.

## Kiểm tra

- `bash ops/tests/test_db_image.sh` — pass.
- `bash -n ops/bootstrap-db-schema.sh ops/bootstrap-db-vm.sh ops/tests/test_db_image.sh` — pass.
- `git diff --check` — pass.
- `docker compose config` — pass.
- Build local amd64 bằng `docker build --platform linux/amd64 -f Dockerfile.db -t vota-db:pg16-postgres .` — pass.
- Fresh container và named volume cục bộ — PostgreSQL 16 healthy, DDL tạo được
  database/schema, các bảng `cdp.products`, `catalog.combo_items`, `app.users`
  tồn tại, bootstrap lần hai idempotent.
- Test volume đã thiếu role nền — bootstrap tạo lại `vota_app`, `cdp_reader`,
  `cdp_writer` và grants thành công.
- Image local là `linux/amd64`, khoảng 155–159 MB tùy lần build.

## Các giai đoạn và phần còn lại

### Giai đoạn PostgreSQL 18/pgvector ban đầu

Đã thử đóng gói `pgvector/pgvector:0.8.6-pg18-bookworm` và volume `vota-pg18`.
Quyết định này được thay thế bởi PostgreSQL 16 không pgvector. Không mount volume
PostgreSQL 18/pgvector vào image PostgreSQL 16 nếu chưa backup và migrate.

### Artifact Registry và VM

- Image Artifact Registry phải được build/push lại với tag
  `vota-db:pg16`; tag `pg18` không còn dùng.
- VM service account cần `roles/artifactregistry.reader` trên repository và
  OAuth scope đọc Artifact Registry phù hợp.
- Cần cấu hình firewall chỉ cho SSH qua kênh quản trị và TCP 5432 từ backend
  hoặc private VPC; xoá rule mở DB ra Internet.
- Cần chạy job seed riêng nếu VM phải có catalog/demo data.

### Ứng dụng và vector store

- Search/Recsys cần cấu hình endpoint/adapter của dịch vụ vector bên ngoài và
  đồng bộ `product_id`/metadata.
- Tạo các role ứng dụng production riêng sau bootstrap; không dùng role
  `postgres` cho backend.
