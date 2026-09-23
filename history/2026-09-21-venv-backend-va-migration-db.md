# Venv cho backend và hệ migration cho database

- Ngày: 2026-09-21
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: backend, database, docs

## Mục tiêu

Người yêu cầu: tạo venv trong backend, làm hệ migration cho database, rồi áp lên Docker.

Lý do cần migration: `db/init/*.sql` chỉ chạy **một lần**, lúc Docker khởi tạo volume rỗng. Bước 2 của
`2026-09-21-auth-p0-contract-va-database.md` thêm `app.refresh_tokens` và `app.login_attempts` vào
`db/init/01_vota.sql`, nhưng mọi máy đã seed sẽ không bao giờ thấy hai bảng đó — backend sẽ lỗi
"permission denied"/"relation does not exist" ngay lần đăng nhập đầu tiên. Trước thay đổi này, cách duy
nhất là `docker compose down -v` rồi seed lại 10.320 sản phẩm.

## File thay đổi

- `src/backend/requirements.txt` — sửa: thêm `argon2-cffi`, `bcrypt`, `PyJWT[crypto]`, `redis` (auth P0).
- `db/migrations/README.md` — thêm: quan hệ giữa `db/init/` và `db/migrations/`, quy tắc idempotent, quy ước tên file, lệnh.
- `db/migrations/0001_auth_p0.sql` — thêm: `app.refresh_tokens`, `app.login_attempts`, cột `app.users.email_verified_at`, GRANT cho `vota_app`.
- `db/migrations/run.py` — thêm: runner (discover, checksum, apply, `--status`, `--dry-run`).
- `db/init/01_vota.sql` — sửa: thêm bảng `app.schema_migrations`, đặt **sau** khối GRANT.
- `db/vota_schema.sql` — sửa: y hệt (hai file vẫn byte-identical).
- `docker-compose.yml` — sửa: cổng host của postgres/redis đổi được qua `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT`, mặc định giữ nguyên 5432/6379.
- `Makefile` — sửa: thêm `db-migrate`, `db-migrate-status`; `demo-db` và `demo-db-reset` gọi `db-migrate`; DSN local theo `POSTGRES_HOST_PORT`.
- `AGENTS.md` — sửa: §1.2 thêm `db/migrations/README.md`; §6 mở đầu, §6.3 (staging cloud) và §6.5 mục 1 hòa giải với hệ migration.
- `README.md` — sửa: mục "Đổi schema database"; mục "Chạy Backend" dùng venv riêng và ghi chú kích thước torch.
- `docs/DATABASE_SCHEMA.md` — sửa: §11 thêm ghi chú hai đường dựng schema.
- `history/2026-09-21-venv-backend-va-migration-db.md` — thêm: entry này.

Không tạo: `src/backend/.venv/` (đã có trong `.gitignore` dòng 16).

## Quyết định

