# vbench — benchmark chọn vector database (fast-track)

Cài theo `docs/spec/vector-bench/spec-fasttrack.md` §4, chi tiết từ `docs/spec/vector-bench/spec.md`. Chạy thật 3 engine: pgvector 0.8.6,
Qdrant 1.19.1, pgvectorscale 0.9.1. Đo ở catalog thật (2.897 search unit từ snapshot 10.320 sản phẩm) và 1M vector khuếch đại
từ catalog. Quy tắc chốt viết sẵn ở fasttrack §6 và được cài trong `vb fast-report`.

Toàn bộ code nằm trong thư mục này. Ngoài thư mục chỉ có một dòng `bench_out/` trong `.gitignore`. Dữ liệu, kết quả và backup nằm ở
`<repo>/bench_out/` (không commit).

## Cài đặt

```bash
python -m venv .venv-vbench                      # ở gốc repo; venv tự tạo .gitignore bên trong
.venv-vbench/Scripts/python -m pip install -r src/evaluation/vector_bench/requirements.txt
.venv-vbench/Scripts/python -m pip install -r src/evaluation/vector_bench/requirements-extra.txt   # bge-m3 (torch)
cd src && ../.venv-vbench/Scripts/python -m evaluation.vector_bench doctor
```

`vb` = `python -m evaluation.vector_bench`, chạy từ `src/`. Trên Windows đặt `PYTHONUTF8=1`.

## Lịch chạy thật (fasttrack §5)

```bash
vb doctor
vb dataset catalog --source jsonl          # mặc định: src/data_collection/data/snapshots/2026-09-21/products.jsonl (make demo-db đã bung)
vb embed --scale catalog                   # bge-m3 trên CPU: ~46 phút cho 2.897 item trên máy Core Ultra 5 (spec ước < 5 phút)
vb queries --scale catalog
vb embed --scale catalog --target queries  # ~2,5 phút
vb gt --scale catalog
vb scale-data 1m --vectors amplify         # tự gọi queries --reuse-query-vectors catalog và gt; ghi kiểm LID vào stats.json
vb --run <RUN> fast                        # pgvector → qdrant → pgvectorscale, chặn 35 phút mỗi engine
vb --run <RUN> fast-report                 # bench_out/runs/<RUN>/fast_report.md + fast_decision.json
```

Chạy thử khung với dữ liệu fake, không cần model hay mạng (đặt `VBENCH_HOME` riêng để không đè dữ liệu thật):

```bash
export VBENCH_HOME=<repo>/bench_out/_fake
vb dataset catalog --source fake --n 5000 && vb embed --scale catalog --backend fake
vb queries --scale catalog && vb embed --scale catalog --target queries --backend fake && vb gt --scale catalog
vb scale-data 100k --vectors fake                                   # hoặc --vectors amplify
vb perf null --scale catalog --rates 100,200 --duration 30          # hiệu chỉnh harness: P99 < perf.harness_max_p99_ms
vb --run test fast --scales catalog,100k --perf-duration 15 --perf-warmup 5 && vb --run test fast-report
```

Lệnh lẻ: `vb engine up|down|restart|status <engine> [--volumes]` · `vb load <engine> --scale S [--index NAME]` ·
`vb smoke <engine>` · `vb quality <engine> --scale S [--sweep full|fast]` · `vb gate <engine>` · `vb perf <engine> --scale S`.

Test: `pytest src/evaluation/vector_bench/tests` (unit) · `pytest -m integration src/evaluation/vector_bench/tests` (cần engine đang chạy).

## Cấu hình

`config/vbench.yaml` là file DUY NHẤT chứa con số. Mục `fast:` chứa phạm vi fasttrack: engine, index mặc định của engine, sweep,
mức tải 100/200 QPS × 90 s, chặn 35 phút, tham số khuếch đại. Ngưỡng chốt không lặp lại ở đây mà đọc từ `quality.a1_pass` và
`scoring.metrics.B1/B3/C1`. `docker/.env` do `vb doctor` sinh từ `.env.example`.

## Lệch so với spec — có đo, có lý do

