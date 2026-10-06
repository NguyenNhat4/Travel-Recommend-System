# Dựng snapshot CDP bổ sung để tqanh đo RecSys

Dữ liệu demo ngày 05/10/2026, phục vụ FR-CDP-01/03, FR-REC-01/02. Đọc kết quả nạp và caveat tại
`src/evaluation/reports/eval-2026-10-05-cdp-append-recsys-handoff.md`.

Chạy từ repo root trên nhánh `bench_search_recomSys`, dùng Python có requirements của seed và harness.
`SEED_DATABASE_URL` phải trỏ **database local mới, rỗng** do bạn tạo trước; không dùng staging.
Đoạn dưới kiểm checksum rồi áp DDL và nạp snapshot trong một transaction; database đã có bảng sẽ bị từ chối.
Không cần Insider, tài khoản app hay mật khẩu staging trong snapshot.

```bash
PYTHONPATH=src python - <<'PY'
import gzip, hashlib, json, os
from pathlib import Path
import psycopg
from data_collection.seed.database import copy_rows, PRODUCT, PROFILE, EVENT
root = Path('src/data_collection/snapshots/2026-10-05-recsys-append-v1')
manifest = json.loads((root / 'manifest.json').read_text())
for name, info in manifest['files'].items():
    packed = (root / name).read_bytes()
    assert hashlib.sha256(packed).hexdigest() == info['sha256'], name
    assert hashlib.sha256(gzip.decompress(packed)).hexdigest() == info['uncompressed_sha256'], name

def read(name):
    return json.loads(gzip.decompress((root / name).read_bytes()))

names = dict(productId='product_id', unitPrice='unit_price', availableFrom='available_from',
             availableTo='available_to', imageUrl='image_url', sourceRef='source_ref')
products = [{names.get(k,k):v for k,v in r.items()} for r in read('catalog.json.gz')]
with psycopg.connect(os.environ['SEED_DATABASE_URL']) as conn:
    exists = conn.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema IN ('cdp','app','catalog'))").fetchone()[0]
    if exists:
        raise SystemExit('Cần database mới, rỗng; không ghi lên database đang sử dụng')
    conn.execute(Path('db/vota_schema.sql').read_text())
    for table, columns, rows in [('products', PRODUCT, products),
                                 ('profiles', PROFILE, read('profiles.json.gz')),
                                 ('events', EVENT, read('events.json.gz'))]:
        print(table, copy_rows(conn, 'cdp.' + table, columns, rows))
    conn.execute("SELECT setval(pg_get_serial_sequence('cdp.events','event_id'),(SELECT max(event_id) FROM cdp.events))")
    conn.execute('ANALYZE')
PY
```

Đây là database **đánh giá CDP/catalog**, không phải DB demo toàn app: không chứa combo_items hay tài khoản/đơn.
Các kiểm tra booking trong `db/verify.sql` không áp cho bản dựng rút gọn này; kết quả verify trên staging đủ app nằm trong report.

Cấu hình `DATABASE_URL` (role `vota_app`) và `EVAL_DATABASE_URL` (role `cdp_reader`) trỏ database vừa dựng.
Login role local theo `db/init/03_roles_dev.sql`; harness không cần dùng superuser.
Tại máy Khôi, bản đã dựng là `vota_append_eval_20261005` trên Postgres local cổng 55433.

```bash
export RECSYS_HOME=bench_out/recsys-append-20261005
# Tái kiểm/sinh split với tên mới nếu thay snapshot; không ghi đè đề thi cũ.
for sp in llbo temporal nexttrip coldstart; do
  python -m src.evaluation.recsys_bench split --kind "$sp" --as-of 2026-10-05 --refresh \
    --freeze-path "src/evaluation/recsys_bench/frozen/split-$sp-append-v1-asof20261005.json"
done
```

Chuẩn bị vector **khớp 14.702 sản phẩm của snapshot này**: dùng `--vectors numpy` nếu collection Weaviate chứa đủ search unit đúng
model/text version, hoặc `--vectors npy:<prefix>` với bộ vector đã sinh từ catalog này. Không mặc định tái dùng e5-small của catalog 30/09.
`vectorsMissing` phải bằng 0 trước khi dùng số để kết luận; luôn ghi modelVersion, configHash, split hash và commit vào report.
E5-small chỉ dùng làm arm nghiên cứu cho tới khi đề xuất PRD được chốt.

```bash
# Đặt V thành chế độ vector đã kiểm coverage; ví dụ numpy cho collection tương ứng.
: "${V:?Cần đặt V thành chế độ vector đã kiểm tra}"
for sp in nexttrip temporal llbo coldstart; do
  SF="src/evaluation/recsys_bench/frozen/split-$sp-append-v1-asof20261005.json"
  python -m src.evaluation.recsys_bench run --arm engine --arm most_popular_in_destination \
    --split "$sp" --as-of 2026-10-05 --vectors "$V" --split-file "$SF" \
    --run-id "20261005-append-v1-$sp-engine"
  python -m src.evaluation.recsys_bench compare --run-id "20261005-append-v1-$sp-engine" \
    --base engine --ref most_popular_in_destination
  python -m src.evaluation.recsys_bench run \
    --algos src/evaluation/recsys_bench/algos_v1.yaml --max-tier 2 --mode funnel \
    --funnel-pool mask --funnel-rerank none --funnel-rerank mmr \
    --split "$sp" --as-of 2026-10-05 --vectors "$V" --split-file "$SF" \
    --run-id "20261005-append-v1-$sp-cf-funnel"
  python -m src.evaluation.recsys_bench run \
    --algos src/evaluation/recsys_bench/algos_v1.yaml --max-tier 2 --mode raw \
    --split "$sp" --as-of 2026-10-05 --vectors "$V" --split-file "$SF" \
    --run-id "20261005-append-v1-$sp-cf-raw"
done
```

Không đặt `--limit-users 200` cho lượt kết luận. Báo riêng cohort `VPX:20261005-recsys-v1:` và khách cũ nếu phân tích được;
không trộn số trước/sau từ hai đề thi khác nhau thành mức cải thiện thuật toán. Phân tầng `targetInOwnHistory`/`targetInOwnCart`,
đặc biệt coldstart vốn có tín hiệu xem/giỏ rất mạnh. Số synthetic chỉ hỗ trợ kiểm thử và so sánh trong giả định generator.
