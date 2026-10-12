# Latency đầu-cuối `/recommendations` TRƯỚC khi đổi engine (lane A1)

- Ngày chạy: 2026-10-08 (tối, giờ VN)
- Phục vụ: NFR-PERF-01 (`docs/prd/requirements.md` §2.1), tiêu chí G1 "Δp95 ≤ 50 ms" của
  `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §4; FR-REC-01/02/04
- Plan: `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` lane A1
- Kết quả gốc: `src/evaluation/recsys_bench/theme_study/results/2026-10-08-lane-a/` (`e2e-before-*.json`,
  `parity-prodcopy.json`, hai file tập khách)
- Engine đo: `feat/recSys_update` @ `1b5af92` — phần RecSys **chưa đổi**, = production 08/10 (`release-mvp-v2` @ `6f77e80`)

## 1. Vì sao cần số này

Mọi lựa chọn G2 (ship phần miễn phí / G6 / F14c + destCap2) đều phải qua tiêu chí latency trước deploy. Số ranking-only
08/10 (p95 38,63 → 39,26 ms) không đủ: ô khám phá B cần thêm **một lượt `near_vector`** cho khách có chuyến mở mà list
ngắn, và chỉ đo đầu-cuối mới thấy. Số ở đây là mốc TRƯỚC; lượt SAU (PR-A, PR-B) chạy **cùng env, cùng collection, cùng hai
file khách**, xen kẽ trước / sau.

## 2. Môi trường

| | |
|---|---|
| Postgres | `vota-prodcopy-pg` 127.0.0.1:55433 / `vota_prodcopy` (bản sao production 08/10 01:49) |
| Weaviate | `sbench-weaviate-1` v1.37.3, 127.0.0.1:58080 (REST) / 55051 (gRPC) — **collection mới** `ProductE5SmallProdcopy`, 3.991 object nạp từ `vec_prodcopy_e5s.npy` của gói bàn giao bằng `theme_study/load_npy_weaviate.py` (không cài torch, không re-embed). Các collection `ProductBench_*` của search bench không đụng (vẫn 3.183) |
| Kiểm collection | `python -m src.backend.jobs.embed_products --dry-run` → `searchUnits 3991, unchanged 3991, embedded 0, deletedOrphans 0` |
| Backend | `.venv/Scripts/python.exe -m uvicorn src.backend.app.main:app --host 127.0.0.1 --port 8000` (1 worker, không reload); env ghi đè `.env`: ba DSN → 55433, `WEAVIATE_URL` local, `VECTOR_COLLECTION=ProductE5SmallProdcopy`, `APP_ENV=development`, `INTERNAL_API_ENABLED=true`, `AUTH_SERVICE_TOKEN` 64 hex, mọi `*_REDIS_URL` rỗng, `CDP_ADAPTER=local`, `PAYMENT_PROVIDER=fake`, `ITINERARY_USE_LLM=false`, `ITINERARY_DATA_MODE=fixture`, `SEARCH_PREWARM=false` (e5 nạp lười → không cần torch), `CATALOG_REFRESH_SECONDS=86400`, `BOOKING_RECONCILE_INTERVAL_SECONDS=0`, `PYTHONUTF8=1` |
| Khởi động | `startup.recsys.index.load.ready search_units=3991`; **không** có `recsys.vectors.out_of_sync` |
| Đường đo | `GET /api/v1/internal/recommendations?cdp_user_id=…&k=4` với `X-Service-Token` (không JWT); guest `GET /api/v1/recommendations?k=4` |
| Máy | Windows 11, không job đo nào khác chạy cùng lúc (hai job `eval_profile` coldstart chạy **sau** lượt này) |

## 3. Parity offline == HTTP (điều kiện để tin số latency)

`recsys_bench parity --base-url http://127.0.0.1:8000 --users users60-prodcopy.json --k 5 --vectors weaviate`:
**PASS 60/60** — 60 khách (4 persona + 56 phân tầng theo lifecycle) trùng hoàn toàn với `OfflineEngine(mode="prod")` (ids,
strategy, destination, excludedVerticals, số món). Tức backend local trên collection nạp từ `.npy` = engine đã đo offline.

## 4. Kết quả TRƯỚC

`http-latency --runs 6 --k 4 --drop-first` (bỏ lượt 1 làm nóng → 300 mẫu / file); số đầu = `diagnostics.latencyMs` (server:
đọc CDP + Weaviate + xếp hạng; không gồm HTTP / auth), `client_ms` = tổng phía client.

