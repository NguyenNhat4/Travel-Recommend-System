# Đưa diagnostics.stageMs của /search lên release-mvp-v2 (contract 1.11.0)

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-stage-timing-v2 (tách từ `origin/release-mvp-v2 @ 1b923d8`)
- Trạng thái: hoàn thành
- Phạm vi: contract, backend, frontend, docs

## Mục tiêu

Cherry-pick `f03ffea` (`history/2026-09-29-search-stage-timing.md`, nhánh `feat/search-stage-timing` tách từ v2 @ `5cede8e`) lên đầu `release-mvp-v2` hiện tại để CI deploy lên VM và Day 2 phần C đo được breakdown p50/p95 từng bước của `/search` trên Cloud (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`, NFR-PERF-01/03). Nội dung `stageMs` không đổi; chỉ đổi số phiên bản contract.

## File thay đổi

- `src/shared/contracts/openapi.yaml` — sửa: `info.version` 1.10.0 → **1.11.0** (xung đột cherry-pick: `f03ffea` ghi 1.9.0, v2 đã lên 1.10.0 khi gộp `feat/booking`, xem `history/2026-09-29-merge-release-mvp-v2-vao-feat-booking.md`).
- `src/backend/app/main.py` — sửa: `FastAPI(version="1.11.0")` khớp contract (xung đột cùng lý do).
- `src/shared/contracts/schemas/search.yaml` — sửa: comment của `stageMs` ghi contract 1.11.0.
- `src/backend/app/application/search/use_cases.py` — sửa: docstring `StageTimer` ghi contract 1.11.0; phần code giữ nguyên `f03ffea`.
- `src/backend/tests/unit/application/test_search_stage_timing.py` — sửa: docstring ghi 1.11.0; 12 test giữ nguyên.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 đoạn `stageMs` ghi contract 1.11.0 (đoạn và tiêu chí 11 lấy nguyên từ `f03ffea`).
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `openapi-typescript@7.13.0` trên contract 1.11.0: kết quả trùng khớp bản cherry-pick (chỉ thêm khối `stageMs`, không mang số phiên bản).
- `history/2026-09-29-search-stage-timing.md` — thêm nguyên bản từ `f03ffea`, không sửa (AGENTS.md §5); số 1.9.0 trong đó là của nhánh gốc, entry này thay thế.

## Quyết định

- **1.11.0, không phải 1.10.0** như plan Day 3 ghi: v2 đã dùng 1.10.0 cho checkout nhiều bước; `stageMs` chỉ thêm trường tuỳ chọn nên tăng minor (`docs/prd/api-contract.md` §3.2). PR cache embedding kế tiếp sẽ là 1.12.0.
- Không sửa entry `2026-09-29-search-stage-timing.md` dù nó ghi 1.9.0: quy tắc không sửa entry cũ; entry này ghi đè quyết định số phiên bản.
- `api.gen.ts` không chứa `info.version` nên bản sinh lại trùng bản cherry-pick; vẫn chạy lại để chắc chắn (không có `node_modules` trong worktree, dùng `npx openapi-typescript@7.13.0` đúng phiên bản trong `package.json`).

## Kiểm tra

- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py` → PASS (97 schemas, 50 grounded products, 70 fixtures; CDP clone 12 schemas).
- `npx --yes openapi-typescript@7.13.0 ../shared/contracts/openapi.yaml -o src/types/api.gen.ts` → `git diff` rỗng.
- `pytest src/backend/tests -q` trong worktree → **902 passed, 21 skipped** (100 s; integration Postgres/Redis skip vì không đặt `RUN_*_INTEGRATION=1`; 12 test `test_search_stage_timing.py` nằm trong số pass).

## Còn lại / rủi ro

- Mở PR `feat/search-stage-timing-v2` → `release-mvp-v2` (reviewer Web + Backend theo spec §7.4); push khi người dùng bảo. Sau merge CI deploy `:latest` lên VM; kiểm `GET https://v-ota.duckdns.org/api/v1/search?q=VinWonders&limit=5` có `diagnostics.stageMs`.
- Không push `release-mvp-v1` trong cửa sổ đo (cùng deploy `:latest`, contract 1.7.0 sẽ ghi đè `stageMs`).
- Nhánh `feat/search-stage-timing` cũ (1.9.0) không dùng nữa; `bench/embed-search` nhận `stageMs` khi gộp v2 về sau PR cache.
