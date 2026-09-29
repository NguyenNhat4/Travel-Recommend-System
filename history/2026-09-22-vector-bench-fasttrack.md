# vbench fast-track: benchmark chọn vector DB (pgvector, Qdrant, pgvectorscale)

- Ngày: 2026-09-22
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/vector-db
- Trạng thái: dang dở
- Phạm vi: evaluation

## Mục tiêu

Cài `docs/vector_bench/spec-fasttrack.md` §4 (chi tiết theo `docs/vector_bench/spec.md`) theo thứ tự Part 0 → 1 → 2 → 3 → 4 → 5 → 7 → 8a → 10 (amplify) → 6 lite → 9 lite → 11 lite → `vb fast`. Sau mỗi Part chạy lệnh "Chạy thử" bằng dữ liệu fake và kiểm "Done khi". Sau đó chạy thật trên catalog mà `make demo-db` đã bung. Code chỉ nằm trong `src/evaluation/vector_bench/`, venv riêng `.venv-vbench`; ngoài thư mục này chỉ có một dòng `.gitignore`.

## File thay đổi

- `.gitignore` — sửa: thêm đúng một dòng `bench_out/`.
- `src/evaluation/vector_bench/` — thêm: toàn bộ package vbench.
  - `__init__.py`, `__main__.py` (CLI typer), `config.py`, `paths.py`, `results.py`, `doctor.py`, `lifecycle.py`.
  - `config/vbench.yaml`, `config/amenity_seed.yaml`, `config/query_templates.yaml`.
  - `docker/compose.yml` (3 profile), `docker/.env.example`.
  - `dataset/{__init__,catalog,amenities,textbuild,fake,items,scale}.py`.
  - `embed.py`, `filters.py`, `querygen.py`, `lexical.py`, `groundtruth.py`, `fast_report.py`.
  - `engines/{__init__,base,registry,pgvector,pgvectorscale,qdrant,selectivity,null}.py`.
  - `runners/{__init__,load,smoke,recall,quality,gates,perf,timing,resources,fast}.py`.
  - `tests/{__init__,conftest,test_catalog,test_filters,test_groundtruth,test_recall,test_scale,test_gates,test_fast_report,test_translate_pgvector,test_translate_pgvectorscale,test_translate_qdrant,test_integration_engines}.py`.
  - `requirements.txt`, `requirements-extra.txt`, `README.md`.

## Quyết định

- Text builder: dùng `src/backend/app/domain/catalog/text_builder.py::build_text` cho `--source jsonl` (spec §1.1). `--source fake` dùng fallback P1.4.
- Nguồn catalog: `src/data_collection/data/snapshots/2026-09-21/products.jsonl`, do `make demo-db` bung từ snapshot có checksum. Đường dẫn mặc định trong spec không tồn tại. Số search unit thật là **2.897**, không phải ~5.000.
- Mọi mục VERIFY đều tra bằng workflow research, có agent kiểm độc lập và thử trên container thật:
  - pgvector 0.8.6: GUC `hnsw.*`, `set_config`, COPY nhị phân cần `HalfVector` và `uuid.UUID`.
  - pgvectorscale 0.9.1: diskann không có halfvec nên dùng `vector(1024)` fp32; query phải cast `::vector`.
  - Qdrant 1.19.1: `indexing_threshold=0` là tắt index; ACORN có từ 1.16; HTTP của client tắt keep-alive với localhost nên dùng gRPC.
- Các chỗ lệch spec (có đo, ghi trong README của package):
  - GUC Postgres đặt ở mức session thay cho SET LOCAL trong transaction. Transaction tốn thêm ~3 ms/query; pipeline mode kẹt ~140 ms trên Docker Desktop.
  - Không tạo lexical (tsv/GIN, sparse bm25) vì fasttrack bỏ phần này hôm nay.
  - `PG_SHM_SIZE=5g`: build HNSW song song cần /dev/shm ≥ `maintenance_work_mem` (4GB); fasttrack ghi `shm 2g`, mâu thuẫn.
  - Ghim `timescaledb-ha:pg16.15-ts2.30.1` và đặt `NO_TS_TUNE=true` để planner hai engine Postgres giống nhau.
  - Qdrant tắt index trong lúc nạp lô, sau đó trả về mặc định của server.
  - Timeout mỗi query trong quality lấy từ `perf.timeout_ms`.
  - Harness Windows: tắt EcoQoS, HIGH_PRIORITY_CLASS, `OPENBLAS_NUM_THREADS=1`, SimpleQueue, spin nhường GIL.
