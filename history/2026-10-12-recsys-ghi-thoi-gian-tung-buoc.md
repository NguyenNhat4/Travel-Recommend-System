# Gợi ý: ghi thời gian từng bước của engine vào log `recsys.recommend`

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành
- Phạm vi: backend, docs
- Liên quan: `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (giai đoạn 2, bước 1)

## Mục tiêu

`/recommendations` chậm 3–10 s trên cloud, nhưng chưa biết bước nào tốn thời gian: chưa có số đo cloud nào sau PR-A/PR-B, và log chỉ có `duration_ms` tổng. Bước này ghi thời gian từng bước của engine để đo trước và sau khi tối ưu (song song, nạp sẵn vector, cache). Không đổi output. Phục vụ NFR-PERF-01.

## File thay đổi

- `src/backend/app/application/recommendation/use_cases.py` — sửa:
  - Tách `RecommendForUser.__call__` thành hai phần: phần đọc CDP và điều phối, và `_rank(raw, k, now, destination, base, stages)` (thân cũ, giữ nguyên logic).
  - Đặt mốc `StageTimer`: `cdp`, `history`, `candidates`, `rank`, `explore`, `build`, `coldStart`.
  - Helper `_with_stages` gắn `diagnostics.stageMs` và `eventsRead`.
- `src/backend/app/application/recommendation/responses.py` — sửa: `ENGINE_ONLY_DIAGNOSTICS = ("stageMs", "cacheOutcome", "eventsRead")` bị bỏ khỏi payload trả về và được ghi vào log `recsys.recommend` (`stage_ms`, `cache`, `events_read`).
- `src/backend/app/core/logging_config.py` — sửa: allowlist `recsys.recommend` thêm `cache`, `stage_ms`, `events_read`.
- `docs/spec/logging-schema.md` — sửa: dòng Recommendation liệt kê trường mới và tên các bước.
- `src/backend/tests/unit/application/test_recommendation_cdp_fallback.py` — sửa: so sánh đường lui CDP với khách sau khi bỏ các khoá chỉ dành cho engine.
- `src/backend/tests/unit/application/test_response_helpers.py` — sửa, thêm 2 test:
  - khoá chỉ dành cho engine không có trong payload mà có trong log;
  - engine có `stageMs` ở cả nhánh cá nhân hoá lẫn cold-start, và có `eventsRead`.
- `history/2026-10-12-recsys-ghi-thoi-gian-tung-buoc.md` — thêm: entry này.

## Quyết định

- **Không đổi contract:** thời gian từng bước chỉ ghi log, không trả ra API, theo tiền lệ `SEARCH_ENGINE_ONLY_FIELDS`. `Traced.summarize` (telemetry) đọc `diagnostics.stageMs` trước khi bị bỏ, nên `/internal/calls` vẫn thấy.
- **`_rank` gọi qua tên toàn cục của module:** `build_profile`, `score_candidates`, `mmr_select`, `explore_fill`, `_LocalSpace` vẫn được gọi theo tên của module, vì harness bench thay chúng theo tên.
- **Không thêm hằng chữ hoa vào `profile.py`**, vì bench băm các hằng đó vào `configHash`.
- **Mốc `explore` luôn có**, kể cả khi không lấp ô (thời gian khoảng 0), để dễ gộp trên log.

## Kiểm tra

- `pytest -q -p no:cacheprovider src/backend/tests/unit src/backend/tests/contract src/evaluation/recsys_bench/tests`: 3036 passed, 8 skipped.
- Parity HTTP (backend + prodcopy) chưa chạy được: container prodcopy không còn trên máy ngày 2026-10-12 (xem `2026-10-12-cold-start-toi-da-2-moi-taxonomy.md`). Parity trong tiến trình (`test_parity.py`) pass.

## Còn lại / rủi ro

- Số đo thật: sau khi deploy, đọc `stage_ms` của `recsys.recommend` trên Cloud Logging. Log backend của VM HA chỉ lên Cloud Logging sau khi PR monitor được apply.
