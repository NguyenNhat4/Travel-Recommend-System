# /search khai thời gian từng bước ở diagnostics.stageMs (contract 1.9.0)

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-stage-timing (tách từ `origin/release-mvp-v2 @ 5cede8e`)
- Trạng thái: hoàn thành
- Phạm vi: contract, backend, frontend, docs

## Mục tiêu

Lịch 10 ngày, Day 1 phần C (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`): thêm timing per-stage cho `/search` (normalize → embed → dense → BM25 → RRF → hydrate) làm đầu vào cho Day 2 (latency breakdown p50/p95 trên cloud). `/search` hiện chỉ có `latencyMs` tổng, trong khi Cohere chiếm phần lớn 0,4–0,6 s/truy vấn (docs/plan/2026-09-28-summary-search-recsys-benchmark.md §1.5). Phục vụ NFR-PERF-01 (p95 ≤ 250 ms) và NFR-PERF-03 (đo được phần Cohere để quyết cache vector truy vấn).

## File thay đổi

- `src/shared/contracts/schemas/search.yaml` — sửa: `EngineDiagnostics` thêm `stageMs` tuỳ chọn (object, `additionalProperties: false`, sáu khoá integer ≥ 0: `normalize`, `embed`, `dense`, `lexical`, `fuse`, `hydrate`); không đổi `required`.
- `src/shared/contracts/openapi.yaml` — sửa: `info.version` 1.8.0 → 1.9.0.
- `src/backend/app/main.py` — sửa: `version="1.9.0"` khớp contract.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại bằng `npm run generate:api-types`, chỉ thêm khối `stageMs`.
- `src/backend/app/application/search/use_cases.py` — sửa: thêm `StageTimer` (perf_counter, cộng dồn số thực, xuất ms nguyên làm tròn xuống); `SearchProducts.__call__` và `_hybrid` ghi `lap()` sau từng bước; gắn `diagnostics.stageMs`; một dòng `logger.debug("search.stage_ms …")`.
- `src/backend/tests/unit/application/test_search_stage_timing.py` — thêm: 12 test (khoá theo chế độ ANN / hybrid / tắt chuẩn hoá / BM25 lỗi; thời gian rơi đúng bước bằng embedder chậm có chủ đích; response khớp contract; contract từ chối khoá lạ; payload tool của agent không mang diagnostics; `StageTimer` cộng dồn; làm tròn xuống với đồng hồ giả; tổng `stageMs` ≤ `latencyMs` qua route thật).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 thêm đoạn mô tả `stageMs`; tiêu chí 11 thêm ghi chú ngưỡng PRD 250 ms và báo p95 theo từng bước.

## Quyết định

- **Contract trước code** (`AGENTS.md` §3). Trường tuỳ chọn, chỉ thêm → tương thích ngược → tăng minor 1.9.0 (tiền lệ `history/2026-09-28-recsys-strategy-enum-va-cdp-fallback.md`). Không lệch PRD: đây là diagnostics bổ sung, không đổi hành vi.
- **Tách nhánh từ `origin/release-mvp-v2`**, không từ `bench/embed-search` như plan ban đầu: `release-mvp-v2` là nhánh deploy (CI/CD chạy trên nó), đã chứa trọn `bench/embed-search` (PR #38), cùng contract 1.8.0, nhưng `api.gen.ts` có thêm 10 dòng của agent. Tách từ bench rồi bump 1.9.0 + sinh lại `api.gen.ts` sẽ xung đột khi hợp vào v2; và Day 2 cần `stageMs` chạy trên VM để đo cloud. Không tách từ `release-mvp-v1` vì nhánh đó còn contract 1.7.0.
- Tên khoá `lexical` (không phải `bm25`) để cùng họ với `lexicalK`, `lexicalCandidates`; không trùng các khoá chuẩn hoá (`normalizedQuery`, `appliedAliases`, `corrections`, `party`).
- Bước không chạy thì không có khoá (`normalize` vắng khi `SEARCH_NORMALIZE=false`; `lexical` vắng ở ANN). `lexical` vẫn có khi nhánh BM25 lỗi, để thấy thời gian của lần gọi hỏng. `dense` gồm dựng bộ lọc cấu trúc (mask/allowed ids). `fuse` ở ANN là `candidate_filter_score`.
- Đo trong `application` bằng `time.perf_counter` (stdlib), không đụng route; `latencyMs` tổng vẫn do route gắn, nên tổng `stageMs` ≤ `latencyMs`. `search_tool_payload` đã bỏ `diagnostics` nên agent không nhận trường mới.
- Thêm một dòng log DEBUG để Day 2 vẫn lấy được số từ log VM nếu cần.
- **Làm tròn xuống, không làm tròn từng bước.** Review độc lập (workflow 3 reviewer + kiểm chứng đối kháng) chỉ ra bản đầu làm tròn từng bước nên tổng `stageMs` có thể vượt `latencyMs` 1–3 ms, trái với câu "tổng các bước <= latencyMs" trong contract. Nay cộng dồn số thực và `int()` khi xuất: tổng các phần làm tròn xuống ≤ phần nguyên của tổng ≤ `latencyMs` (route làm tròn trên tổng thời gian dài hơn). Mô tả contract ghi "làm tròn xuống".

## Kiểm tra

- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py`: PASS (88 schemas, 64 fixtures; CDP clone 12 schemas, 7 fixtures, 11 negative checks).
- `npm --prefix src/frontend run generate:api-types`: OK (openapi-typescript 7.13.0); `git diff` của `api.gen.ts` chỉ là khối `stageMs`.
- `npm --prefix src/frontend run typecheck`: exit 0.
- `pytest -q src/backend/tests` bằng `.venv` (Python 3.13, Windows, `PYTHONUTF8=1`, worktree không có `.env`): **689 passed, 19 skipped**, 0 failed; 12 trong đó là test mới. Lần này `.venv` import và chạy được `psycopg` (khác ghi nhận ở `2026-09-29-fix-backend-ci-sau-merge-agent.md`).
- `pytest -q` 5 file search/response (stage timing, hybrid, normalization, engines, response helpers): 40 passed.
- `coverage` trên `src/backend/tests/unit/application`: `application/search/use_cases.py` 98 % (133 stmts, 3 miss), `application/search/*` 98 %.
- CI-parity trong Docker `python:3.11` (cây làm việc gồm file đã track và file mới chưa ignore, không `.env`, `pip install -r src/backend/requirements.txt`): `validate_contract.py` PASS; `compileall` ok; `pyflakes` trên hai file Python đổi/thêm: sạch; `pytest -q src/backend/tests`: **687 passed, 19 skipped**.

## Còn lại / rủi ro

- Frontend CI sẽ chạy khi push vì chạm `src/shared/contracts/**`. Thay đổi contract cần reviewer Web + Backend (`architecture.md` §6.4); cần báo nhóm Web trường mới (tuỳ chọn, không phá UI).
- Day 2: đo p50/p95 từng bước trên cloud cần nhánh này đã deploy lên VM qua `release-mvp-v2`.
- `routes/search.py` vẫn hard-code `cutoff: 0.62` cho trang rỗng trong khi `settings.search_cutoff` mặc định 0.52 — ngoài phạm vi, ghi ở mục Issue Day 1 của `docs/spec/bench/recsys-offline-eval.md` (nhánh `bench/recsys-harness`).
