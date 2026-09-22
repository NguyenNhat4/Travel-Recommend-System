# Migration cho database `vota`

`db/init/*.sql` chỉ chạy **một lần duy nhất**, lúc Docker khởi tạo volume rỗng. Database nào đã có dữ liệu
— máy dev đã seed, hoặc Postgres cloud dùng làm staging — sẽ không bao giờ thấy bảng mới nếu chỉ sửa `db/init/`.
Thư mục này là đường thứ hai: áp thay đổi schema lên database **đang có dữ liệu**, không xoá gì.

## Quan hệ với `db/init/`

`db/init/01_vota.sql` vẫn là **nguồn sự thật cho một database mới** (`AGENTS.md` §6.5 mục 1: không tạo bảng bằng ORM).
Migration không thay nó — hai đường phải cho ra **cùng một schema**:

| Tình huống | Đường đi |
|---|---|
| Volume rỗng (`docker compose down -v`, máy mới, CI) | initdb chạy `db/init/*.sql` → schema đầy đủ. Runner sau đó ghi nhận các migration là đã áp (no-op). |
| Database đã có dữ liệu (máy dev đã seed, staging cloud) | `make db-migrate` áp phần còn thiếu, giữ nguyên dữ liệu. |

Vì vậy **mọi migration phải idempotent**: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`,
`CREATE INDEX IF NOT EXISTS`, `DO $$ … END $$` có kiểm tra cho constraint. Chạy lại lần hai không được lỗi.

## Sửa schema: làm cả hai bên trong cùng commit

1. Sửa `db/init/01_vota.sql` **và** `db/vota_schema.sql` (hai file phải giữ byte-identical).
2. Thêm `db/migrations/NNNN_<slug>.sql` làm đúng việc đó theo cách idempotent.
3. Cập nhật `docs/DATABASE_SCHEMA.md` §4 (ERD), §7 (bảng) và §11 (DDL) — `AGENTS.md` §6.
4. Chạy `make db-migrate` rồi `make verify-db`.
5. Ghi entry trong `history/`.

Bỏ bước 1 thì máy mới sẽ thiếu bảng. Bỏ bước 2 thì máy đang chạy sẽ thiếu bảng. Phải có cả hai.

## Lệnh

```bash
make db-migrate                 # áp phần còn thiếu lên Postgres Docker local
make db-migrate-status          # xem đã áp gì, còn gì
```

Chạy tay trên database khác (ví dụ staging cloud):

```bash
python db/migrations/run.py --database-url "$SEED_DATABASE_URL" --status
python db/migrations/run.py --database-url "$SEED_DATABASE_URL"
```

Runner cần quyền tạo bảng trong schema `app` → dùng `SEED_DATABASE_URL` (superuser), **không** dùng
`DATABASE_URL` của backend. Đây là job hạ tầng, không phải code app.

## Quy ước tên file

`NNNN_<slug>.sql`, bốn chữ số tăng dần, không bao giờ đổi tên hay sửa nội dung một file đã áp ở đâu đó —
runner lưu checksum và sẽ báo lỗi nếu file đổi sau khi đã áp. Cần sửa thì thêm migration mới.

## Bảng theo dõi

`app.schema_migrations(version, checksum, applied_at, applied_by)`. Bảng này do runner tự tạo, và cũng
có trong `db/init/01_vota.sql` để database mới có sẵn.
