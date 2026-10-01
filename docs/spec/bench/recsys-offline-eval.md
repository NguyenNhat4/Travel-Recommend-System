# Đánh giá offline engine Recommendation trên DB seed

- Phục vụ: **FR-REC-01..04**, **NFR-PERF-01** (`docs/prd/requirements.md`); `docs/prd/test-plan.md` §2.5; handbook §11–§12.
- Code: `src/evaluation/recsys_bench/` (nhánh `bench/recsys-harness`). Số thô: `bench_out/recsys/runs/<run_id>/` (không commit).
- Thay cho `eval/report.md` của lịch 10 ngày (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md` §0.1).
- Cập nhật lần cuối: 2026-10-02 (§4.14 sau FR-REC-02; 01/10: §2.1 sanity, §3.1 split đóng băng, §4.5 guest path Cloud, §4.6 v3 NDCG@5, §4.7–4.11 ceiling / phân khúc / strict / 20 ca / findings, §4.12 parity offline = HTTP)

> **Caveat bắt buộc (handbook §12):** lịch sử khách hàng là dữ liệu sinh. Các số này cho biết pipeline chạy đúng,
> không cho biết engine sẽ chạy thế nào trên khách thật.

## 1. Cách chạy

Từ gốc repo, Windows đặt `PYTHONUTF8=1`. Harness đọc catalog bằng `DATABASE_URL` (role `vota_app`) và event bằng
`EVAL_DATABASE_URL` (role `cdp_eval_login`, chỉ đọc `cdp.*`). Biến môi trường thắng `.env`, nên muốn chạy trên
Postgres compose local thì truyền DSN local (role dev trong `db/init/03_roles_dev.sql`) thay vì tunnel `15432`.

```bash
docker compose up -d --wait postgres weaviate            # DB đã seed: make demo-db AS_OF=2026-09-24 SEED=42
python -m src.evaluation.recsys_bench doctor               # kết nối, số event, as_of suy ra
python -m src.evaluation.recsys_bench load                 # bảng lọc (mục 2)
python -m src.evaluation.recsys_bench split --kind llbo --freeze   # hoặc --kind temporal [--T …]; --freeze ghi frozen/split-<kind>-asof<YYYYMMDD>.json
python -m src.evaluation.recsys_bench run --arm random --arm most_popular --arm most_popular_in_destination --arm engine --arm engine_prod \
    --split llbo --vectors weaviate --split-file src/evaluation/recsys_bench/frozen/split-llbo-asof20260922.json --run-id 2026-10-01-llbo-v3
python -m src.evaluation.recsys_bench user --id VP0000001  # một khách, như production, kiểm contract
python -m src.evaluation.recsys_bench http-latency --base-url https://v-ota.duckdns.org --runs 3 --k 5   # p95 qua HTTP (Day 2 C)
python -m src.evaluation.recsys_bench run --arm engine_nommr --split llbo --vectors weaviate --split-file … --run-id 2026-10-01-llbo-v3   # thêm arm vào run đã có
python -m src.evaluation.recsys_bench analyze --run-id 2026-10-01-llbo-v3   # B5–B8: ceiling, phân khúc, strict/lenient, 20 ca (không cần Weaviate)
python -m src.evaluation.recsys_bench sanity [--json] [--refresh]            # B1: kiểm dữ liệu seed (§2.1); mã 1 khi kiểm tra cứng hỏng
python -m src.evaluation.recsys_bench run --arm engine --split temporal --vectors weaviate --split-file … --override MMR_LAMBDA=0.85   # M7: dò tham số trong tiến trình (§4.13)
python -m src.evaluation.recsys_bench parity --make-users --seed 42          # frozen/users60.json (4 persona + 56 phân tầng)
AUTH_SERVICE_TOKEN=… python -m src.evaluation.recsys_bench parity --base-url http://127.0.0.1:8000 --k 5   # B9: offline = HTTP (§4.12)
python -m pytest -q src/evaluation/recsys_bench/tests      # không cần DB
```

- `http-latency` (30/09): p50/p95 `/recommendations` qua HTTP, mặc định **guest path** (không cookie → `popular`) — đường
  duy nhất đo được từ ngoài trên Cloud hôm nay vì `/internal/recommendations` cần `X-Service-Token` + `INTERNAL_API_ENABLED`
  và BFF không chuyển header; `--users frozen/users60.json --token-env AUTH_SERVICE_TOKEN` đi `/internal` khi có tunnel IAP
  hoặc backend local. Số đầu bảng là `diagnostics.latencyMs` (server), `client_ms` (gồm mạng) báo riêng; `--drop-first` bỏ
  lượt 1. Ghi `bench_out/recsys/runs/<run_id>/http_latency.json`.

- `--vectors weaviate`: giống `main.build_recsys`, mỗi request truy vấn top-K ở Weaviate. `--vectors numpy`: kéo toàn
  bộ vector một lần (REST) và quét chính xác trong RAM, dùng cho grid-search. `none`: chỉ catalog, cho arm random.
- `as_of` mặc định là 00:00 UTC ngày sau event cuối. `--as-of` cắt ngay ở kho (`all_events(until=…)`).
- Event được cache ở `bench_out/recsys/cache/` theo DB (host:port/db) và `as_of`. **Seed lại DB thì chạy kèm
  `--refresh`** (hoặc `doctor`, lệnh này luôn đọc lại), nếu không `load`/`split`/`run` dùng bản cũ.
- **Split đóng băng (01/10, B2):** `split --freeze` ghi `src/evaluation/recsys_bench/frozen/split-<kind>-asof<YYYYMMDD>.json`
  (commit; không đè file có sha khác trừ `--force`) gồm `sha256` của phần quyết định kết quả: loại split, tham số, sha256
  của tập event đầu vào đã lọc, và từng target (unit, productId gốc, trip, as_of, số event/purchase train). `run --split-file
  <file>` **luôn đọc lại CDP (bỏ cache event)**, tính lại split rồi đối chiếu; lệch (DB seed lại, tham số khác) thì dừng với
  mã 1 và nêu khác ở đâu; khớp thì `summary.split.frozenSha256` ghi sha. Bản đóng băng chỉ phủ **event**: catalog / vector
  lấy trực tiếp (theo dõi qua `modelVersion`, `searchUnits`, `recommendable`, `vectorsMissing` trong `summary.json`).
  `--limit-users` ghi `limitUsers` / `usersEvaluated` và header in `SUBSET n/N`. Mọi bảng từ 01/10 phải cùng `frozenSha256`
  và cùng `configHash` mới so được với nhau.
- **`run --run-id <run đã có>`** gộp arm mới vào run cũ (thay arm trùng tên; từ chối khi khác `configHash` / `frozenSha256` /
  `modelVersion` / `asOf`). Arm `engine_nommr` (01/10): cùng engine eval nhưng thay `mmr_select` bằng "lấy theo score" và
  k = 200 → list = toàn bộ pool ứng viên; `rank` của target trong list này (poolRank) tách "không vào pool" khỏi "MMR đẩy
  xuống". Chỉ để chẩn đoán (B8) và ablation MMR (M7), không phải số báo cáo.
- **`analyze --run-id R [--base engine|engine_prod] [--ref most_popular_in_destination]`** (01/10, B5–B8): đọc `per_user.jsonl`,
  tính lại split (đối chiếu bản đóng băng của run), ghi `ceiling.{json,md}`, `segments.{json,md}`, `strict.md`, `cases.{json,md}`
  vào thư mục run; không cần Weaviate.
- **`summary.json` (01/10, B3):** `modelVersion`, `engineConfig` (ảnh chụp mọi hằng viết hoa của
  `domain/recommendation/profile.py` + `mode`, `candidateK`, `popularK`, `maxPerVertical`, `popularityWindowDays` 90,
  `purchaseLookbackDays` 730), `configHash` (sha256 8 ký tự; `configHashProd` cho arm `engine_prod`), `vectorsMissing` (unit
  không có vector đúng model — engine bỏ qua). `per_user.jsonl` (B7) mỗi khách: `ids` top-k đúng thứ tự, `targetProductId`
  (purchase gốc, có thể là phòng/chuyến con), `targetIsChild`, `rank` (lenient, unit cha — metric chính) và `rankStrict`
  (đúng productId gốc; engine chỉ trả search unit nên với con luôn None).

## 2. Dữ liệu (Day 1)

Postgres compose local, seed `AS_OF=2026-09-24`, `SEED=42`. Catalog có 3.183 search unit, 2.384 unit
recommendable, model `embed-multilingual-v3.0:catalog-text-v2`. `as_of` suy ra là 2026-09-24T00:00Z; event nằm trong
khoảng 2024-09-26 → 2026-09-23.

| | Số | Tỉ lệ trên purchase | Kỳ vọng (seed_report) |
|---|---:|---:|---|
| Event | 7.145 (purchase 3.153, view 2.179, cart 1.284, search 529) | | 7.145 |
| Purchase orphan (không quy được về search unit) — loại | 63 | 2,0 % | 63 |
| Purchase thiếu `event_group_id` — loại | 94 | 3,0 % | 94 |
| Purchase bị loại (hợp, 5 dòng dính cả hai) | 152 | 4,8 % | |
| View/cart/search thiếu gid — **giữ** (seed chỉ gắn gid cho purchase) | 3.992 | | |
| Event giữ lại · khách có event | 6.993 · 1.582 | | |
| Event ở hoặc sau `as_of` | 0 | | 0 |

### 2.1. Sanity dữ liệu seed (B1, 01/10) — `sanity`

Chạy trước khi tin số đo; hằng tỷ lệ đọc từ `src/data_collection/seed/config.py`; lifecycle tính lại theo đúng
`seed_histories.lifecycle` (ngày lịch VN, as_of = ngày sau event cuối, đếm **mọi** purchase kể cả orphan); profile đọc qua
`PostgresCdpReader.all_profiles()` (01/10). DB local seed 21/09 (as_of 22/09, 7.131 event, 2.000 profile, 2.897 search unit):

| Kiểm tra | Loại | Kết quả 01/10 |
|---|---|---|
| `lifecycle_mix` — `cdp.profiles.lifecycle_stage` vs STAGE_MIX 25/45/20/10 ± 5 điểm | cứng | **PASS** new 25,1 · active 45,0 · dormant 20,0 · churned 10,0 % |
| `lifecycle_recomputed` — stage và `days_since_last_booking` tính lại từ event = cột seed | cứng | **PASS** lệch 0/2.000 |
| `trips_multi_vertical` — chuyến có ≥ 2 taxonomy ≈ 65 % ± 5 | cứng | **PASS** 63,6 % (1.159/1.822) |
| `one_destination_per_trip` — chuyến có purchase ở ≥ 2 điểm đến ≤ 1 % | cứng | **PASS** 0/1.814 |
| `messy_edges` — orphan ≈ 2,0 %, thiếu `eventGroupId` ≈ 3,0 % (± 0,5) | cứng | **PASS** 63 (2,0 %) · 94 (3,0 %) trên 3.148 purchase |
| `popularity` — top-10 % sản phẩm chiếm bao nhiêu purchase; Gini; Zipf | chỉ báo | 159/1.584 sản phẩm chiếm **41,1 %** (kỳ vọng ≈ 41 %) · Gini sản phẩm 0,423 · search unit 0,525 · Zipf slope −0,63 (seed ZIPF_S 0,8 — phẳng hơn vì phân bố cắt theo điểm đến) |
| `golf_share` — tỷ lệ purchase theo taxonomy | chỉ báo | hotel 55,6 · flight 21,7 · attraction 17,8 · combo 3,0 · golf 1,9 % |
| `split_users` — số khách test của bản đóng băng | chỉ báo | LLBO 1.007 · temporal 102 |

Kết quả ghi `bench_out/recsys/sanity.json`; lệnh thoát mã 1 khi một kiểm tra cứng hỏng (số đo sau đó không được trích dẫn).

## 3. Split

| | LLBO (`--kind llbo`) | LLBO như seed (`--min-trips 2`) | Temporal (`--kind temporal`) |
|---|---|---|---|
| Luật | Khách ≥ 2 purchase hợp lệ; giấu purchase cuối; train = event của khách trước thời điểm đó | Như bên trái, thêm ≥ 2 `event_group_id` | T = phân vị 80 % thời điểm purchase = **2026-07-10T09:13Z**; train < T; target = purchase đầu tiên ≥ T |
| Khách test | **1.016** | 269 (= 267 của seed + 2 persona) | **98** (loại 262 khách không có event trước T) |
| Persona trong test | VP0000001, VP0000003 | | VP0000001 |
| Taxonomy của target | flight 433 · attraction 330 · combo 123 · hotel 80 · golf 50 | | hotel 93 · attraction 4 · combo 1 |
| Target đã mua trước đó (engine không thể trúng) | 10 | 10 | 1 |
| Target cùng loại món đã mua trong trip đang mở (bị category exclusion loại) | 0 | 0 | 18 |

- Target quy về search unit cha (phòng → khách sạn, chuyến → tuyến), vì engine chỉ trả search unit.
- Target LLBO phần lớn là vertical kế tiếp **trong cùng chuyến** (seed đặt hotel trước rồi flight/attraction). Đây đúng
  là ca `cross_vertical`, nên LLBO thuận lợi cho engine; temporal khó hơn nhiều.
- Baseline "Recall@20 = 59,9 %" trong `seed_report.md` **không so trực tiếp được** với bảng dưới. Nó biết trước điểm
  đến của món bị giấu, đếm độ phổ biến trên toàn bộ thời gian kể cả sau target, và so ở cấp sản phẩm (phòng).

### 3.1. Bản đóng băng (01/10)

| File (`src/evaluation/recsys_bench/frozen/`) | sha256 | Event đầu vào (sau lọc) | Khách test |
|---|---|---|---|
| `split-llbo-asof20260922.json` | `29033b34f8eb…4fb803` | 6.979 event, sha `17db0bd2…3363` | 1.007 |
| `split-temporal-asof20260922.json` | `a7735af1581a…962fff` | 6.979 event (T = 2026-07-07T15:23Z, phân vị 0,8) | 102 |

DB nguồn: Postgres local seed 2026-09-21 (`as_of` suy ra 2026-09-22), 2.897 search unit. Seed lại hoặc đổi `--min-purchases`
/ `--min-trips` / `--T` thì `run --split-file` từ chối — muốn đo trên DB khác thì `split --freeze` bản mới và ghi bảng riêng.

**Quy ước tuning (B10, chốt 01/10):** grid-search tham số engine chỉ chạy trên **temporal** đóng băng (train < T, kiểm ≥ T);
bảng báo cáo cuối dùng **LLBO** đóng băng; không chọn tham số theo LLBO. Mọi run ghi `configHash` (eval) / `configHashProd`;
hai bảng chỉ so được khi cùng `frozenSha256` **và** cùng `configHash`, cùng `modelVersion`.

## 4. Kết quả

k = 20, cùng tập khách và cùng train cho mọi arm. Random chạy 3 seed (42, 43, 44), báo trung bình ± độ lệch.
Hai baseline most-popular (cửa sổ thời gian) và most-popular-in-destination là việc của Day 2. **Engine v0 chạy
sớm** (lịch để Day 3) vì chạy đủ tập chỉ mất khoảng 40 giây.

### 4.1. LLBO — run `2026-09-29-llbo-v0`

| Arm | Khách | Recall@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Diversity@10 | Trả về (TB) | p95 ms | p99 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random (3 seed) | 1016 | 0.0010 ± 0.0008 | 0.0036 ± 0.0020 | 0.0066 ± 0.0023 | 0.0018 ± 0.0012 | 0.999 | 1.000 | 0.236 | 0.518 ± 0.004 | 20.0 | 0.0 | 0.1 |
| most-popular (cửa sổ) | Day 2 | | | | | | | | | | | |
| most-popular-in-destination | Day 2 | | | | | | | | | | | |
| engine | 1016 | 0.5817 | 0.6191 | 0.6191 | 0.4718 | 0.207 | 1.000 | 0.953 | 0.642 | 5.3 | 58.2 | 81.1 |

- Strategy của engine: `cross_vertical` 923, `recent_activity` 93. Tỉ lệ trúng theo loại target: golf 50/50,
  hotel 65/80, flight 294/433, combo 55/123, attraction 165/330.
- Engine trả trung bình 5,3 món (1–9) dù `k = 20`, nên Recall@20 = Recall@10 (Issue I-5).
- Golf trúng 50/50 vì catalog chỉ có 6 unit golf và golf không bị loại khi đã đặt khách sạn. Con số này không nói
  lên chất lượng xếp hạng.
- Kiểm sanity: random Recall@20 ≈ 20 / 2.384 unit recommendable ≈ 0,8 % (đo được 0,66 %).

### 4.2. Temporal — run `2026-09-29-temporal-v0`

| Arm | Khách | Recall@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Diversity@10 | Trả về (TB) | p95 ms | p99 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random (3 seed) | 98 | 0.0034 ± 0.0048 | 0.0034 ± 0.0048 | 0.0034 ± 0.0048 | 0.0034 ± 0.0048 | 0.563 | 1.000 | 0.322 | 0.515 ± 0.005 | 20.0 | 0.1 | 0.2 |
| engine | 98 | 0.1327 | 0.1327 | 0.1327 | 0.1327 | 0.086 | 1.000 | 0.686 | 0.768 | 6.8 | 83.1 | 86.4 |

- Strategy: `long_term` 42, `cross_vertical` 24, `dormant` 16, `cold_start_content` 10, `recent_activity` 6. Cả 13
  lần trúng đều ở hạng 1 và đều là khách sạn; 9/10 ca `cold_start_content` trúng (khách đã xem đúng khách sạn đó).
- 98 khách là tập nhỏ; một lần trúng làm Recall đổi khoảng 1 điểm %.

### 4.3. Đối chiếu ngưỡng

| Tiêu chí | Ngưỡng | LLBO engine | Ghi chú |
|---|---|---|---|
| Thắng rõ most-popular-in-destination ở Recall@20, NDCG@10 | handbook §12 | **Đạt** (mode eval, 30/09, §4.4): Recall@20 0,851 vs 0,635; NDCG@10 0,524 vs 0,389 | list production (cap 2 / taxonomy, `engine_prod`) chỉ 0,591 / 0,460 — I-5 |
| Availability precision | ≥ 95 % | 100 % | engine lọc `available` trước; random cũng bốc trong tập đó |
| Catalog coverage | > 20 % | 20,7 % (Day 1) · 58,3 % eval / 20,5 % prod (30/09) | mpd 41,6 % |
| p95 `/recommendations` | ≤ 250 ms (PRD NFR-PERF-01) | 58 ms offline (Day 1) · 214 ms (30/09, máy khác, Weaviate app local 2.897 object) | Weaviate local, không gồm HTTP và đọc CDP; số cloud là Day 2 |

### 4.4. Ngày 30/09 — đủ 4 arm (random / most_popular / most_popular_in_destination / engine) trên seed 2026-09-21

Chạy trên máy A (kế hoạch `docs/plan/2026-09-30-bench-search-recsys-3-ngay.md`, quyết định D5): Postgres compose local
đang là **seed snapshot 2026-09-21, as_of 2026-09-22** (2.897 search unit, 2.118 recommendable, 7.131 event; khác seed
09-23 của Day 1 nên số không so trực tiếp với §4.1–4.2), Weaviate app local `Product` 2.897 object (`WEAVIATE_URL`
ghi đè `http://127.0.0.1:8080` vì `.env` đang trỏ Cloud). Lọc: purchase orphan 63 (2,0 %), thiếu gid 94 (3,0 %), loại
152; giữ 6.979 event / 1.582 khách. Hai baseline mới (`recsys_bench/arms.py`): `most_popular` = `Popularity.unit_scores`
cửa sổ 90 ngày trước `as_of` của từng khách (đúng thành phần pop của engine, chỉ purchase < `as_of`);
`most_popular_in_destination` = cùng điểm nhưng lọc theo điểm đến của chuyến đang mở (≤ 60 ngày) hoặc chuyến gần nhất,
thiếu thì bù most_popular toàn cục (`strategy = most_popular_fallback`, 0/1.007 khách LLBO cần bù). Cả hai chỉ chọn
unit `recommendable` + còn chỗ như engine.

**LLBO** — run `2026-09-30-llbo-v1`: 1.007 khách test (min 2 purchase), target: flight 437 · attraction 379 · hotel 81
· combo 66 · golf 44; `repeatTarget` 10; k = 20.

| Arm | Khách | Recall@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Diversity@10 | Trả về (TB) | p95 ms | p99 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random (3 seed) | 1007 | 0.0023 ± 0.0005 | 0.0040 ± 0.0008 | 0.0083 ± 0.0026 | 0.0017 ± 0.0003 | 0.999 | 1.000 | 0.224 | 0.507 | 20.0 | 0.1 | 0.3 |
| most_popular (90 ngày) | 1007 | 0.0993 | 0.1867 | 0.2929 | 0.0891 | 0.068 | 1.000 | 0.770 | 0.514 | 20.0 | 41.0 | 52.2 |
| most_popular_in_destination | 1007 | 0.4965 | 0.5780 | 0.6346 | 0.3890 | 0.416 | 1.000 | 0.385 | 0.617 | 20.0 | 44.5 | 54.6 |
| engine (mode eval, không cap) | 1007 | **0.6693** | **0.7527** | **0.8510** | **0.5244** | 0.583 | 1.000 | 0.898 | 0.516 | 15.2 | 185.0 | 257.2 |
| engine_prod (cap 2 / taxonomy) | 1007 | 0.5720 | 0.5909 | 0.5909 | 0.4602 | 0.205 | 1.000 | 0.943 | 0.625 | 4.8 | 136.8 | 190.6 |

**Temporal** — run `2026-09-30-temporal-v1`: T = 2026-07-07T15:23Z (phân vị 80 %), 102 khách test (266 khách chưa có
event trước T bị loại), target hotel 94 · attraction 5 · combo 2 · flight 1; `targetVerticalExcluded` 15.

| Arm | Khách | Recall@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Cross-category | Diversity@10 | Trả về (TB) | p95 ms | p99 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random (3 seed) | 102 | 0.0033 ± 0.0046 | 0.0065 ± 0.0092 | 0.0065 ± 0.0092 | 0.0024 ± 0.0033 | 0.619 | 1.000 | 0.340 | 0.503 | 20.0 | 0.3 | 0.4 |
| most_popular (90 ngày) | 102 | 0.0000 | 0.0196 | 0.0588 | 0.0060 | 0.009 | 1.000 | 0.677 | 0.600 | 20.0 | 1.8 | 2.4 |
| most_popular_in_destination | 102 | 0.0294 | 0.0784 | 0.0980 | 0.0312 | 0.140 | 1.000 | 0.393 | 0.606 | 20.0 | 2.1 | 2.7 |
| engine (mode eval, không cap) | 102 | **0.1667** | **0.1961** | **0.1961** | **0.1438** | 0.379 | 1.000 | 0.425 | 0.557 | 18.9 | 264.9 | 293.9 |
| engine_prod (cap 2 / taxonomy) | 102 | 0.1176 | 0.1176 | 0.1176 | 0.1127 | 0.091 | 1.000 | 0.663 | 0.709 | 6.1 | 152.9 | 175.6 |

Hai dòng engine (quyết định 30/09, kế hoạch Day 3 B): **`engine` = mode eval** — cùng `RecommendForUser`, chỉ bỏ cap
`MAX_PER_VERTICAL = 2` (`max_per_vertical=None`, `OfflineEngine(mode="eval")`) để k = 20 có đủ 20 món — đây là **list
đánh giá**; **`engine_prod`** = đúng list production (cap 2 mỗi taxonomy, `mode="prod"`) — "khách thật sự thấy gì".
Production (`main.py`) không đổi. Cap 2/taxonomy khiến engine_prod trả TB 4,8 món (2 món 223 khách, 4 món 235, 5 món 112,
6 món 190, 7 món 197, tối đa 9) nên Recall@20 = Recall@10 (Issue I-5).

Đọc số:

- **Thứ tự sanity đúng ở cả hai split:** random ≪ most_popular < most_popular_in_destination (Recall@20 LLBO 0,008 ≪ 0,293
  < 0,635; temporal 0,007 ≪ 0,059 < 0,098) → split và dữ liệu không lỗi (handbook §6, §12).
- **Engine (eval) so với most_popular_in_destination — tiêu chí M5 đạt:** Recall@20 LLBO **0,851 vs 0,635**, NDCG@10
  **0,524 vs 0,389**; temporal 0,196 vs 0,098 và 0,144 vs 0,031. Cùng xếp hạng đó nhưng cắt theo list production
  (engine_prod) chỉ còn Recall@20 0,591 — thua mpd — tức là chất lượng xếp hạng đủ, **cap 2 món / taxonomy là thứ làm
  mất recall** ở k = 20; ở top-5 (list khách thấy) engine_prod vẫn hơn mpd (Recall@5 0,572 vs 0,497).
- **Theo taxonomy của target (LLBO, trúng@20, engine_prod):** hotel 68/81, golf 44/44, combo 28/66, flight 296/437,
  attraction 159/379; mpd hotel 18/81, golf 35/44, combo 23/66, flight 340/437, attraction 223/379. Với 139 khách mpd trúng
  mà engine_prod trượt, target chủ yếu attraction (85) / flight (49) — món đúng nằm ngoài 2 slot của vertical đó.
- **Cross-category:** engine_prod 0,943, engine (eval) 0,898 (mục đích của `/recommendations`, handbook §12), mpd 0,385.
  **Coverage:** engine (eval) 58,3 %, engine_prod 20,5 % (sát ngưỡng > 20 %), mpd 41,6 %. Availability 100 % mọi arm.
- **Temporal** (102 khách, 1 lần trúng ≈ 1 điểm %): engine (eval) 20/102, engine_prod 12/102, mpd 10/102; engine_prod
  trúng chủ yếu ở `cold_start_content` 8/13 và `recent_activity` 3/3, gần như không ở `long_term` 1/45, `dormant` 0/19,
  `cross_vertical` 0/22 (15 target bị category exclusion loại) — chỗ Day 4–5 nên xem.
- **Latency:** p95 engine (eval) 185 ms, engine_prod 137 ms LLBO (máy này, Weaviate app local; Day 1 máy khác 58 ms) —
  chưa gồm HTTP / đọc CDP; mpd ~22 ms là chi phí dựng `Popularity` theo `as_of` từng khách (cache 8 mốc).

Lệnh sinh lại (từ gốc repo, `.venv`): `WEAVIATE_URL=http://127.0.0.1:8080 WEAVIATE_API_KEY= EVAL_DATABASE_URL=<.env>
python -m src.evaluation.recsys_bench run --arm random --arm most_popular --arm most_popular_in_destination --arm engine
--arm engine_prod --split llbo|temporal --vectors weaviate --run-id <id>`; số thô ở
`bench_out/recsys/runs/2026-09-30-{llbo,temporal}-v2/` (v1 = trước khi có mode eval, engine = engine_prod).

### 4.5. Ngày 01/10 — p95 `/recommendations` trên Cloud (guest path)

`python -m src.evaluation.recsys_bench http-latency --base-url https://v-ota.duckdns.org --runs 3 --k 5` (01/10 ~01:30 UTC+7,
qua BFF công khai, không cookie → `strategy = popular`; 3 lượt × 5 GET, bỏ lượt 1 khỏi p50/p95):

| Đường | n | `latencyMs` p50 | p95 | client p50 | p95 | strategy |
|---|---:|---:|---:|---:|---:|---|
| guest | 10 | **9 ms** | **10 ms** | 141 ms | 391 ms | popular ×15 |

- Số server (engine) xa dưới ngân sách 300 ms (spec search-recommendation §7.1, "cache hit"); phần còn lại của wall phía
  client là RTT + BFF + TLS, không phải engine.
- **Không phải số của 60 khách**: đường có JWT / `/internal/recommendations` (cần IAP + `X-Service-Token`) chưa đo được từ
  ngoài; khi ops mở IAP chạy lại với `--users frozen/users60.json --token-env AUTH_SERVICE_TOKEN`. Local 24/09 với 60 khách:
  p50 127 / p95 143 ms (lịch 10 ngày Day 2 C).
- Cùng lúc đó `/api/v1/search` công khai treo rồi 500 sau ~64 s (chuỗi backoff Cohere 2+4+8+16+32 s) trong khi `/similar`
  (chỉ Weaviate) 1,5 s và `/recommendations` bình thường → lỗi ở bước embed Cohere trên VM (khoá / egress), không phải Weaviate;
  chờ ops kiểm log container. Run: `bench_out/recsys/runs/20261001-cloud-guest/http_latency.json`.

### 4.6. Ngày 01/10 — v3: split đóng băng, NDCG@5, `ids` theo khách (B Phase 0)

Run `2026-10-01-llbo-v3` và `2026-10-01-temporal-v3` (`--split-file` khớp §3.1; `configHash` eval / prod ghi trong
`summary.json`; `vectors weaviate` local, `vectorsMissing 0`). **Mọi số Recall/NDCG@10/Coverage tái tạo đúng v2 (§4.4)** —
bảng dưới thêm cột NDCG@5 (list production 5 món).

LLBO — 1.007 khách:

| Arm | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Trả về (TB) | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| random (3 seed) | 0,0023 | 0,0012 | 0,0040 | 0,0083 | 0,0017 | 0,999 | 20,0 | 0,3 |
| most_popular | 0,0993 | 0,0611 | 0,1867 | 0,2929 | 0,0891 | 0,068 | 20,0 | 42,5 |
| most_popular_in_destination | 0,4965 | 0,3624 | 0,5780 | 0,6346 | 0,3890 | 0,416 | 20,0 | 40,2 |
| engine (eval, bỏ cap) | **0,6693** | **0,4973** | **0,7527** | **0,8510** | **0,5244** | 0,583 | 15,2 | 300,5 |
| engine_prod (cap 2/taxonomy) | 0,5720 | 0,4536 | 0,5909 | 0,5909 | 0,4602 | 0,205 | 4,8 | 233,5 |

Temporal — 102 khách (T = 2026-07-07T15:23Z):

| Arm | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Trả về (TB) | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| random (3 seed) | 0,0033 | 0,0013 | 0,0065 | 0,0065 | 0,0024 | 0,619 | 20,0 | 0,2 |
| most_popular | 0,0000 | 0,0000 | 0,0196 | 0,0588 | 0,0060 | 0,009 | 20,0 | 1,8 |
| most_popular_in_destination | 0,0294 | 0,0149 | 0,0784 | 0,0980 | 0,0312 | 0,140 | 20,0 | 2,0 |
| engine (eval) | **0,1667** | **0,1348** | **0,1961** | **0,1961** | **0,1438** | 0,379 | 18,9 | 420,5 |
| engine_prod | 0,1176 | 0,1127 | 0,1176 | 0,1176 | 0,1127 | 0,091 | 6,1 | 229,4 |

- p95 ms là thời gian xếp hạng offline trên máy dev **đang chạy song song** tác vụ khác (lần chạy đầu 01/10 rảnh máy: engine 190 / prod 138 ms LLBO); chỉ so thứ tự, không dùng làm số latency.
- NDCG@5 của `engine_prod` (0,4536) sát NDCG@10 của nó (0,4602): list 5 món production giữ gần trọn thứ hạng; chênh eval −
  prod ở Recall@5 (0,669 → 0,572) là do cap 2 món/taxonomy đẩy target ra khỏi top-5 (I-5), không phải do xếp hạng.
- Strategy của engine trên LLBO/temporal ghi trong `summary.json` (`rows[].strategies`); phân khúc theo strategy làm ở B6.

### 4.7. Ceiling — trần recall theo bộ lọc cứng của engine (B5, 01/10)

`ceiling.py` mô phỏng profile + mask ứng viên của `RecommendForUser` (cap lặp, trip mở ≤ 60 ngày, `bought_units`, điểm đến và
taxonomy bị loại của trip mở, fallback khi mask theo điểm đến rỗng; không có trip → `cold_start`). Bản "chính xác" dùng
`strategy` / `destination` / `excludedVerticals` engine trả về; bản xấp xỉ chỉ từ event — **đồng thuận 100 %** trên cả hai split.

| Split | Khách | Ceiling (target tới được mask) | Recall@20 engine | Recall@20 trên khách tới được | mpd Recall@20 | Lý do không tới được (đa nhãn) |
|---|---:|---:|---:|---:|---:|---|
| LLBO | 1.007 | **0,990** (997) | 0,851 | 0,860 | 0,635 | `already_bought` 10 |
| Temporal | 102 | **0,784** (80) | 0,196 | 0,250 | 0,098 | `taxonomy_excluded` 15 · `destination_mismatch` 18 · `already_bought` 1 (lý do đầu: 14 / 7 / 1) |

Luật đọc (plan Day 3): ceiling ≥ Recall@20 của mpd ở cả hai split → filter **không** phải nút thắt; nhưng trên temporal 22 %
target bị chính filter chặn — xem findings.

### 4.8. Phân khúc (B6, 01/10) — hit@20 / NDCG@10, nhãn tính một lần từ train

LLBO (1.007) — engine (eval) · engine_prod · mpd:

| Nhãn | Giá trị | n | engine | engine_prod | mpd |
|---|---|---:|---:|---:|---:|
| strategy | cross_vertical | 911 | 0,844 / 0,497 | 0,565 / 0,429 | 0,668 / 0,415 |
| | recent_activity | 96 | 0,917 / 0,788 | 0,833 / 0,758 | 0,312 / 0,142 |
| coldStart (< 3 event) | False / True | 664 / 343 | 0,860 / 0,834 | 0,623 / 0,528 | 0,625 / 0,653 |
| lifecycleAtAsOf | active / dormant | 969 / 38 | 0,847 / 0,947 | 0,581 / 0,842 | 0,642 / 0,447 |
| targetTaxonomy | flight | 437 | 0,838 / 0,559 | 0,677 / 0,538 | 0,778 / 0,549 |
| | attraction | 379 | 0,871 / 0,460 | 0,420 / 0,316 | 0,588 / 0,331 |
| | hotel | 81 | 0,938 / 0,825 | 0,840 / 0,784 | 0,222 / 0,065 |
| | combo | 66 | 0,621 / 0,198 | 0,424 / 0,233 | 0,348 / 0,127 |
| | golf | 44 | 1,000 / 0,673 | 1,000 / 0,681 | 0,795 / 0,289 |
| targetTrip | open / new | 911 / 96 | 0,844 / 0,917 | 0,565 / 0,833 | 0,668 / 0,312 |
| activeTripIsSolo (I-3) | False / True | 911 / 96 | 0,844 / 0,917 | 0,565 / 0,833 | 0,668 / 0,312 |
| persona | True *(ồn)* | 2 | 0,000 | 0,000 | 0,500 |

Temporal (102):

| Nhãn | Giá trị | n | engine | engine_prod | mpd |
|---|---|---:|---:|---:|---:|
| strategy | long_term | 45 | 0,089 / 0,044 | 0,022 / 0,022 | 0,089 / 0,022 |
| | cross_vertical | 22 | **0,000** | 0,000 | 0,045 / 0,023 |
| | dormant *(ồn)* | 19 | 0,053 | 0,000 | 0,053 |
| | cold_start_content *(ồn)* | 13 | 0,923 / 0,751 | 0,615 / 0,615 | 0,154 / 0,054 |
| coldStart | False / True | 72 / 30 | 0,111 / 0,400 | 0,056 / 0,267 | 0,097 / 0,100 |
| lifecycleAtAsOf | active / dormant / new *(ồn)* | 68 / 21 / 13 | 0,088 / 0,095 / 0,923 | 0,044 / 0,048 / 0,615 | 0,088 / 0,095 / 0,154 |
| targetTaxonomy | hotel | 94 | 0,191 / 0,146 | 0,117 / 0,117 | 0,085 / 0,023 |
| activeTripIsSolo | False / True *(ồn)* | 86 / 16 | 0,058 / 0,938 | 0,012 / 0,688 | 0,070 / 0,250 |

Bảng đầy đủ (kể cả `engine_nommr`, `most_popular`): `bench_out/recsys/runs/2026-10-01-*-v3/segments.md`.

### 4.9. Strict vs lenient theo taxonomy (B7, 01/10)

`rank` (unit cha, metric chính) vs `rankStrict` (đúng productId đã mua). Seed mua phòng (`hotel_room`) và chuyến bay (con) còn
engine chỉ trả search unit nên với hai loại này strict = 0 **theo cấu trúc**; attraction / combo / golf target đã là unit → strict = lenient.

| Split | Taxonomy | n | target là con | engine lenient / strict | engine_prod | mpd |
|---|---|---:|---:|---:|---:|---:|
| LLBO | flight | 437 | 437 | 0,838 / 0,000 | 0,677 / 0,000 | 0,778 / 0,000 |
| | attraction | 379 | 0 | 0,871 / 0,871 | 0,420 / 0,420 | 0,588 / 0,588 |
| | hotel | 81 | 81 | 0,938 / 0,000 | 0,840 / 0,000 | 0,222 / 0,000 |
| | combo | 66 | 0 | 0,621 / 0,621 | 0,424 / 0,424 | 0,348 / 0,348 |
| | golf | 44 | 0 | 1,000 / 1,000 | 1,000 / 1,000 | 0,795 / 0,795 |
| Temporal | hotel | 94 | 94 | 0,191 / 0,000 | 0,117 / 0,000 | 0,085 / 0,000 |

Kết luận: 518/1.007 target LLBO (51 %) và 95/102 temporal không đo được strict với engine v0; muốn đo "đúng hạng phòng /
chuyến" cần engine trả cấp con — ngoài phạm vi v0, không đổi metric chính.

### 4.10. Engine trượt mà baseline trúng — 20 ca và đếm toàn tập (B8, 01/10)

Arm chẩn đoán `engine_nommr` (pool 200 theo score, không MMR): LLBO Recall@20 **0,863** / NDCG@10 **0,548** (engine có MMR
0,851 / 0,524); temporal 0,196 / 0,136 (= engine).

| Split | engine trượt top-20 & mpd trúng | Nguyên nhân (toàn tập) |
|---|---:|---|
| LLBO | 21 / 1.007 | `filtered` 9 (`already_bought`) · `mmr_demoted` 6 (target ở pool hạng 3–17, tức trong top-20 theo score nhưng MMR đẩy ra) · `ranked_low` 6 (pool hạng 22–33: trượt kể cả không MMR) |
| Temporal | 4 / 102 | `filtered` 1 (VP0000001: đã mua + hotel bị loại) · `mmr_demoted` 1 (pool 13) · `ranked_low` 1 (pool 76) · `wrong_active_trip` 1 (trip mở là view lẻ, target thuộc trip khác) |

Không có ca `pool_miss`, `out_of_candidates`, `destination_mismatch` riêng: khi target tới được mask, nó **luôn** vào pool 200 theo
score; trượt chia đôi giữa MMR (λ 0,7) đẩy ra và xếp hạng theo score chưa đủ (hạng 22–33). 20 ca LLBO và 4 ca temporal:
`bench_out/recsys/runs/2026-10-01-*-v3/cases.md` (mỗi ca: khách, target, loại · điểm đến, strategy · điểm đến engine, hạng
engine / mpd, số event train).

### 4.11. Engine v0 — findings (01/10)

1. LLBO: bộ lọc cứng không phải nút thắt — ceiling 0,990, chỉ 10 target là món đã mua (engine loại có chủ đích); Recall@20 0,851 = 86 % số tới được.
2. MMR làm giảm nhẹ: bỏ MMR → Recall@20 0,863 / NDCG@10 0,548 (+0,012 / +0,024); 6/21 ca engine trượt-mpd trúng là `mmr_demoted` (target trong top-20 theo score, hạng 3–17) và 6 ca là `ranked_low` (hạng 22–33, score chưa đủ). Ứng viên tune M7: λ MMR 0,7 → 0,85 hoặc chỉ MMR sau top-5 — chạy trên temporal đóng băng (§3.1); phần `ranked_low` cần trọng số W_SHORT/W_POP, không phải MMR.
3. Cap 2 món / taxonomy (production) đắt nhất ở attraction (0,871 → 0,420) và combo (0,621 → 0,424); hotel, golf gần như không đổi (I-5).
4. Temporal (đoán chuyến kế): 22 % target bị chính filter chặn — `taxonomy_excluded` (khách vừa mua hotel trong trip mở, chuyến kế lại mua hotel) và `destination_mismatch` (chuyến kế ở điểm đến khác); strategy `cross_vertical` **0/22**. *(02/10: tách được — 11/21 là trip chỉ view bị coi là mở tới 60 ngày, 10/21 là chuyến chưa đi tại T; §4.14.)*
5. Giả định cross-vertical đúng **trong** chuyến (LLBO 0,844) nhưng sai **giữa** hai chuyến: category exclusion và khoá điểm đến chỉ nên áp khi trip mở còn diễn ra (theo `usingDate`), không áp cho chuyến kế — **đã chốt và áp dụng 02/10** (FR-REC-02, `update-archive/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md`): trip mở theo `usingDate`, trip chỉ view mở ≤ 14 ngày → temporal R@20 0,196 → 0,216, LLBO không đổi (§4.14).
6. `activeTripIsSolo` (I-3) là phân khúc mạnh nhất: trip mở là view lẻ ngay trước purchase → engine gợi đúng món vừa xem (LLBO 0,917, temporal 0,938). Đây là hành vi xem-rồi-mua seed tạo ra; số này phản ánh cấu trúc seed hơn là chất lượng xếp hạng — ghi chú khi trích dẫn.
7. `long_term` / `dormant` trên temporal ≈ mpd (0,089 vs 0,089): vector dài hạn không hơn popular theo điểm đến cho chuyến kế; target hotel 94/102 hit 0,191.
8. Strict = 0 theo cấu trúc cho 51 % target LLBO (flight, hotel con); không phải lỗi engine, là độ mịn của catalog search unit.
9. mpd là baseline mạnh ở flight (0,778) và golf (0,795), yếu ở hotel (0,222); engine hơn hẳn ở hotel (0,938) và attraction (0,871).
10. Hai persona trong test LLBO đều trượt (VP0000001 đặt lại KS đã mua → `already_bought`): kịch bản demo P1 cần món khác loại, không phải mua lại.

### 4.12. Offline = HTTP trên 60 khách (B9, 01/10) — `parity`

Engine offline của harness (`OfflineEngine(mode="prod")`, cap 2 món / taxonomy) so với `GET /api/v1/internal/recommendations?cdp_user_id=&k=5`
của backend local chạy từ cùng checkout (Postgres 5432 seed 21/09, Weaviate 8080, `APP_ENV=development`, `INTERNAL_API_ENABLED=true`,
`X-Service-Token` sinh ngẫu nhiên cho phiên đo). Khác biệt được trung hoà: as_of = `generatedAt` của response; event của khách mới
nhất trước như `events_for_user`; bảng phổ biến từ purchase thô trước as_of (production neo ở lúc backend khởi động / nạp lại
900 s — khởi động lại backend ngay trước khi đo); cùng `candidate_k`. Bộ khách `frozen/users60.json` (seed 42): 4 persona + 56
khách phân tầng theo `lifecycleStage` của `cdp.profiles` 14 new / 25 active / 11 dormant / 6 churned; 14 khách `new` đều **không
có event** (418/501 profile `new` không có event) → đi đường `popular`, kiểm cả cold start (bộ 24/09 không được lưu).

| Chỉ số | Lần 1 (56 khách suy từ event, 06:30) | Lần 2 (tầng theo `cdp.profiles`, 14 khách 0 event; 08:00) |
|---|---|---|
| Trùng hoàn toàn (strategy, destination, excludedVerticals, eventsUsed, top-5 đúng thứ tự) | **60/60** | **60/60** |
| HTTP local `diagnostics.latencyMs` p50 / p95 | 250 / 321 ms (máy đang chạy song song) | **93 / 134 ms** (máy rảnh; 24/09 đo 127 / 143) |
| Client wall p50 / p95 | 263 / 338 ms | 99 / 139 ms |

Run: `bench_out/recsys/runs/2026-10-01-parity-http{,-v2}/parity.json`. Kết luận: mọi số offline của harness (§4.4–4.11) là số của đúng
engine production; trên Cloud chỉ đo được guest path (§4.5) cho tới khi ops mở IAP.

### 4.13. Grid-search lần 1 trên temporal đóng băng (M7, 01/10) — `run --override`

`run --override KEY=VALUE` đặt hằng của `domain/recommendation/profile.py` **trong tiến trình harness** (production không đổi);
`engineConfig`/`configHash` ghi giá trị đã đổi. Quy ước B10 (§3.1): chỉ dò trên temporal đóng băng `a7735af1…` (102 khách, k = 20),
LLBO giữ nguyên làm bảng cuối. Một yếu tố mỗi lần, arm `engine` (eval) và `engine_prod` (cap 2):

| Run | Override | configHash (eval / prod) | engine R@5 / NDCG@5 | engine R@20 / NDCG@10 | Δ R@20 / Δ NDCG@10 vs gốc | engine_prod R@5 / NDCG@5 | Δ prod NDCG@5 |
|---|---|---|---:|---:|---:|---:|---:|
| gốc (`2026-10-01-temporal-v3`) | — | 21577d17 / a19bf1e1 | 0.1667 / 0.1348 | 0.1961 / 0.1438 | — | 0.1176 / 0.1127 | — |
| mmr085 | `MMR_LAMBDA=0.85` | 6af95718 / dff1afe4 | 0.1667 / 0.1341 | 0.1961 / 0.1376 | +0.0000 / -0.0062 | 0.1176 / 0.1121 | -0.0007 |
| mmr100 | `MMR_LAMBDA=1.0` | eb6b2a49 / 533fd8d0 | 0.1569 / 0.1325 | 0.1961 / 0.1360 | +0.0000 / -0.0078 | 0.1275 / 0.1183 | +0.0055 |
| wshort05 | `W_SHORT=0.5, W_POP=0.35` | 892db886 / c4ff7b26 | 0.1471 / 0.0886 | 0.2059 / 0.0981 | +0.0098 / -0.0457 | 0.1078 / 0.0714 | -0.0413 |
| wshort07 | `W_SHORT=0.7, W_POP=0.15` | cef1d0fa / fa2d231f | 0.1667 / 0.1434 | 0.1961 / 0.1499 | +0.0000 / +0.0061 | 0.1569 / 0.1391 | +0.0264 |
| hshort60 | `H_SHORT_DAYS=60.0` | 9b7294fc / e457f5cc | 0.1667 / 0.1348 | 0.1961 / 0.1438 | +0.0000 / +0.0000 | 0.1176 / 0.1127 | +0.0000 |
| active30 | `ACTIVE_TRIP_MAX_AGE_DAYS=30` | cc3fd38d / 95f7d15d | 0.1863 / 0.1452 | 0.2157 / 0.1542 | +0.0196 / +0.0104 | 0.1275 / 0.1189 | +0.0062 |
| active14 | `ACTIVE_TRIP_MAX_AGE_DAYS=14` | 22d1ecc4 / acf56417 | 0.1863 / 0.1452 | 0.2255 / 0.1542 | +0.0294 / +0.0104 | 0.1275 / 0.1189 | +0.0062 |
| dormant90 | `DORMANT_AFTER_DAYS=90` | 026e08ab / c82d8692 | 0.1667 / 0.1348 | 0.1961 / 0.1438 | +0.0000 / +0.0000 | 0.1176 / 0.1127 | +0.0000 |
| wtype531 | `W_TYPE={"purchase": 5.0, "add_to_cart": 3.0, "product_view": 1.0, "search": 0.1}` | 2fc70be5 / f3401058 | 0.1667 / 0.1348 | 0.1961 / 0.1438 | +0.0000 / +0.0000 | 0.1176 / 0.1127 | +0.0000 |

Chỉ **cửa sổ trip mở** đổi kết quả: `ACTIVE_TRIP_MAX_AGE_DAYS` 60 → 30 / 14 nâng Recall@20 0,196 → 0,216 / **0,225** và NDCG@10 0,144 → 0,154 (+0,010), prod NDCG@5 +0,006 — cùng hướng với finding M6 (trip cũ còn trong 60 ngày bị coi là đang mở nên loại nhầm). `W_SHORT=0,7 / W_POP=0,15` +0,006 NDCG@10 và prod NDCG@5 +0,026; `W_SHORT=0,5 / W_POP=0,35` tệ hẳn (NDCG@10 −0,046). MMR λ 0,85 / 1,0, `H_SHORT_DAYS` 60, `DORMANT_AFTER_DAYS` 90 và `W_TYPE` 5/3/1 không đổi hoặc giảm nhẹ. Khác biệt trên 102 khách là 1–3 khách nên chỉ là hướng dò, không phải quyết định; muốn áp dụng phải qua M6 (đề xuất PRD) và chạy lại LLBO.

### 4.14. Sau FR-REC-02 (M6, 02/10): trip mở theo `usingDate`, N = 14 cho trip chỉ view

Người dùng chốt đề xuất `update-archive/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` (02/10). Engine: trip có
`usingDate` mở tới hết ngày sử dụng (`trip_is_open`, `ENGINE_RULES_VERSION = 2026-10-02-trip-ended`); trip không có
`usingDate` (chỉ view / search) mở khi event gần nhất ≤ N ngày. Harness (ceiling, `excluded_taxonomies`, `trip_destination`)
mô phỏng cùng luật. Hai bước, cùng split đóng băng (§3.1):

| Bước | configHash eval / prod | Temporal engine R@20 / NDCG@10 | Temporal ceiling | LLBO engine R@20 / NDCG@10 | LLBO ceiling |
|---|---|---:|---:|---:|---:|
| v3 — luật cũ (tuổi event ≤ 60 ngày) | 21577d17 / a19bf1e1 | 0,1961 / 0,1438 | 0,784 (80/102) | 0,8510 / 0,5244 | 0,990 |
| v4 — `usingDate`, N = 60 | 738cdf77 / 8aabd24c | 0,1961 / 0,1438 | 0,794 (81/102) | 0,8510 / 0,5244 | 0,990 |
| **v5 — `usingDate`, N = 14** (code hiện tại) | b0aee886 / 81d16abd | **0,2157 / 0,1542** (prod NDCG@5 0,1127 → 0,1189) | **0,892** (91/102; 11 còn lại: 6 `taxonomy_excluded`, 9 `destination_mismatch`, 1 `already_bought` — đều là chuyến chưa đi tại T) | 0,8510 / 0,5244 (không đổi) | 0,990 (997/1007, 10 `already_bought`) |

Vì sao `usingDate` một mình gần như không đổi (v4): trong 21 target temporal bị chặn ở v3, **11** đến từ trip **chỉ có view**
(không `usingDate`) 36–58 ngày tuổi vẫn bị coi là mở và khoá điểm đến; **10** đến từ chuyến thật sự chưa đi tại T
(`usingDate` ≥ T, 0–37 ngày sau T) — ở mốc T engine đúng khi coi đó là chuyến mở, target là purchase của chuyến kế **sau khi**
chuyến này đi xong, nên split temporal (as_of = T) đang hỏi "đã mua gì sau T" chứ không phải "gợi gì ngay trước lúc mua".
N = 14 xử lý nhóm đầu (grid §4.13: 14 và 30 cho cùng NDCG@10, 14 cao hơn R@20); nhóm sau cần split kiểu "next trip" (as_of =
ngay trước purchase kế, trip trước đã kết thúc) — việc tiếp theo của harness, không phải lỗi engine.

Trên LLBO (trong chuyến) cả hai bước không đổi số nào: 911 khách `cross_vertical` đều có trip có `usingDate` còn mở tại as_of.
Run: `bench_out/recsys/runs/2026-10-02-{temporal,llbo}-v{4,5}/` (+ `-v4-n14` là lượt thử override trước khi đổi hằng).
Sau v5, ceiling temporal còn **0,892** — 11 target không tới được đều thuộc khách có chuyến chưa đi tại T (`usingDate` ≥ T), tức giới hạn của split temporal; engine trượt-mpd trúng **4/102** (`filtered` 1, `mmr_demoted` 1, `ranked_low` 1, `wrong_active_trip` 1).

## 5. Kiểm nhanh P1 `VP0000001` (Day 1 C)

Lệnh `user --id VP0000001 --k 5`, `as_of` 2026-09-24, 12 event lịch sử, cùng engine production (không HTTP).

| Kỳ vọng (lịch Day 1 C, tiêu chí 17 spec search-recommendation) | Kết quả |
|---|---|
| `strategy = cross_vertical` | đạt |
| `excludedVerticals = ["hotel"]` | đạt |
| Không có item hotel | đạt: flight, golf, attraction, flight, attraction (đều Nha Trang, mỗi món có `because`) |
| `nextVertical ∈ {flight, attraction}` | đạt: `flight` |
| Response khớp `RecommendationResponse` | 0 lỗi; dư field `sections` ngoài contract (I-4) |

`latencyMs` 47, `eventsUsed` 12, `trips` 8. Chưa kiểm trên cloud (cần backfill và backend VM).

## 6. Issue Day 1 (ghi nhận, chưa sửa)

| # | Vấn đề | Chỗ | Việc của |
|---|---|---|---|
| I-1 | `nextVertical` là taxonomy xuất hiện nhiều nhất trong kết quả; combo/golf không bị loại khi đã đặt khách sạn nên có thể thành `nextVertical`. P1 lần này ra `flight`, nhưng ở rank 2 đã là golf | `application/recommendation/use_cases.py` (mask, `nextVertical`) | C Day 4 |
| I-2 | Trang rỗng của `/search` hard-code `cutoff: 0.62`, trong khi `settings.search_cutoff` mặc định 0.52 (`.env.example` 0.62) | `api/v1/routes/search.py` | C |
| I-3 | Seed không gắn `event_group_id` cho view/cart/search → engine gom mỗi sản phẩm thành trip `_solo_`. Một view **sau** purchase trở thành trip đang mở, làm mất `cross_vertical` và category exclusion (test `test_later_view_without_group_takes_over_the_open_trip`) | `use_cases.py` (`trip_id`), `profile.py` (`active_trip`) | C Day 4 + Data |
| I-4 | Engine trả `sections` (và `trips`, `popularitySource` trong diagnostics) không có trong `recommendations.yaml`; hợp lệ vì schema không cấm field lạ | `use_cases.py` | RecSys + Web |
| I-5 | `MAX_PER_VERTICAL = 2` cộng category exclusion → `k = 20` chỉ trả 1–9 món (TB 5,3), nên Recall@20 = Recall@10. Spec §4.7 nói giới hạn 2 món mỗi `parentProductId`, không phải mỗi taxonomy | `domain/recommendation/profile.py` | M6 (Day 5–6) |
| I-6 | `main.build_recsys` dựng popularity không truyền `now`, nên production dùng giờ thật; `PostgresCdpReader.purchase_events` không có cận trên | `main.py`, `postgres_cdp_reader.py` | ghi nhận; harness đã tự cắt |
| I-7 | Engine không loại event sau `now` mà kẹp `days_ago` về 0 (test `test_engine_itself_does_not_drop_future_events`) | `use_cases.py` | ghi nhận; harness chặn từ đầu vào |

## 7. Giới hạn và việc tiếp theo

- Day 2 (B): hai baseline most-popular / most-popular-in-destination và kiểm thứ tự đã làm 30/09 (§4.4); `sanity` 01/10 (§2.1)
  PASS 5/5 kiểm tra cứng. Phase 0 (01/10): split đóng băng §3.1, NDCG@5, `ids` / `rankStrict` theo khách, `configHash` — §4.6.
  Phase 1 (01/10): ceiling §4.7, phân khúc §4.8, strict/lenient §4.9, 20 ca + `engine_nommr` §4.10, findings §4.11. Phase 3
  (01/10): offline = HTTP 60/60 §4.12. M6 (02/10): FR-REC-02 chốt, engine đổi luật trip mở + N = 14 (§4.14); grid lần 1 §4.13.
- Split temporal (as_of = T) đo "mua gì sau T", không phải "gợi gì ngay trước lúc mua chuyến kế": 10/21 target bị chặn là chuyến
  chưa đi tại T. Việc tiếp theo: split "next trip" (as_of = ngay trước purchase kế, trip trước đã kết thúc theo `usingDate`).
- **I-5** đã xử lý ở harness (30/09): `engine` = mode eval bỏ cap để đo đủ k = 20; `engine_prod` báo list production.
  Spec §4.7 nói giới hạn 2 món mỗi `parentProductId`, code giới hạn 2 mỗi taxonomy — lệch spec/code này vẫn còn, là việc
  của C (M6), production chưa đổi.
- Số 30/09 đo trên seed 2026-09-21 (máy A); Day 1 trên seed 2026-09-23 (máy B). Muốn một bộ số thống nhất thì seed lại
  cùng snapshot (`make demo-db AS_OF=2026-09-24 SEED=42`) rồi chạy lại hai lệnh ở §4.4.
- Temporal hiện chỉ giữ một target mỗi khách (purchase đầu tiên ≥ T). Muốn đo nhiều target thì cần đổi metric.
- Availability đo theo trạng thái catalog hôm nay, không theo `as_of`.
- p95/p99 là thời gian xếp hạng offline (Weaviate local, không HTTP, không đọc CDP) — không thay số đo trên cloud.
  Số trên cloud đo bằng `http-latency` (§1), nhưng chỉ **guest path** cho tới khi ops mở IAP: một khách `popular` lặp
  lại, không phải 60 khách của brute-force check — ghi rõ khi trích dẫn.
