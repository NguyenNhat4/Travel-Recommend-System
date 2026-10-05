# Harness RecSys đọc vector `.npy` của search bench (e5-small / e5-base) + sửa import `Protocol` của backend

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành
- Phạm vi: evaluation, backend (sửa lỗi import)
- Phục vụ: FR-REC-01..04, FR-SRC-02, NFR-PERF-01; plan `docs/plan/2026-10-05-bench-recsys-e5-small.md` Day 6 (6.2–6.7)

## Mục tiêu

Nhóm chốt e5-small / 384 thay Cohere v3 (05/10). Cần đo RecSys bằng vector e5-small và e5-base đã embed ở search bench (3.183 unit,
`catalog-text-v2`), không embed lại, không cần Weaviate. Harness trước đây chỉ lấy vector theo `modelVersion` Cohere của settings backend.

## File thay đổi

- `src/evaluation/recsys_bench/data_source.py` — sửa: thêm chế độ `--vectors npy:<prefix>` (`read_npy_vectors`, `_npy_index`):
  đọc `<prefix>.npy` + `.ids.json` + `.meta.json` → `NumpyVectorSearch`; `modelVersion = <cache_model>:<text_builder_version>`; từ chối khi
  số dòng ≠ số id, id trùng, `dim` lệch, text builder ≠ `TEXT_BUILDER_VERSION`, chưa chuẩn hoá L2 (atol 1e-3), thiếu `cache_model`, hoặc
  < 50 % search unit có vector; ghi provenance (`prefix`, `cacheModel`, `dim`, `itemsSha256`, `textSha256`, `npySha256`, `nFile`, `nUsed`).
- `src/evaluation/recsys_bench/__main__.py` — sửa: help `--vectors` nêu `npy:<prefix>`; `summary.json` thêm `vectorsSource`.
- `src/evaluation/recsys_bench/tests/test_npy_vectors.py` — thêm: 8 test đọc / từ chối file vector.
- `src/backend/app/application/ports/unit_index.py` — sửa: thêm `from typing import Protocol`.
- `history/2026-10-05-recsys-bench-npy-vectors.md` — thêm: entry này.

## Quyết định

- Sửa `unit_index.py` một dòng: merge `3a11433` ("merge research recsys", 02/10) thêm `VectorStorePort` / `CdpClientPort` dùng `Protocol`
  mà không import → mọi import backend trên nhánh này lỗi `NameError` (17 lỗi collection ở `recsys_bench/tests`). Không xoá hai Protocol
  thừa và không đụng đoạn method chết mà cùng merge chèn vào cuối `_to_profile` của `infrastructure/cdp/local_cdp_client.py` (sau
  `return`, không chạy) — để chủ merge (tqanh123) dọn.
- DB bench là Postgres **riêng** (compose project `wt-seed`, cổng 55433, worktree sạch `HEAD 942f5aa` trong scratchpad) để không xoá DB demo
  local (seed 29/09, 11.708 sản phẩm). Seed: snapshot `2026-09-23`, `AS_OF=2026-09-24`, `SEED=42` (plan 6.3).
- `compare` không đổi; so e5-small với e5-base giữa hai run làm bằng script phụ lục report (plan 7.6).

## Kiểm tra

- `make demo-db` (cổng 55433, snapshot 09-23): `db/verify.sql` và `db/verify_insider.sql` PASS toàn bộ (gồm `products >= 11387`).
- `recsys_bench doctor`: catalog 3.183 search unit · 2.384 recommendable; CDP 7.145 event, as_of suy ra 2026-09-24 (khớp plan 6.3).
- `pytest -q src/evaluation/recsys_bench/tests` (vsf2, sau khi cài `implicit 0.7.3`, `threadpoolctl`): trước sửa import 17 lỗi
  collection; sau sửa 119 passed; sau thêm test `.npy` **127 passed**.
- Smoke 6.6 `run --arm random --arm most_popular_in_destination --arm engine --split llbo --vectors npy:…/vec_T3+R_e5-small --split-file
  frozen/split-llbo-asof20260924.json --limit-users 50` (run `2026-10-05-smoke-e5s`): exit 0, `frozenSha256 1c31d43cfc28` khớp,
  `vectorsMissing 0`, `modelVersion intfloat/multilingual-e5-small:catalog-text-v2`, `configHash b0aee886`.
- Chưa chạy test backend đầy đủ.

## Còn lại / rủi ro

- Plan 6.1: báo tqanh123 phạm vi sửa `data_source.py` + review — người dùng làm.
- Day 7–8 (chạy đủ bench hai model, report) ghi ở entry riêng.
- Container `wt-seed-postgres-1` (cổng 55433) và worktree scratchpad còn chạy để làm Day 7; dọn sau khi xong.
