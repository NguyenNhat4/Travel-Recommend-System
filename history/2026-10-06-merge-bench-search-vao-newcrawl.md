# Merge bench_search_recomSys (search query plan 1.16, RecSys bench) vào test/newcrawl

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl (merge làm trên nhánh tạm `merge/newcrawl-search` để không đụng worktree đang chạy cào)
- Trạng thái: hoàn thành
- Phạm vi: backend, contract, frontend, data, evaluation, docs

## Mục tiêu

Người dùng muốn `test/newcrawl` (data 02–06/10 + e5-small, đã gồm `release-mvp-v2`) có luôn các cập nhật search/RecSys mới nhất của `origin/bench_search_recomSys` (gồm PR #109, #110 từ `fix/search-gold-v4`), để chỉ cần một PR vào `release-mvp-v2`.

Nhánh bench mang về 25 commit (không tính merge): query plan F1–F6 sau cờ (contract 1.15.0) và 1.16.0 (fuzzy, party, tone, trọng số RRF, search log); gold_v3 → gold_v5, bench search ablation 45 arm, bench RecSys (registry thuật toán, baseline_v1, regress, split next-trip/cold-start, snapshot CDP append-v1); báo cáo eval; các đề xuất `docs/prd/update/` đang chờ (replica đọc, trọng số RecSys, hybrid min_coverage/RRF, LLM fallback query plan).

## Xử lý conflict (10 file)

- `src/data_collection/fresh_catalog_db.py`, `pipeline_graph.py`, `tests/test_pipeline_graph.py` — giữ bản `test/newcrawl`: phía bench chỉ có commit 02/10 gốc (`bb41479`, `d7ea30a`) mà `test/newcrawl` đã gom và sửa tiếp (`2a62d28`).
- `docs/spec/bench/recsys-offline-eval.md` — lấy bản bench (chủ của tài liệu, mới hơn).
- `Makefile` — giữ target tunnel của `release-mvp-v2` + thêm `.PHONY` recsys của bench.
- `src/backend/app/main.py`, `api/v1/routes/search.py`, `domain/search/__init__.py` — giữ cả hai: gợi ý tìm kiếm `SuggestProducts` (FR-SRC-05, từ `release-mvp-v2`) và query plan/search log (bench).
- `src/backend/app/application/search/use_cases.py` — giữ `scored()` (rating/reviewCount của `release-mvp-v2`) và `matchedChildren` (bench): `scored()` nhận thêm `**extra`.
- `src/shared/contracts/openapi.yaml` — hai nhánh cùng dùng số 1.14.0 cho hai thay đổi khác nhau (`release-mvp-v2`: rating/gợi ý/đơn nháp; bench: 1.14–1.16 query plan) → bản gộp lên **1.17.0** (không dùng lại số khi merge); `main.py` `version="1.17.0"`, `tests/contract/test_search_contract.py` theo.

## File thay đổi thêm ngoài merge

- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `openapi-typescript` 7.13.0 (CI frontend sinh lại và `git diff --exit-code`); bench chưa sinh lại cho 1.15–1.16.
- `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md` — xoá: đề xuất đã áp dụng, bản `đã áp dụng` nằm ở `docs/prd/update-archive/` (commit `5df2170`).
- `.env.example` — sửa một dòng còn nhắc `EMBED_PROVIDER` (đã bỏ).

## Kiểm tra

- Backend `pytest src/backend --ignore=tests/integration` (vsf2): **1.627 passed, 2 skipped**.
- `pytest src/data_collection/tests`: 487 passed, 21 skipped.
- `pytest src/evaluation/search_bench/tests`: 575 passed, 11 skipped, 1 failed (`test_gold_cli.py::test_share_dry_run_writes_launcher_outside_git_and_codes`) — cũng fail trên `origin/bench_search_recomSys` gốc, lỗi có sẵn.
- `validate_contract.py`: PASS. Frontend `tsc --noEmit` (container node:20, node_modules của repo chính): không lỗi. Chưa chạy test frontend (vitest).

## Còn lại / rủi ro

- Cờ F1–F6 vẫn mặc định tắt; bật trên production cần quyết định của người dùng (F4 cần Web đồng ý).
- Các đề xuất search/RecSys trong `docs/prd/update/` vẫn chờ chốt.
- Ngưỡng trong code: `SEARCH_CUTOFF` 0,84 (e5-small); các tham số hybrid giữ mặc định cũ (RRF 60, min_coverage 0,6) chờ đề xuất hybrid.
