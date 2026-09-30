# Đánh giá offline engine Recommendation trên DB seed

- Phục vụ: **FR-REC-01..04**, **NFR-PERF-01** (`docs/prd/requirements.md`); `docs/prd/test-plan.md` §2.5; handbook §11–§12.
- Code: `src/evaluation/recsys_bench/` (nhánh `bench/recsys-harness`). Số thô: `bench_out/recsys/runs/<run_id>/` (không commit).
- Thay cho `eval/report.md` của lịch 10 ngày (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md` §0.1).
- Cập nhật lần cuối: 2026-09-29 (Day 1). Mọi số dưới đây phải sinh lại được bằng lệnh ở mục 1.

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
python -m src.evaluation.recsys_bench split --kind llbo    # hoặc --kind temporal [--T 2026-07-10]
python -m src.evaluation.recsys_bench run --arm random --arm engine --split llbo --vectors weaviate
python -m src.evaluation.recsys_bench user --id VP0000001  # một khách, như production, kiểm contract
python -m pytest -q src/evaluation/recsys_bench/tests      # không cần DB
```

- `--vectors weaviate`: giống `main.build_recsys`, mỗi request truy vấn top-K ở Weaviate. `--vectors numpy`: kéo toàn
  bộ vector một lần (REST) và quét chính xác trong RAM, dùng cho grid-search. `none`: chỉ catalog, cho arm random.
- `as_of` mặc định là 00:00 UTC ngày sau event cuối. `--as-of` cắt ngay ở kho (`all_events(until=…)`).
- Event được cache ở `bench_out/recsys/cache/` theo DB (host:port/db) và `as_of`. **Seed lại DB thì chạy kèm
  `--refresh`** (hoặc `doctor`, lệnh này luôn đọc lại), nếu không `load`/`split`/`run` dùng bản cũ.

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
| Thắng rõ most-popular-in-destination ở Recall@20, NDCG@10 | handbook §12 | chưa so | baseline Day 2 |
| Availability precision | ≥ 95 % | 100 % | engine lọc `available` trước; random cũng bốc trong tập đó |
| Catalog coverage | > 20 % | 20,7 % | sát ngưỡng |
| p95 `/recommendations` | ≤ 250 ms (PRD NFR-PERF-01) | 58 ms offline | Weaviate local, không gồm HTTP và đọc CDP; số cloud là Day 2 |

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

- Day 2 (B): `sanity.py` (lifecycle 25/45/20/10, ≥ 2 vertical 64 %, top-10 % sản phẩm 39 % purchase, Zipf 0,8) và hai
  baseline most-popular (cửa sổ 90 ngày như `Popularity.unit_scores`) và most-popular-in-destination (điểm đến của
  trip đang mở hoặc gần nhất). Kiểm thứ tự random ≪ most-popular < most-popular-in-destination trước khi đọc số engine.
- Temporal hiện chỉ giữ một target mỗi khách (purchase đầu tiên ≥ T). Muốn đo nhiều target thì cần đổi metric.
- Availability đo theo trạng thái catalog hôm nay, không theo `as_of`.
- p95/p99 là thời gian xếp hạng offline (Weaviate local, không HTTP, không đọc CDP) — không thay số đo trên cloud.
