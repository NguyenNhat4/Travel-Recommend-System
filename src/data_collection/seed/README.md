# data_collection.seed

Loader và mock data tuần 1 cho database `vota` + `insider`. Spec: [`docs/MOCK_DATA_SPEC.md`](../../../docs/MOCK_DATA_SPEC.md),
quy tắc: [`AGENTS.md`](../../../AGENTS.md) §6, schema: [`docs/DATABASE_SCHEMA.md`](../../../docs/DATABASE_SCHEMA.md).

## Chạy

```bash
docker compose up -d --wait postgres          # từ gốc repo, chạy db/init/*.sql
pip install -r src/data_collection/seed/requirements.txt

cd src
python -m data_collection.seed --as-of 2026-09-20 --seed 42 --reset
```

Chạy **từ thư mục `src`** (hoặc `PYTHONPATH=src`). Trên Windows đặt `PYTHONUTF8=1`, nếu không output
tiếng Việt vỡ khi pipe hoặc redirect.

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--as-of` | hôm nay | Ngày nạp. **Mọi thứ có ngày sinh tương đối theo đây**: cửa sổ đặt chỗ, lịch 30 ngày, event lịch sử, chuyến sắp tới của persona |
| `--seed` | 42 | Cùng seed + cùng as-of → cùng dữ liệu, trên mọi máy |
| `--users` | 2000 | Số dòng `cdp.profiles` |
| `--products` | tự dò | `products.jsonl`; không có thì sinh và dùng `products.synthetic.jsonl` |
| `--reset` | tắt | Xoá dữ liệu seed cũ rồi nạp lại. Chặn host không phải localhost trừ khi có `--allow-remote-reset` |

Exit code `1` khi có dòng `verify` FAIL ngoài dự kiến, để CI bắt được.

Kết nối lấy từ env (`.env.example`): `SEED_DATABASE_URL` (superuser — role `vota_app` của
`DATABASE_URL` **không** ghi được `cdp.*`), `INSIDER_DATABASE_URL`, `INSIDER_TOKEN`.

**Chạy lại trước mỗi buổi demo.** Cửa sổ đặt chỗ chỉ dài 30 ngày tính từ `as_of`; không chạy lại thì
toàn bộ catalog hết hạn và trang đặt chỗ trống trơn.

## Sáu bước

| Module | Việc |
|---|---|
| `gen_products.py` | Bước 0, chỉ khi chưa có crawl: sinh `products.synthetic.jsonl` đúng contract `docs/SCHEMA.md` (§1b) |
| `load_products.py` | `products.jsonl` → `cdp.products`; cửa sổ 30 ngày, `attributes.availability`, thuộc tính combo |
| `parse_combos.py` | `description` → `catalog.combo_items` bằng `pg_trgm`, ghi `source`/`confidence`/`evidence` |
| `seed_histories.py` | `cdp.profiles` + `cdp.events`: 2.000 khách, ~7.600 event theo chuyến, power-law Zipf |
| `seed_app.py` | `app.users` (4 persona + 50 test) và `app.bookings` của P1 |
| `seed_insider.py` | Database `insider`: partners, profiles, identifiers, events (TTL 90/730), channel_events |
| `report.py` | Chạy `db/verify*.sql`, đo baseline, ghi khối `seed-report` trong `../README.md` |

Mọi tỷ lệ và phân bố nằm ở **`config.py`** — Evaluation chỉnh ở đó, không đọc code.

Mỗi module tách làm hai nửa: `build_*()` thuần (không chạm database, test offline được) và
`write_*()` mỏng (một transaction, COPY hoặc batch 1.000 dòng). `psycopg` chỉ import trong nửa sau.

## Tài khoản demo

Mật khẩu chung `Demo@2026` (BCrypt cost 10). `minhanh@vota.demo` (P1), `quocbao@vota.demo` (P2),
`thuha@vota.demo` (P3), `khachmoi@vota.demo` (P4), `test01@vota.demo`…`test50@vota.demo`.

## Kiểm tra

`report.py` tự chạy `db/verify.sql` và `db/verify_insider.sql` qua psycopg (không cần cài `psql`).
Chạy tay nếu có psql:

```bash
psql "$SEED_DATABASE_URL"    -f db/verify.sql
psql "$INSIDER_DATABASE_URL" -f db/verify_insider.sql
```

Hai dòng **FAIL theo thiết kế** khi dùng catalog tổng hợp: `products = 2216` và
`is_recommendable properties >= 300`. Đó là ngưỡng của crawl thật (2.216 sản phẩm; 316/559 property
có hạng phòng), còn catalog tổng hợp cố ý nhỏ hơn ~5 lần để chạy nhanh và đọc tay được.
Cùng lý do, baseline Recall@20 cao hơn ngưỡng 0.6. Có `products.jsonl` thật thì chạy lại `--reset`,
cả ba tự về đúng — **không sửa `db/*.sql`** và không hạ `ZIPF_S` để ép chỉ số.

Unit test (offline, không cần database), chạy từ `src/data_collection`:

```bash
python -m unittest discover -s tests -t . -v
```

## Ràng buộc dễ vấp

- Cột GENERATED không bao giờ được liệt kê trong INSERT: `combo_items.combo_taxonomy`,
  `booking_items.line_total`, `insider_events.ttl_days`.
- `cdp.events."timestamp"` là từ khoá SQL — luôn để trong ngoặc kép.
- `combo_items.item_kind` vừa là loại hiển thị vừa là taxonomy trong FK
  `(item_product_id, item_kind) → products (product_id, taxonomy)`, nên `meal`/`transfer`/`other`
  **buộc** phải có `item_product_id = NULL`.
- `verify_insider.sql` dùng `insider_profiles.updated_at` làm **mốc opt-out**, chính xác đến giây.
- Các cast trong view `catalog.product_meta` không có phòng vệ: một `starRating` hay `latitude` sai kiểu
  làm mọi truy vấn trên view lỗi. `gen_products._validate()` chặn trước khi nạp.