| Tập khách | n | server p50 | server p95 | client p50 | client p95 |
|---|---:|---:|---:|---:|---:|
| `users-strata.json` (20 chuyến mở / 20 đã mua, không chuyến mở / 16 chỉ xem / 4 persona) | 300 | 66.0 | **87.0** | 69.1 | 89.8 |
| `users60-prodcopy.json` (4 persona + 56 theo lifecycle) | 300 | 67.0 | **86.0** | 70.2 | 89.1 |
| guest (`--runs 11`, một khách `popular`) | 40 | 9.0 | 9.0 | 12.5 | 13.4 |

Theo `strategy` (từ `samples[].strategy`, ms):

| strategy | n (strata) | server p50 | server p95 | n (users60) | server p50 | server p95 |
|---|---:|---:|---:|---:|---:|---:|
| `long_term` (không chuyến mở — nhánh F14c / destCap2 sẽ chạy) | 228 | 70.0 | 87.6 | 174 | 71.0 | 86.0 |
| `dormant` (không chuyến mở) | 54 | 70.5 | 89.0 | 108 | 70.5 | 87.0 |
| `cold_start_content` (chuyến mở chỉ xem, < 3 event — nhánh ô B) | 42 | 57.0 | 69.0 | — | — | — |
| `recent_activity` (chuyến mở chỉ xem — nhánh ô B) | 30 | 50.5 | 73.1 | 6 | 51.0 | 67.2 |
| `popular` | 6 | 21.5 | 43.5 | 72 | 34.5 | 44.0 |

Không có mẫu `cross_vertical`: bản sao 08/10 chỉ có 1 khách có purchase với `usingDate` ≥ 08/10 (không nằm trong 60), và chuyến
Nha Trang của P1 đã kết thúc 05/10. Nhánh ô B vẫn được đại diện bởi `recent_activity` / `cold_start_content` (cùng khoá điểm
đến, cùng cap 2 món / loại → list ngắn).

Đối chiếu: NFR-PERF-01 p95 ≤ 250 ms (đạt ở local); hợp đồng §7.1 300 / 800 ms; lượt local 05/10 (60 khách, Cohere, 3.183
unit) p50/p95 72 / 86 ms — cùng cỡ.

## 5. Tiêu chí G1 áp cho lượt SAU

- Δp95 của **server `latencyMs`** ≤ 50 ms, tính trên **cùng** `users-strata.json` và `users60-prodcopy.json`, tổng **và** theo
  từng `strategy`; `client_ms` báo kèm. Chạy xen kẽ TRƯỚC / SAU / TRƯỚC / SAU (restart backend giữa các lượt) để khử trôi máy.
- Caveat: số local không chứng minh được chi phí lượt `near_vector` thêm của ô B trên Weaviate Cloud khác region
  (05/10: cá nhân hoá p50 820 ms trên cloud). Nếu cần đo cloud: IAP + service token; ngoài phạm vi lượt này.

## 6. Lệnh tái sinh

```bash
# 1. Collection mới từ .npy (một lần)
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55433/vota_prodcopy WEAVIATE_URL=http://127.0.0.1:58080 \
       VECTOR_COLLECTION=ProductE5SmallProdcopy
python -m src.evaluation.recsys_bench.theme_study.load_npy_weaviate /đường/dẫn/vectors/vec_prodcopy_e5s
python -m src.backend.jobs.embed_products --dry-run          # unchanged 3991, embedded 0

# 2. Backend (env như §2), rồi
python -m src.evaluation.recsys_bench parity --make-users --users users60-prodcopy.json --seed 42
python -m src.evaluation.recsys_bench parity --base-url http://127.0.0.1:8000 --users users60-prodcopy.json --k 5 \
       --vectors weaviate --token-env AUTH_SERVICE_TOKEN --run-id <id>              # PASS 60/60
python -m src.evaluation.recsys_bench http-latency --base-url http://127.0.0.1:8000 --users users-strata.json \
       --token-env AUTH_SERVICE_TOKEN --runs 6 --k 4 --run-id <id>-strata
python -m src.evaluation.recsys_bench http-latency --base-url http://127.0.0.1:8000 --users users60-prodcopy.json \
       --token-env AUTH_SERVICE_TOKEN --runs 6 --k 4 --run-id <id>-users60
python -m src.evaluation.recsys_bench http-latency --base-url http://127.0.0.1:8000 --runs 11 --k 4 --run-id <id>-guest
# p50/p95 theo strategy: đọc bench_out/recsys/runs/<id>/http_latency.json, nhóm samples[] theo `strategy`, bỏ run 1
```

`users-strata.json` được chọn bằng SQL read-only trên `vota_prodcopy` (20 khách có event ≤ 14 ngày hoặc purchase `usingDate` ≥
08/10; 20 khách đã mua nhưng không hoạt động gần đây; 16 khách chỉ xem; 4 persona), sắp theo `md5(cdp_user_id)`.
