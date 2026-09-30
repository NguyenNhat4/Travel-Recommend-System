# RecSys harness — Track B Phase 0: split đóng băng, config snapshot, NDCG@5, `ids` theo khách, chạy lại v3

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation (recsys_bench), docs spec bench

## Mục tiêu

Plan Day 3 (`docs/plan/2026-09-30-plan-day3.md`) Track B Phase 0 — B2 (đóng băng split, hash), B3 (ảnh chụp cấu hình engine +
`configHash`), B4 (NDCG@5), B7 phần dữ liệu (`ids` top-k, `targetProductId`, `rankStrict`) — rồi chạy lại v3 để mọi phân tích
sau (ceiling, phân khúc, 20 case) đọc từ thư mục run mà không cần Weaviate. Phục vụ FR-REC-01/02, test-plan §2.5, M5.

## File thay đổi

- `src/evaluation/recsys_bench/splits.py` — sửa: `events_sha256` (event đã lọc, không phụ thuộc thứ tự), meta `eventsSha256` /
  `eventsCount` ở cả hai split; `Split.canonical()`, `frozen_sha256()`, `freeze(path, db_as_of, dsn_label)`, `verify(path)`;
  `SplitMismatch` nêu khác ở params / eventsSha256 / targets.
- `src/evaluation/recsys_bench/engine.py` — sửa: `POPULARITY_WINDOW_DAYS` (chuyển từ `arms.py`), `PURCHASE_LOOKBACK_DAYS`,
  `engine_config(engine)` (mọi hằng viết hoa của `domain/recommendation/profile.py` + tham số harness), `config_hash`.
- `src/evaluation/recsys_bench/arms.py` — sửa: import `POPULARITY_WINDOW_DAYS` từ `engine.py` (tên vẫn export).
- `src/evaluation/recsys_bench/metrics.py` — sửa: `ndcg@5`.
- `src/evaluation/recsys_bench/report.py` — sửa: cột NDCG@5; `header(summary)`; `write_run` ghi thêm `per_user.jsonl`.
- `src/evaluation/recsys_bench/bench.py` — sửa: hàng theo khách thêm `ids`, `targetProductId`, `targetIsChild`, `rankStrict`.
- `src/evaluation/recsys_bench/paths.py` — sửa: `FROZEN_DIR`.
- `src/evaluation/recsys_bench/__main__.py` — sửa: `split --freeze [--freeze-path]`; `run --split-file` (lệch → mã 1);
  `summary.json` thêm `modelVersion`, `engineConfig`, `configHash` (+ `engineConfigProd`/`configHashProd` khi có `engine_prod`),
  `vectorsMissing`, `split.frozenSha256` / `splitFile`; in `header` trước bảng; docstring module.
- `src/evaluation/recsys_bench/frozen/split-llbo-asof20260922.json`, `split-temporal-asof20260922.json` — thêm: bản đóng băng
  (sha `29033b34…`, `a7735af1…`; 6.979 event sau lọc; 1.007 / 102 khách test).
- `src/evaluation/recsys_bench/tests/test_splits.py` — thêm 2 test (sha event không phụ thuộc thứ tự, nhạy nội dung; canonical /
  freeze / verify roundtrip, lệch params, lệch event, temporal). `tests/test_arms_metrics.py` — sửa/thêm: NDCG@5, hàng theo khách
  (u1 mua FL1 → target F1, `targetIsChild`, `rankStrict` None), `engine_config` / `config_hash` / `header`, `per_user.jsonl`.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 lệnh `--freeze` / `--split-file`, mô tả `summary.json` / `per_user.jsonl`;
  §3.1 bảng bản đóng băng; §4.6 bảng v3 (LLBO + temporal, có NDCG@5).

## Quyết định

- Đặt tên file đóng băng theo `as_of` suy ra từ DB (`asof20260922`), không theo ngày seed: đó là mốc thật sự quyết định split.
- `verify` so sha của phần canonical (kind, params, sha event đầu vào, từng target với productId gốc / trip / as_of / số
  event–purchase train); `frozenAt`, `dbAsOf`, `dsnLabel` chỉ để đọc. Lệch → dừng trước khi chạy arm nào.
- `engine_config` lấy **mọi** hằng viết hoa của `profile.py` bằng introspection thay vì liệt kê tay, để thêm hằng mới không lọt
  khỏi hash; harness thêm `mode`, `candidateK`, `popularK`, `maxPerVertical`, `popularityWindowDays`, `purchaseLookbackDays`.
- `rankStrict` giữ đúng nghĩa "đúng productId đã mua": với phòng / chuyến con luôn None vì engine chỉ trả search unit — bảng
  strict/lenient (B7) sẽ nói rõ, không đổi metric chính.
- Không đổi backend.

## Kiểm tra

- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/evaluation/recsys_bench/tests` → **39 passed** (trước 35).
- `split --kind llbo --freeze`, `split --kind temporal --freeze` → hai file `frozen/`.
- `run … --split-file … --run-id 2026-10-01-llbo-v3` (5 arm, Weaviate local): "split khớp bản đóng băng"; **mọi Recall/NDCG@10/Coverage
  bằng đúng v2** (engine 0,851 / 0,524; mpd 0,635 / 0,389; prod 0,591 / 0,460); NDCG@5 engine 0,497, prod 0,454, mpd 0,362.
  Temporal v3 = v2 (engine 0,196 / 0,144); NDCG@5 engine 0,135. `vectorsMissing 0`. `per_user.jsonl` có `ids`.
- Review đối kháng (workflow 3 lens: determinism/leakage, metric & hàng theo khách, wiring & quy tắc) → 3 lens / 8 agent, xác nhận 3 lỗi và đã sửa trong cùng thay đổi: (1) run --split-file so split với cache event JSONL thay vì DB → nay luôn đọc lại CDP khi có --split-file; (2) POPULARITY_WINDOW_DAYS / PURCHASE_LOOKBACK_DAYS chép số 90 / 730 → nay đọc từ chữ ký Popularity.unit_scores và CdpHistoryReader.purchase_events; (3) docstring trỏ "§8 spec" chưa có → §3.1, thêm quy ước tuning B10 vào §3.1 và cập nhật §7. Kèm các sửa nhỏ: split --freeze không đè file có sha khác (trừ --force), verify chịu JSON không phải object (không traceback), summary ghi limitUsers / usersEvaluated và header in SUBSET, vectorsMissing tính được ở mode numpy, test CLI (freeze → split-file khớp / lệch / file sai), bỏ assertion tautology. Bác bỏ: "thiếu history" (entry này), "rankStrict vô nghĩa" (đúng thiết kế, đã ghi chú). Test sau sửa: 40 passed.

## Còn lại / rủi ro

- Phase 1 (ceiling, 20 case, phân khúc, strict/lenient) đọc từ `bench_out/recsys/runs/2026-10-01-*-v3/` — chưa làm.
- Seed lại DB local thì phải `split --freeze` lại và ghi bảng mới; bảng §4.6 gắn với sha ở §3.1.
