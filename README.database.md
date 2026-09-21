# vota-schema-bundle · 20/09/2026

## Cách đưa vào repo (một lệnh)

Zip này có layout **trùng với gốc repo**, không có thư mục bọc ngoài. Đứng ở gốc monorepo (nơi có `ARCHITECTURE.md` và `src/`), chạy:

```bash
unzip -o vota-schema-bundle.zip -d .
```

Sau lệnh đó các file nằm đúng chỗ như cây dưới. Ba việc còn lại làm tay vì đụng file có sẵn của repo:
1. Gộp `CLAUDE.database.md` vào `CLAUDE.md` gốc (thêm thành mục "Database"), rồi xoá `CLAUDE.database.md`.
2. Gộp service `postgres` trong `docker-compose.db.yml` vào `docker-compose.yml`, rồi xoá file `.db.yml`.
3. `cp .env.example .env` nếu chưa có `.env`; `README.database.md` và `PROMPT_claude_code.md` không cần commit.

**Không** giải nén vào `src/` — `src/` theo ARCHITECTURE.md §4 chỉ chứa source code; DDL, docs, compose là hạ tầng ở gốc. Phần duy nhất vào `src/` là hai README giữ chỗ (`src/cdp_clone/`, `src/data_collection/seed/`) — code seed sẽ do Claude Code sinh vào `src/data_collection/seed/`.

## Vị trí từng file theo `ARCHITECTURE.md` §4

```text
<repo>/
├── CLAUDE.md                      ← gộp CLAUDE.database.md vào (mục Database)
├── docker-compose.yml             ← gộp service `postgres` từ docker-compose.db.yml
├── .env.example                   ← 7 biến môi trường (xem dưới)
├── db/                            ← MỚI · hạ tầng database, dùng chung cho backend + cdp_clone (cùng database `vota`)
│   ├── init/
│   │   ├── 00_create_insider.sql  ← tạo database `insider`
│   │   ├── 01_vota.sql            ← schema cdp · catalog · app + role cdp_reader/cdp_writer/vota_app
│   │   ├── 02_insider.sql         ← schema cho database `insider`
│   │   └── 03_roles_dev.sql       ← login role dev cho DATABASE_URL / CDP_DATABASE_URL
│   ├── vota_schema.sql            ← bản đọc được của 01 (giải thích, comment)
│   ├── insider_schema.sql         ← bản đọc được của 02
│   ├── verify.sql                 ← chạy sau seed trên `vota`, mọi dòng PASS
│   └── verify_insider.sql         ← chạy sau seed trên `insider`
├── docs/
│   ├── DATABASE_SCHEMA.md
│   ├── PRODUCT_SCHEMA.md
│   ├── MOCK_DATA_SPEC.md
│   └── spec/hop-dong-tich-hop-cdp.md   (đã có sẵn)
└── src/
    ├── data_collection/
    │   └── seed/                  ← README giữ chỗ; Claude Code sinh code theo MOCK_DATA_SPEC §1 (gen_products → seed_insider)
    ├── backend/app/application/ports/{cdp_client,insider_client}.py   ← interface (Protocol)
    ├── backend/app/infrastructure/cdp/local_cdp_client.py            ← SQL trên schema cdp qua CDP_DATABASE_URL
    ├── backend/app/infrastructure/insider/http_insider_client.py     ← httpx → INSIDER_BASE_URL
    ├── cdp_clone/README.md        ← giữ chỗ; CDP clone là database (db/), không phải service; contract ở shared/contracts
    ├── insider_clone/             ← service; DATABASE_URL trỏ database `insider` — KHÔNG chứa DDL riêng
    └── shared/contracts/cdp-clone.openapi.yaml
```