- **Runner SQL thuần, không Alembic, cho database `vota`.** Repo **đã có** Alembic ở `src/cdp_clone/`
  (`alembic.ini`, `migrations/env.py`, `versions/0001_events_profiles.py`) — nhưng đó là service đang **tạm gác**
  (`AGENTS.md` §6.1, `src/cdp_clone/README.md`), trỏ vào database riêng ở cổng 5433, và `env.py` của nó lấy schema
  từ `src.cdp_clone.app.infrastructure.tables.metadata`, tức **một định nghĩa schema thứ hai** song song với
  `db/init/01_vota.sql`. Hai bản đã lệch: `unit_price` là `Float` vs `numeric(14,2)`, `purchased_verticals` là
  `JSON` vs `text[]`, `event_id` là `String(128)` vs `bigserial PRIMARY KEY`, `lifecycle_stage` không có CHECK.
  Đó chính là thứ cần tránh cho `vota`.
  Lý do kỹ thuật cho `vota` cụ thể: schema này nặng về thứ Alembic autogenerate không mô hình hóa được — đếm trên
  DB thật có **3 view, 5 partial index, 30 CHECK, 76 GRANT**, mà GRANT là ranh giới `cdp_writer`/`vota_app` theo
  `AGENTS.md` §6.1. Dùng Alembic thì phần lớn vẫn phải `op.execute(...)`, cộng thêm một metadata phải tự giữ đồng bộ.
  Thêm nữa `db/init/` buộc phải là nguồn sự thật cho database mới (§6.5 mục 1) và cho staging cloud (§6.3), nên
  Alembic không thể sở hữu việc tạo schema mà không phá hai quy tắc đó.
  `AGENTS.md` §6.5 vốn cấm "tạo bảng bằng ORM/migration khác" — đã sửa lại thành cấm **ORM**, còn migration SQL
  viết tay là đường bổ sung cho `db/init/`, không thay nó.
  **Đánh đổi đã chấp nhận:** mất branching (DAG `down_revision`) và `downgrade()` của Alembic. Số thứ tự tuyến tính
  sẽ đụng nhau nếu hai người cùng thêm `0002`. Muốn có DAG mà vẫn một nguồn sự thật thì cho Alembic chạy file SQL
  thuần bằng `op.execute(Path(...).read_text())` — chưa làm, người yêu cầu chốt giữ runner hiện tại.
- **Hai đường, một schema.** `db/init/` dựng database mới; `db/migrations/` cập nhật database đã có. Mọi migration
  phải idempotent nên chạy trên database mới cũng an toàn (no-op, chỉ ghi nhận). Đã kiểm bằng cách so schema của
  hai đường — giống hệt.
- **`app.schema_migrations` đặt sau khối GRANT** trong `db/init/01_vota.sql`: `vota_app` không được sửa lịch sử
  migration của chính nó. Runner chạy bằng `SEED_DATABASE_URL` (superuser), đúng phân vai "job hạ tầng, không
  phải code app" của `AGENTS.md` §6.1.
- **Migration phải GRANT tường minh.** `GRANT … ON ALL TABLES IN SCHEMA app` trong `db/init/` chỉ áp cho bảng tồn
  tại lúc nó chạy. Bảng thêm qua migration không được bao. Thiếu dòng GRANT trong `0001` thì backend gặp
  "permission denied for table refresh_tokens" ngay lần đăng nhập đầu.
- **Checksum chặn sửa file đã áp.** Sửa một migration đã chạy ở máy khác làm lịch sử không còn tin được; runner
  báo lỗi và bắt thêm file mới.
- **Runner bọc transaction, file không được tự `BEGIN`/`COMMIT`.** Đây là lỗi đã gặp thật lúc chạy (xem dưới);
  thêm guard báo lỗi rõ ràng thay vì để psycopg ném "savepoint _pg3_1 does not exist".
- **Cổng host đổi được.** Máy này đang có `build-phase-db-1` (postgis, project khác) giữ 5432, nên compose của
  repo không lên được. Mặc định vẫn 5432 nên không ai bị ảnh hưởng.

## Lỗi gặp khi chạy thật, đã sửa

`0001_auth_p0.sql` ban đầu có `BEGIN;` … `COMMIT;`. `run.py` dùng `conn.transaction()` (savepoint), nên `COMMIT`
trong file đóng transaction của psycopg giữa chừng và lệnh giải phóng savepoint thất bại:
`savepoint "_pg3_1" does not exist`. Đã bỏ `BEGIN`/`COMMIT` khỏi migration và thêm guard trong `discover()` chặn
mọi file chứa `BEGIN;`/`COMMIT;`/`ROLLBACK;` (bỏ qua phần trong comment).

## Kiểm tra

Postgres của repo chạy trên cổng 5433 (`POSTGRES_HOST_PORT=5433`) vì 5432 đang bị project `build-phase` chiếm.
Không đụng vào container/volume của project đó.

