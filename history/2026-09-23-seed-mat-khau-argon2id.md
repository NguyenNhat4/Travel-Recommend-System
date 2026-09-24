# Seed băm mật khẩu demo bằng Argon2id ngay từ đầu

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người dùng: "seed dữ liệu đang bcrypt cũ nên phải có 1 bước để hash, nên là từ bước seed ta nên chuẩn Argon2id". Trước đây `seed_histories.py` ghi một hash BCrypt cost 10 dùng chung cho 54 user. Backend phải băm lại lần đăng nhập đầu, và plan còn dự tính thêm `seed_auth.py` chỉ để đặt lại 4 persona.

Thay đổi này không lệch PRD (PRD không quy định thuật toán băm), chỉ sửa spec và code seed. Phục vụ FR-USR-01, NFR-SEC-01.

## File thay đổi

- `src/data_collection/seed/config.py` — sửa: `DEMO_PASSWORD_HASH` (BCrypt) → `DEMO_PASSWORD = "Demo@2026"` cùng tham số `ARGON2_*` giống backend.
- `src/data_collection/seed/seed_histories.py` — sửa: thêm `demo_password_hash(user_id)` (Argon2id, salt tất định); `app.users.password_hash` dùng hàm này; sửa docstring và dòng report.
- `src/data_collection/seed/requirements.txt` — sửa: `bcrypt>=4.1` → `argon2-cffi>=23.1`.
- `src/data_collection/tests/test_seed_histories.py` — sửa: kiểm tiền tố `$argon2id$v=19$m=19456,t=2,p=1$`, mỗi user một hash khác nhau, verify được `Demo@2026`, và tái lập được.
- `.env.example` — sửa: gỡ khối `AUTH_TEST_PASSWORD_P1..P4` (không nơi nào dùng) và ghi chú về mật khẩu demo chung.
- `docs/spec/hop-dong-tich-hop-auth.md` — sửa: §8.2 ghi seed đã là Argon2id; đường bcrypt chỉ còn cho DB seed trước ngày này.
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: `app.users` băm Argon2id thay BCrypt.
- `docs/spec/DATABASE_SCHEMA.md` — sửa: §8 thứ tự nạp, bỏ bước `seed_auth`.
- `docs/plan/2026-09-23-auth-p0.md` — sửa: bước 4 xong, bỏ `seed_auth.py`; kỳ vọng integration test đổi thành `needs_rehash = false`.
- `history/2026-09-23-seed-mat-khau-argon2id.md` — thêm: entry này.

## Quyết định

- **Salt tất định theo `user_id`** (`sha256("vota-seed-salt|" + user_id)[:16]`), không ngẫu nhiên. Seed phải tái lập được byte-for-byte giữa các lần chạy, và mỗi user vẫn có salt riêng. Chỉ chấp nhận được vì mật khẩu demo vốn công khai; mật khẩu người dùng thật vẫn do backend băm với salt ngẫu nhiên.
- **Tham số giống hệt backend** (m=19456 KiB, t=2, p=1, hash 32 byte) nên `check_needs_rehash` trả `False` và đăng nhập không phải ghi lại hash.
- **Bỏ `seed_auth.py` và mật khẩu riêng từng persona.** Spec auth §4.2 cho `DemoAccountSwitcher` dùng một mật khẩu demo chung, nên mật khẩu riêng sẽ mâu thuẫn với chính spec đó.
- **Giữ đường bcrypt trong backend** (`argon2_hasher.py`) và giữ nguyên comment DDL/`COMMENT ON COLUMN` trong `db/vota_schema.sql`, `db/init/01_vota.sql`, `0001_auth_p0.sql`. Các DB đã seed trước ngày này vẫn có hash BCrypt. Migration `0001` có checksum nên không được sửa.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 src/backend/.venv/bin/python -m pytest -q -p no:cacheprovider data_collection/tests` (từ `src/`): **67 passed**.
- Kiểm chéo bằng `Argon2Hasher` của backend trên hash do seed sinh: verify `Demo@2026` → True, mật khẩu sai → False, `needs_rehash` → False, verify mất khoảng 29 ms.
- Chưa chạy seed trên Postgres thật (chưa `make demo-db`), chưa chạy `db/verify.sql`.

## Còn lại / rủi ro

- Máy đã seed trước ngày này cần `make demo-db` (hoặc `--reset`) để có hash mới. Nếu không, backend vẫn đăng nhập được qua đường bcrypt rồi rehash.
- Seed chậm thêm khoảng 1,6 giây (54 lần Argon2id, mỗi lần khoảng 29 ms).
- Khi mọi môi trường đã seed lại: gỡ đường bcrypt khỏi `argon2_hasher.py`, bỏ `bcrypt` khỏi `src/backend/requirements.txt`, và sửa comment DDL bằng một migration mới.
