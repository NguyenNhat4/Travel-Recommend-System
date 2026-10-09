# Sửa CI: dọn phần Cohere còn sót ở crawler (e5-only) và race trong test rời trang thanh toán

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: data | frontend

## Mục tiêu

PR `fix/search-production` vào `release-mvp-v2` fail hai job CI:

1. **Crawler DB run lock** (`ha-checks.yml`): `test_fresh_catalog_job.py::IndexSettingsTests::test_local_provider_needs_no_cohere_key` — `'Settings' object has no attribute 'embed_provider'`.
2. **Frontend quality checks**: `tests/unit/checkoutView.test.tsx:810` — `beforeunload` không bị chặn (`defaultPrevented` false).

Trước khi sửa đã merge `origin/release-mvp-v2` mới nhất (`1515020`, PR #129) vào nhánh (commit `89a0fae`, không conflict) vì CI chạy trên kết quả merge với release và test ở dòng 810 thuộc release.

## Nguyên nhân

- **Crawler:** commit `1eb7624` của nhánh thêm `EMBED_PROVIDER` (local | cohere đường lui) vào backend và data_collection; commit `17dfbb5` gỡ khỏi backend theo đề xuất đã chốt `docs/prd/update-archive/2026-10-06-bo-duong-lui-cohere.md` nhưng phần data_collection còn sót. Ngoài test CI, phần sót còn làm hỏng: `monitor.embed_query` import `cohere_embedder` (đã xoá) và đọc `settings.weaviate_collection` (không có) → ô "Thử truy vấn" của monitor crash; UI monitor ghi "Gọi Cohere" và mất handler `cleanupForm` của release; `Dockerfile.daily` gọi `LocalE5Embedder(...).warmup()` không tồn tại → build image daily hỏng (cùng lỗi đã sửa ở `Dockerfile.backend` trong commit `490c825`). Release đã ở trạng thái e5-only cho các file này.
- **Checkout:** guard rời trang chỉ bật khi `drafts.length > 0`; `drafts` dựng trong effect chờ `authReady`, muộn hơn lúc tiêu đề "Hành khách" hiện. Test phát `beforeunload` ngay sau `open()` (chỉ chờ tiêu đề) nên trên CI chậm guard chưa bật. Lỗi của test, không phải sản phẩm.

## File thay đổi

- `src/data_collection/monitor.py`, `src/data_collection/monitor_ui/index.html` — sửa: lấy lại bản release (thử truy vấn bằng e5 qua `build_embedder`, `vector_collection`, handler `cleanupForm`).
- `src/data_collection/fresh_settings.py`, `src/data_collection/index_backlog.py`, `src/data_collection/cron_daily.sh` — sửa: lấy lại bản release (bỏ chú thích / biến `EMBED_PROVIDER`).
- `src/data_collection/tests/test_live_monitor.py`, `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: lấy lại bản release (bỏ các test chuyển provider local ↔ cohere và `test_local_provider_needs_no_cohere_key`).
- `src/data_collection/daily.py` — sửa: bỏ `embed_provider()`; `index_missing()` chỉ cần `WEAVIATE_URL` (giữ sửa lỗi của nhánh: release bỏ qua bước index khi thiếu `COHERE_API_KEY` dù backend chỉ dùng e5); chú thích `TARGETS` theo e5.
- `src/data_collection/tests/test_daily.py` — sửa: `IndexGateTest` theo e5 (chỉ cần `WEAVIATE_URL`, khoá Cohere không ảnh hưởng, thiếu Weaviate thì bỏ qua index); `CrawlerImageEmbeddingTest` bỏ yêu cầu `.warmup()` / `requirements-embed` ở mọi image, thêm `test_build_checks_only_call_existing_embedder_methods` (đọc method của `LocalE5Embedder` bằng `ast`, mọi lời gọi `LocalE5Embedder(...).<method>(` trong ba Dockerfile phải tồn tại).
- `Dockerfile.daily` — sửa: bước kiểm lúc build dùng `embed_query('kiểm tra')` + assert 384 chiều thay `.warmup()`; bỏ chú thích đường lui Cohere.
- `src/frontend/tests/unit/checkoutView.test.tsx` — sửa: test `beforeunload` chờ (`waitFor`) guard bật trước khi kiểm; `vi.setConfig({ testTimeout: 15_000 })` riêng cho file này (chạy song song cả bộ, vài test vượt 5 s — kể cả trên release).

## Quyết định

- Không lệch PRD: FR-SRC-02 chỉ e5-small local; đề xuất bỏ đường lui Cohere đã chốt + áp dụng 06/10. Sửa ở đây là dọn phần chưa áp dụng.
- Giữ `Dockerfile.fresh-catalog` của release (torch `>=2.3`, không `requirements-embed`, không bước kiểm model): image này build được; đồng bộ phiên bản torch/transformers với backend để sau (xem Còn lại).
- Test frontend: sửa test, không đổi `useLeaveGuard` — người dùng thật không đóng tab trong cùng tích tắc trước khi đoàn khách dựng xong.

## Kiểm tra

- Job CI crawler (Linux `python:3.11-slim`, đúng gói của `ha-checks.yml`): `pytest tests/test_catalog_run_lock.py tests/test_fresh_catalog_job.py tests/test_pipeline_graph.py tests/test_alerts.py` → **75 passed, 1 skipped** (lock cần Postgres thật).
- Toàn bộ `src/data_collection/tests` cùng container: 581 passed, 27 skipped, 6 failed — 6 test runner Docker (`test_fresh_monitor` DockerRunnerTests, `test_runner_fresh_monitor`, `test_runner_prune_images`) lỗi `set: pipefail` do môi trường container; chạy trên bản release gốc (`git archive origin/release-mvp-v2`) cùng container cũng fail đúng 6 test này.
- Lệnh kiểm model mới của `Dockerfile.daily` chạy trong image backend e5 (`HF_HUB_OFFLINE=1`): OK, vector 384 chiều. Chưa build trọn image daily (cần Playwright/Chromium).
- Frontend, các bước CI trong container Linux `node:22` (`npm ci`, sinh lại `api.gen.ts`, lint, typecheck, test):
  - `api.gen.ts` sinh lại khớp file đã commit; lint 0 lỗi (2 cảnh báo có sẵn); typecheck exit 0.
  - `vitest run` cả bộ: trước khi nâng timeout, 3/4 lần có 1–2 test `checkoutView` quá hạn 5 s; bản release gốc (`git archive`) cùng
    container cũng fail 2/2 lần chạy cả bộ ở đúng các test này → chập chờn có sẵn, không do nhánh.
  - Sau khi sửa: 6 lần chạy cả bộ, 5 lần 786/786 pass, 1 lần fail 1 test `homeView` (instant search) chưa tái hiện lại; `checkoutView`
    không fail lần nào. Test `beforeunload` (dòng lỗi trên CI) pass mọi lần.

## Còn lại / rủi ro

- `Dockerfile.fresh-catalog` dùng torch `>=2.3` + transformers theo `requirements.txt` backend (`<5`), còn backend/daily ghim `torch==2.14.1`, `transformers==5.18.0` — có thể lệch số học nhỏ giữa vector job ghi và vector backend tra; nên đồng bộ.
- `src/data_collection/README.md` (bản release) còn mô tả Cohere / `COHERE_API_KEY` — cần cập nhật theo đề xuất bỏ Cohere.
- `fresh_settings.ENV_STATUS` (release) vẫn liệt kê `COHERE_API_KEY` trên monitor.
- Các test rời trang khác trong `checkoutView.test.tsx` (bấm logo ngay sau `open()`) có cùng kiểu race nhưng chưa fail trên CI.
- `homeView.test.tsx` (instant search) chập chờn 1/6 lần khi chạy cả bộ trong container; chưa xử lý.