Vì sao DDL để ở `db/` gốc chứ không tách vào từng service:
- `catalog.*` (view `product_meta`, FK của `combo_items`) tham chiếu thẳng `cdp.products` → hai schema bắt buộc cùng một database, không tách file theo service được.
- `docker-entrypoint-initdb.d` chỉ đọc một thư mục, không đệ quy → một chỗ `db/init/` cho cả hai database.
- Ranh giới giữ bằng role + connection: `LocalCdpClient` dùng `cdp_writer` qua `CDP_DATABASE_URL` (không có USAGE trên `catalog`/`app`); phần còn lại của backend dùng `vota_app` qua `DATABASE_URL` (không có quyền trên `cdp.events`/`cdp.profiles`).

`PROMPT_claude_code.md` không cần commit — dán vào phiên Claude Code đầu tiên.

Biến môi trường (`db/init/03_roles_dev.sql` tạo sẵn login role cho dev; đặt trong `.env.example`):

```text
DATABASE_URL=postgresql://vota_app_login:vota@localhost:5432/vota        # backend: catalog + app, chỉ SELECT cdp.products
CDP_DATABASE_URL=postgresql://cdp_client_login:cdp@localhost:5432/vota   # LocalCdpClient: cdp.* — connection riêng, không dùng chung
EVAL_DATABASE_URL=postgresql://cdp_eval_login:eval@localhost:5432/vota   # evaluation: chỉ đọc cdp.*
SEED_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vota     # loader/seed: superuser
INSIDER_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/insider   # chỉ src/insider_clone và seed_insider
INSIDER_BASE_URL=http://localhost:8081                                   # backend → Insider clone qua HTTP
INSIDER_TOKEN=dev-token
```

Vì sao hai database chứ không ba: handbook §6 nói CDP clone là **database** đọc qua interface `CdpClient`, còn Insider clone là **service**. Ranh giới CDP ép bằng role + connection riêng (xem cuối `db/vota_schema.sql`), không cần tách database — tách database sẽ mất FK/view của `catalog` và `app` sang `cdp.products`, và catalog vẫn phải là bảng local để search p95 < 300 ms kể cả khi lên CDP thật.

Local hay cloud: **cả hai, mỗi cái một việc.** Dev chạy local (docker) vì seed là tất định — cùng `--seed 42` cùng `--as-of` cho cùng dữ liệu trên mọi máy, reset thoải mái. Một Postgres cloud có pgvector (Neon, Supabase, RDS…) làm staging chung cho FE/agent/demo và cho evaluation chạy trên cùng một bản dữ liệu; chỉ job seed được reset nó, mỗi lần reset báo trong nhóm. Trên cloud không có `docker-entrypoint-initdb.d`: chạy tay `psql "$URL" -f db/init/01_vota.sql` (bỏ `00_create_insider.sql` nếu provider không cho `CREATE DATABASE` — tạo database `insider` bằng dashboard rồi chạy `02_insider.sql` không có dòng `\connect`), và kiểm tra provider cho `CREATE ROLE` (khối role cuối `01_vota.sql`); không cho thì tạo role bằng dashboard trước.

Kiểm tra sau khi `docker compose up -d postgres`:

```bash
psql postgresql://postgres:postgres@localhost:5432/vota    -c "\dt cdp.* catalog.* app.*"
psql postgresql://postgres:postgres@localhost:5432/insider -c "\dt"
```

Kỳ vọng: vota 15 bảng + 3 view (`catalog.product_meta`, `product_parents`, `search_rows`); insider 5 bảng + view `live_events`.
Tạo lại từ đầu: `docker compose down -v` rồi `up` (initdb chỉ chạy khi volume trống).

Cần sửa `ARCHITECTURE.md` §3 và §9 cho khớp: CDP clone không phải service HTTP có PostgreSQL riêng mà là schema `cdp` trong database `vota`, backend vào qua `CdpClient` với connection riêng (đúng handbook §6 "one implementation now, reading locally"); `products` ở `cdp.products`, `users`/`bookings` ở `app.*`, `product_vectors` ở `catalog.*` — câu "đang chờ xác nhận" đã có câu trả lời. `cdp-clone.openapi.yaml` giữ lại làm contract cho `HttpCdpClient` sau này.