- Recall P6.1: item vùng biên mà engine trả thì không đẩy mẫu số, tức mẫu số = min(|G|, k − số item vùng biên). Công thức chữ của P6.1 phạt cả engine exact đúng, mâu thuẫn P3.1 #4 và tiêu chí Done "exact A1 = 1".
- Workflow review đối kháng (5 chiều, 34 agent) xác nhận 11 lỗi thật, đã sửa hết:
  - `Table.take` chuyển CSR mỗi lần gọi.
  - Thống kê auto bị `statement_timeout` cắt.
  - Cache GUC không xoá khi reconnect; auto→exact RESET GUC qua lại.
  - Report coi engine chưa đo là trượt; quy tắc hoà theo CI P99 chưa áp; cổng LID mở khi dữ liệu không phải amplify; report đọc nhầm kết quả cũ cùng run.
  - Khởi động và pool worker nằm ngoài try/finally.
  - `achieved_qps` tính từ lịch.

## Kiểm tra

- `pytest src/evaluation/vector_bench/tests`: 60 passed, 3 skipped (integration cần engine).
- `pytest -m integration` từng engine (catalog fake 2.000, mọi loại filter): pgvector, Qdrant, pgvectorscale pass (precision 1,0, exact recall 1, count = evaluator).
- Chạy thử từng Part bằng fake:
  - doctor exit 0; engine up healthy sau 4,4 s; `down --volumes` sạch.
  - catalog fake 5.000; embed fake 0,5 s, lần hai `re-embedded: 0`.
  - 1.000 query đủ quota, sha256 tất định; GT tự kiểm 50/50 và 20/20.
  - smoke exact 0 vi phạm cho cả 3 engine; G3 pass.
  - `vb perf null`: P99 0,82–0,85 ms (< 2 ms).
  - `vb --run fasttest fast --scales catalog,100k` chạy hết 3 engine: pgvector 6,5 phút, Qdrant 2,9, pgvectorscale 22,5. `fast-report` ra "CHƯA CHỐT — catalog fake", đúng thiết kế.
- Chạy thật trên catalog:
  - `dataset catalog --source jsonl`: 2.897 search unit.
  - `embed` bge-m3 trên CPU: 2.780 s (spec ước < 5 phút).
  - `queries` 1.000 dòng, đủ quota; `embed --target queries` 143 s; `gt` pass.
  - `scale-data 100k --vectors amplify` trên vector thật: LID ratio 0,747 → FAIL (xem mục dưới).

## Còn lại / rủi ro

- **Chờ chốt:** lưới sigma của fasttrack §3 ({0,05; 0,1; 0,2; 0,3}) không đạt c1 = 0,824, và LID ratio ở σ = 0,3 là 0,747 < 0,75. Thử thêm: σ 0,35 → 0,851; 0,4 → 0,977; 0,5 → 1,286; 0,6 → 1,636. Cần người quyết lưới sigma trước khi chạy `scale-data 1m` + `vb fast` + `fast-report`.
- Chưa sửa con số "~5.000" trong `docs/vector_bench/VECTOR_DB_SELECTION.md` §2 thành 2.897, vì file này nằm ngoài thư mục được phép sửa.
- Build diskann chậm: 100k mất 280 s. Nếu tăng tuyến tính, ở 1M sẽ vượt khung 35 phút; khi đó report ghi `partial` / chưa chốt.
- Latency đo qua port-forward của Docker Desktop trên Windows: sàn transport pg ~0,4–0,7 ms, Qdrant ~0,9 ms (p99 ~2,9 ms). Report in sàn này cạnh P99.
- Stack app (p205-*, 2 container Postgres) đang chạy cùng máy; fasttrack §2.6 khuyên tắt khi đo.
