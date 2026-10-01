# Harness đánh giá offline RecSys trên DB seed (Day 1 B) và kiểm P1 (Day 1 C)

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/recsys-harness (tách từ `bench/embed-search @ f2a697a`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, backend, cdp, docs

## Mục tiêu

Lịch 10 ngày (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`), Day 1 phần B: đưa harness RecSys offline lên DB đã seed, in số event bị loại, chốt hai cách split, bọc engine production thành `recommend(cdp_user_id, as_of, k)` gọi trực tiếp và chạy baseline random. Kèm phần C: kiểm nhanh `/recommendations` cho persona P1 `VP0000001`, chỉ ghi issue. Phục vụ FR-REC-01..04, NFR-PERF-01, test-plan §2.5.

## File thay đổi

- `src/backend/app/application/ports/cdp_client.py` — sửa: `CdpHistoryReader.all_events(until=None)` (chỉ cho đánh giá offline).
- `src/backend/app/infrastructure/cdp/postgres_cdp_reader.py` — sửa: hiện thực `all_events` qua `_query` sẵn có (map lỗi, xoá DSN), `WHERE "timestamp" < until` khi có, `ORDER BY cdp_user_id, "timestamp", event_id`, không `statement_timeout`.
- `src/backend/tests/fakes/jsonl_cdp_reader.py` — sửa: `all_events` cho bản giả.
- `src/backend/tests/unit/infrastructure/test_postgres_cdp_reader.py` — sửa: thêm 3 test (đọc lô tất định không `set_config`; `until` cắt ở kho; lỗi kết nối thành `CdpUnavailableError`).
- `src/evaluation/recsys_bench/` — thêm: `__init__.py`, `__main__.py` (CLI typer: `doctor`, `load`, `split`, `run`, `user`), `paths.py`, `data_source.py`, `events.py`, `splits.py`, `engine.py`, `arms.py`, `metrics.py`, `bench.py`, `report.py`, `tests/` (conftest + 4 file, 29 test; test CLI tự skip khi thiếu `typer`). Dependency: `src/backend/requirements.txt` + `src/evaluation/requirements.txt` (đã có `typer`), không thêm gói mới.
- `docs/spec/bench/recsys-offline-eval.md` — thêm: cách chạy, số lọc, split, kết quả random + engine v0, kiểm P1, 7 issue, giới hạn.
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: §7 thêm một dòng về `all_events` (chỉ evaluation, `EVAL_DATABASE_URL`).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick 4 mục B và 2 mục C kèm số; mục backfill ghi chưa chạy; dòng Day 1 ở §8 Log; một dòng bảng §0.1 (checkpoint note mentor).

## Quyết định

- **Port có chọn lọc, không merge `origin/khoa/recsys-research@6b9b0af`.** Nhánh đó dựng trên nền 21/09: `ports/recsys.py` đã đổi thành `ports/unit_index.py` (git nhận là rename, merge có thể gắn nhầm `all_events`), `UnitIndex` không còn `E`, `PostgresVectorStore.load()` trả tuple, `SentenceTransformersEmbedder` đã comment. Lấy `_time_key`/`leave_one_purchase_out` (→ `splits.py`), `score_recommendations`/`_purchased_taxonomies` (→ `metrics.py`, giữ tên khoá), `all_events` (→ adapter) và ca test metric; ghi nguồn trong docstring. Bỏ 10 prototype, Streamlit và sơ đồ (lịch §7 cho phép chỉ giữ engine + 3 baseline).
- **Chống rò rỉ ở harness, hai tầng.** Engine production không loại event sau `now` mà kẹp `days_ago` về 0, và `main.build_recsys` dựng popularity theo giờ thật. Harness chặn event `>= as_of` ở `filter_events` và ở `OfflineEngine.recommend`, dựng popularity bằng chính `BuildPopularity` trên purchase `< as_of` với `now=as_of`; `OfflineCdpReader` ném lỗi nếu engine tự đọc CDP. Có test ghi lại hành vi kẹp của engine để ai đổi engine sẽ thấy.
- **Lọc chỉ áp purchase** (orphan, thiếu gid); giữ view/cart/search thiếu gid vì seed không bao giờ gắn gid cho chúng — đã kiểm 3.992/3.992 event duyệt không có gid.
- **Target quy về search unit cha** vì engine chỉ trả search unit. LLBO: khách ≥ 2 purchase hợp lệ, `as_of` = thời điểm purchase bị giấu, train `<` mốc đó. Temporal: T mặc định là phân vị 80 % thời điểm purchase, target là purchase đầu tiên ≥ T. Có `--min-trips 2` để chọn khách như baseline trong seed.
- **Kết nối:** catalog qua `DATABASE_URL`, event qua `EVAL_DATABASE_URL` (role chỉ đọc `cdp_eval_login`), không SQL thẳng vào `cdp.*` (`AGENTS.md` §6.1). Vector: `weaviate` (như production), `numpy` (kéo một lần, cache), `none`.
- **Số đặt ở `docs/spec/bench/recsys-offline-eval.md`**, số thô ở `bench_out/recsys/` (gitignore), không dùng `eval/report.md` hay `src/evaluation/reports/*.md` (`AGENTS.md` §7).
- Không tạo `src/evaluation/README.md` (`AGENTS.md` §1.2 yêu cầu hỏi người dùng); hướng dẫn chạy nằm trong report spec.
- Chạy engine v0 ngay (lịch để Day 3) vì cả tập chỉ mất khoảng 40 giây.
- **Review độc lập** (workflow 3 reviewer, mỗi lỗi một người kiểm chứng đối kháng): 6 lỗi được xác nhận, 2 bị bác. Đã sửa: `doctor` xoá mọi cache event của DB (trước chỉ làm mới bản không có `as_of`, trái với hướng dẫn trong report); lệnh `user` lấy `candidate_k` từ Settings như production; `excluded_taxonomies` áp `MAX_REPEAT_PER_TRIP` như `build_profile` (thêm test đối chiếu với engine thật; số trên DB seed không đổi: LLBO 0, temporal 18); note mentor và lịch ghi rõ `stageMs` còn nằm ở nhánh chờ PR. Lỗi làm tròn `stageMs` sửa ở nhánh C.

## Kiểm tra

- Dữ liệu: Postgres + Weaviate của compose local (volume có sẵn, không seed lại) — 7.145 event, 2.000 profile, 3.183 search unit; khớp `snapshots/2026-09-23/seed/seed_report.md` (seed 42, as_of 2026-09-24). DSN truyền bằng biến môi trường, không sửa `.env`.
- `python -m src.evaluation.recsys_bench doctor`: catalog, CDP, Weaviate đều OK; as_of suy ra 2026-09-24.
- `load`: orphan 63 (2,0 %), thiếu gid 94 (3,0 %), loại 152, giữ 6.993.
- `split --kind llbo`: 1.016 khách test; `--min-trips 2`: 269; `--kind temporal`: T 2026-07-10T09:13Z, 98 khách.
- `run --arm random --arm engine --split llbo --vectors weaviate` (run `2026-09-29-llbo-v0`): random 3 seed Recall@20 0,0066 ± 0,0023; engine Recall@10 = Recall@20 0,6191, NDCG@10 0,4718, coverage 0,207, availability 1,0, p95 58 ms. Temporal (run `2026-09-29-temporal-v0`): engine Recall@10 0,1327.
- `user --id VP0000001 --k 5`: `cross_vertical`, `excludedVerticals ["hotel"]`, `nextVertical flight`, 0 lỗi contract; dư field `sections`.
- `pytest -q src/evaluation/recsys_bench/tests`: 29 passed (không cần DB).
- `pytest -q src/backend/tests src/evaluation/recsys_bench/tests` trong worktree sạch tại `f2a697a` chép đúng các file đã đổi, không có `.env` (như CI), trước vòng review: 682 passed, 19 skipped.
- `src/evaluation/tests/test_golden.py`: 3 failed, 49 passed — đã fail y hệt trên `f2a697a` sạch, không liên quan thay đổi này.
- CI-parity trong Docker `python:3.11` (cây làm việc gồm file đã track và file mới chưa ignore, không `.env`): `validate_contract.py` PASS; `compileall` ok; `pyflakes` trên file mới/đổi: sạch. Trước vòng review (28 test harness): chỉ cài `src/backend/requirements.txt` → 681 passed, 20 skipped (test CLI tự skip khi thiếu `typer`). **Sau vòng review, cài thêm `src/evaluation/requirements.txt`: 683 passed, 19 skipped** (651 cũ + 3 test reader + 29 test harness).

## Còn lại / rủi ro

- Day 2 (B): `sanity.py` và hai baseline most-popular (cửa sổ thời gian) và most-popular-in-destination; kiểm thứ tự random ≪ most-popular < most-popular-in-destination trước khi đọc số engine.
- Issue I-1…I-7 ở `docs/spec/bench/recsys-offline-eval.md` §6, đáng chú ý: view không có gid sau purchase làm engine mất `cross_vertical` (I-3); engine trả tối đa 9 món khi `k = 20` (I-5).
- Chạy `pytest src/backend/tests` từ repo chính khi `.env` trỏ DB tunnel `15432` và Postgres/Weaviate local đang chạy: `test_assistant_contract.py::test_every_error_path_matches_the_contract` mất 58 giây đến hơn 120 giây vì app dựng recsys thật. Bộ test chưa kín với `.env`; chạy không có `.env` (worktree sạch hoặc Docker như CI) thì bình thường.
- Harness lấy `recommend_candidate_k` từ Settings nhưng dùng `popular_k = 50` mặc định của engine, giống production.