| Chỗ | Spec | Cài | Lý do (đo 22/09 trên máy này) |
|---|---|---|---|
| GUC truy vấn Postgres | `BEGIN; SET LOCAL …; query; COMMIT` | `SET` mức session, chỉ gửi khi cấu hình đổi | Transaction + set_config thêm ~3 ms/query (3–4 round trip); pipeline mode psycopg kẹt ~140 ms trên Docker Desktop; gộp một message ~50 ms. Mỗi connection của bench chỉ phục vụ một cấu hình → tương đương; production làm được bằng `server_settings` của pool |
| Lexical | cột `tsv` + GIN, sparse bm25 Qdrant | không tạo | fasttrack bỏ lexical hôm nay; không để B3/C1 gánh chi phí kênh chưa đo |
| `shm_size` | 2g | `PG_SHM_SIZE=5g` trong `fast.pg_env` | build HNSW song song cấp DSM ≈ `maintenance_work_mem` (4GB) trong /dev/shm; thiếu thì CREATE INDEX lỗi ngay |
| Ảnh pgvectorscale | `timescale/timescaledb-ha:pg16` | ghim `pg16.15-ts2.30.1` (cùng digest) + `NO_TS_TUNE=true` | tag trôi; timescaledb-tune đổi random_page_cost, effective_cache_size, parallel workers → không công bằng với container pgvector |
| Cột vector pgvectorscale | halfvec nếu diskann hỗ trợ | `vector(1024)` fp32 (probe bảng tạm mỗi lần create) | diskann 0.9.1 không có opclass halfvec |
| Nạp Qdrant | `upsert(wait=True)` theo lô | như spec, nhưng tắt index khi upload rồi trả `indexing_threshold` về mặc định server | thực hành nạp lô của Qdrant; cấu hình cuối vẫn là mặc định |
| Client Qdrant | — | gRPC | HTTP của client tắt keep-alive với localhost |
| Timeout trong quality | không nêu | `perf.timeout_ms` mỗi query | tránh một cấu hình chậm ăn hết khung 35 phút; query > 1 s đằng nào cũng trượt B1 |
| Harness Windows | — | tắt EcoQoS, HIGH_PRIORITY_CLASS, `OPENBLAS_NUM_THREADS=1`, SimpleQueue, spin nhường GIL | không có thì `vb perf null` P99 2–32 ms; có thì ~0,85 ms |
| Text builder | fallback nếu repo chưa có | dùng `src/backend/app/domain/catalog/text_builder.py::build_text` cho jsonl | spec §1.1; fake dùng fallback P1.4 |
| Build diskann | "diskann mặc định" | tham số index mặc định, nhưng `ANALYZE` trước build + `diskann.force_parallel_workers` = `max_parallel_maintenance_workers` | vectorscale 0.9.1 mặc định build TUẦN TỰ (100k: 202–227 s, 1 lõi); cả hai cùng bật → 4 worker, 79 s. Cùng ngân sách song song fasttrack §4 cấp cho pgvector; chỉ ảnh hưởng B3 |
| Lưới sigma khuếch đại | {0,05; 0,1; 0,2; 0,3} | {0,05 … 0,6} (người chạy quyết 22/09) | trên bge-m3 thật σ ≤ 0,3 trượt LID (0,747); lưới rộng → hiệu chỉnh chọn 0,6, trượt LID 1,64 → lùi 0,5 (LID 1,286, qua) |
| Recall P6.1 | `min(trúng, |G|)/|G|` | mẫu số `min(|G|, k − số dòng vùng biên engine trả)` | công thức chữ phạt cả engine exact đúng khi dòng vùng biên chiếm chỗ trong top-k — mâu thuẫn P3.1 #4 ("không tính miss") và Done "exact A1 = 1" |

## Kết quả lượt chạy 22–23/09 (`bench_out/runs/fast-20260922/`)

**CHƯA CHỐT.** Catalog: cả ba engine G3 pass, A3 = 1,0, count exact 100%; A1 = 1,0 (Qdrant) / 0,992 (pgvector) / 0,767
(pgvectorscale). 1M: chỉ pgvector đo đủ (A1 0,553 trượt, B1 trượt, B3 6,3 phút, C1 10,7 GB); Qdrant và pgvectorscale bị cắt ở
khung 35 phút/engine khi build index. Chi tiết và cách đọc số: `history/2026-09-23-vector-bench-ket-qua-fast-track.md`.

Ba điều phải nhớ khi đọc lại các số này:

1. **A1 chỉ là số ANN khi index ANN thật sự chạy.** Bảng report có dòng "index ANN thật sự dùng": Qdrant ở catalog là
   `0/2897 vector đã index` (segment dưới `indexing_threshold` → brute force), pgvector là `plan dùng index 0%` cho query có filter.
2. **A1 ở 1M không phải kết luận chất lượng.** Metadata kế thừa làm filter chọn nguyên cụm: dòng khớp thứ 10 nằm ở hạng ~7.800
   (b10) / ~39.500 (b1) trong thứ tự không lọc, trong khi trên catalog thật là hạng 1–2. Ngưỡng A1 ≥ 0,95 ở 1M (§6) mâu thuẫn với
   §3 ("số 1M không dùng cho chất lượng tìm kiếm").
3. **P99 trong bảng bị kẹp trần ở timeout.** Đọc `status_split` và `uncapped_ms` trong `perf.json` mới ra latency thật.

## Việc còn mở

- **Lưới sigma của khuếch đại (fasttrack §3)** — đã chốt 22/09 (mở rộng tới 0,6). Trên vector bge-m3 thật: c1 = 0,824; σ 0,3 → LID
  0,747; 0,35 → 0,851; 0,4 → 0,977; 0,5 → 1,286; 0,6 → 1,636 (cos 0,831 ≈ c1). Khớp c1 và qua LID không cùng lúc được — ghi vào
  báo cáo; 1M dùng σ = 0,5.
- Sàn transport của Docker Desktop trên Windows cộng vào mọi latency (pg `SELECT 1` ~0,7 ms, Qdrant gRPC vài ms). `fast_report.md`
  in sàn này cạnh P99.
- Số `~5.000 vector` trong `vector-db-selection.md` §2 → thực tế 2.897 (chưa sửa doc, nằm ngoài thư mục được phép sửa).
- Muốn chốt engine: `fast.max_minutes_per_engine` ≥ 90 rồi `vb fast --engines qdrant,pgvectorscale` (Qdrant cần ~45 phút cho 1M).
- Muốn A1(1m) có nghĩa: dùng vector 1M thật (đối chứng Wikipedia-vi, fasttrack §7) hoặc sửa bước kế thừa metadata của §3 để filter
  không chọn nguyên cụm; nên thêm chỉ số "hạng không lọc của dòng khớp thứ k" vào `stats.json` của amplify.
- pgvectorscale: `query_rescore` mới là tham số quyết định recall (không phải `query_search_list_size`); cân nhắc đưa vào sweep.