- `docker compose config` → **VALID**.
- `diff db/init/01_vota.sql db/vota_schema.sql` → **không khác biệt**.
- Volume `travel-recommendation-product_pgdata` tồn tại nhưng **rỗng** (products=0, profiles=0, users=0), nên initdb
  chạy với `db/init/*.sql` bản mới → tạo đủ bảng auth + `schema_migrations`, không ERROR/FATAL.
- Runner trên `vota`: `--status` báo 1 chờ → áp xong → chạy lại **no-op** → `--status` báo 1 đã áp, 0 chờ.
- **Kiểm đường migration thật** trên database `vota_migtest` dựng từ `git show HEAD:db/init/01_vota.sql` (bản
  **trước** auth), có sẵn 1 dòng `app.users`:
  - trước: `refresh_tokens=f, login_attempts=f`, không có cột `email_verified_at`;
  - sau khi áp: cả hai bảng có, cột có, **dữ liệu cũ còn nguyên** (`users sau = 1, email=minh.anh@example.com`);
  - `vota_app` có `SELECT,INSERT,UPDATE,DELETE` trên cả hai bảng mới.
- **So hai đường dựng schema** (`vota` từ initdb-mới vs `vota_migtest` từ cũ+migration): cột, index và constraint
  của schema `app` **giống hệt nhau** (diff rỗng cả ba).
- Guard `BEGIN/COMMIT`: file thử chứa `BEGIN;` → runner báo `bỏ BEGIN — run.py đã tự bọc transaction`, không chạy.
- Phát hiện drift: thêm một dòng vào `0001` đã áp → runner báo lỗi, exit 3; khôi phục file → chạy lại bình thường.
- `make db-migrate-status POSTGRES_HOST_PORT=5433` → chạy đúng.
- Database test `vota_migtest` đã xoá sau khi kiểm.
- `validate_contract.py` không chạy lại: thay đổi lần này không đụng contract hay mock.

## Còn lại / rủi ro

- **Máy này chỉ có Python 3.14.7**, không có 3.10–3.13, không có conda. `requirements.txt` cài được (torch 2.14.0
  có wheel cp314) nhưng tải ~554 MB nên lần đầu rất lâu. Repo ghi "Python >= 3.10"; chưa ai kiểm repo này trên 3.14,
  nên có thể còn lỗi tương thích chưa lộ ra.
- **Cổng 5432 đang bị project `build-phase` chiếm.** Postgres của repo hiện chạy ở 5433, nên `.env`/`.env.example`
  (`localhost:5432`) đang trỏ nhầm sang database của project kia. Người dùng cần chọn: dừng container kia, hoặc
  đặt `POSTGRES_HOST_PORT=5433` và sửa các DSN trong `.env` cho khớp.
- **Volume của repo rỗng** — chưa có catalog. Cần `make demo-db` (bung snapshot 10.320 sản phẩm) trước khi chạy
  backend hay test integration.
- Chỉ có migration `0001`; các bảng P1/P2 của auth (`email_verifications`, `mfa_credentials`, `mfa_recovery_codes`,
  `oauth_identities`) sẽ là `0002`… khi làm tới pha đó.
- Runner chưa có `down`/rollback. Cố ý: rollback tự động trên database có dữ liệu thật dễ mất dữ liệu hơn là cứu;
  sai thì viết migration mới sửa tiếp.
- Bước 3–7 của kế hoạch auth P0 (port `ensure_profile`, domain/application, `seed_auth.py`, route FastAPI, BFF, test)
  vẫn chưa làm.
- **Metadata của `src/cdp_clone/` lệch với `db/init/01_vota.sql`** (chi tiết ở mục Quyết định). Người yêu cầu chốt
  phạm vi "chỉ làm backend, không đụng phần khác" nên **không sửa**; ghi lại đây để người sau biết cái bẫy đó có thật.
- Chưa commit, chưa push.
