# Áp dụng đề xuất M6: FR-REC-02 — trip đang mở theo `usingDate`, N = 14 cho trip chỉ view (PRD → spec → engine → harness)

- Ngày: 2026-10-02
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/m6-trip-ended (tách từ `bench/embed-search @ 9352569`; gộp lại; phần backend cherry-pick lên nhánh từ `release-mvp-v2`)
- Trạng thái: hoàn thành
- Phạm vi: PRD, spec, backend (domain + application recommendation), evaluation (recsys_bench), docs plan, docs/prd/update-archive

## Mục tiêu

Người dùng chốt đề xuất `2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` ("đồng ý sửa PRD theo phương án này",
02/10). Theo AGENTS.md §8: sửa `docs/prd/` trước, rồi spec và code, rồi chuyển đề xuất sang `update-archive/`. Mục tiêu đo:
temporal ceiling 0,784 → gần 1, `cross_vertical` temporal > 0, LLBO không giảm. FR-REC-02, FR-REC-01, M6/M7.

## File thay đổi

- `docs/prd/requirements.md` — sửa: §1.3 FR-REC-02 (điều kiện "chuyến chưa diễn ra xong", vế "sau khi chuyến xong", N là tham số engine).
- `docs/prd/update/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` → `docs/prd/update-archive/` (`git mv`), trạng thái
  `đã áp dụng`, chốt bởi tqanh123 02/10 — rename đã lọt vào commit gold `b4d7968` của phiên gán nhãn (cùng cây làm việc); commit này chỉ thêm
  ghi chú kết quả áp dụng vào cuối file.
- `src/evaluation/reports/eval-2026-10-02-recsys-bench-v5.md` — thêm: report chạy bench theo rule mới AGENTS.md §7 (bảng v3/v4/v5 nguyên văn,
  configHash, caveat, lệnh tái sinh).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.4 bổ sung 02/10 định nghĩa "trip đang mở" (= chưa kết thúc theo
  `tripFactor` §4.3: `max(usingDate) ≥ hôm nay`; trip không `usingDate` mở ≤ N = 14 ngày); §4.5 exclusion chỉ cho trip mở.
- `src/backend/app/domain/recommendation/profile.py` — sửa: `ResolvedEvent.using_date`, `Trip.ends_on` / `ended`, `trip_is_open`,
  `build_profile(…, today=)`, `ACTIVE_TRIP_MAX_AGE_DAYS` 60 → **14** (chỉ còn áp cho trip không `usingDate`), `ENGINE_RULES_VERSION`.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: parse `usingDate` (`_using_date`), `build_profile(…, today=now.date())`.
- `src/backend/tests/unit/domain/test_recommendation_trip_open.py` — thêm (luật `trip_is_open`, `build_profile` đóng / mở trip theo ngày).
- `src/backend/tests/unit/application/test_recommendation_strategy_contract.py` — sửa: `_events` nhận `usingDate`; 2 ca mới
  (chuyến đã đi xong 3 ngày → `long_term`; mua 120 ngày trước nhưng còn 10 ngày nữa đi → `cross_vertical`).
- `src/evaluation/recsys_bench/ceiling.py`, `splits.py`, `arms.py` — sửa: `ends_on` + `trip_is_open` (mô phỏng cùng luật engine).
- `src/evaluation/recsys_bench/tests/conftest.py` — sửa: `ev()` gắn `usingDate` = ngày mua + 45 cho purchase (như seed);
  `tests/test_ceiling.py` — thêm test trip đóng / mở theo `usingDate` trùng diagnostics engine, sửa rows có `usingDate`.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §4.11 findings 4–5, thêm §4.14, §7. `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — log Day 5.

## Kết quả

- v4 (chỉ `usingDate`, N = 60): temporal **không đổi** (0,196 / 0,144), ceiling 0,784 → 0,794. Mổ xẻ 21 target bị chặn: 11 từ trip
  chỉ view 36–58 ngày tuổi (không `usingDate`) vẫn mở → khoá điểm đến; 10 từ chuyến thật sự chưa đi tại T (`usingDate` ≥ T) — engine
  đúng ở T, split temporal hỏi khác câu.
- v5 (N = 14): temporal R@20 **0,216** (+0,020), NDCG@10 **0,154** (+0,010), prod NDCG@5 0,113 → 0,119; LLBO **không đổi**
  (0,851 / 0,524; prod 0,591 / 0,460). Chi tiết §4.14.

## Quyết định

- "Đã diễn ra xong" = `max(usingDate)` của trip < hôm nay (đúng định nghĩa `tripFactor` đã có ở spec §4.3); hôm nay = ngày của
  `now` (UTC; `usingDate` là ngày địa phương → lệch tối đa 1 ngày ở biên, ghi trong code).
- N = 14 chọn trên temporal đóng băng (B10), LLBO không giảm → đổi hằng production; `ENGINE_RULES_VERSION` để bench tách bộ số.
- Không đổi contract (`strategy`, `excludedVerticals`, `destination` giữ nghĩa); `tripFactor` 0,2 của spec §4.3 vẫn chưa hiện thực
  (ngoài phạm vi đề xuất).
- Harness fixture gắn `usingDate` cho purchase để test mô phỏng đúng seed (seed luôn có ngày sử dụng).

## Kiểm tra

- Backend: `tests/unit/domain tests/unit/application tests/unit/api` 339 passed; bộ đầy đủ → **661 passed, 19 skipped** (17 phút, máy đang chạy song song).
- Harness: `pytest src/evaluation/recsys_bench/tests` → 62 passed.
- v5: `run … --run-id 2026-10-02-{temporal,llbo}-v5` + `analyze` — bảng §4.14.
- Review đối kháng (workflow 3 lens) → 3 lens / 9 agent: xác nhận 2 — (1) đề xuất chưa `git mv` sang update-archive dù PRD đã trỏ tới (làm lúc commit), (2) `arms.trip_destination` tính `ends_on` / tuổi trên event chưa áp cap `MAX_REPEAT_PER_TRIP` như `build_profile` (đã sửa); bác bỏ 3 (history "thiếu" — đã có; nội dung đề xuất "lệch" — là kế hoạch trước khi làm). Ghi chú thêm: today = ngày UTC vs `usingDate` ngày VN lệch ≤ 7 h (chấp nhận, ghi trong code); `Trip.ended` chưa được production dùng (tripFactor 0,2 vẫn chưa hiện thực).

## Còn lại / rủi ro

- Cherry-pick 2 file backend + 2 test lên `feat/recsys-trip-ended` (từ `origin/release-mvp-v2`) để mở PR; spec/PRD cũng phải vào PR đó.
- Split "next trip" cho harness (as_of = ngay trước purchase kế, trip trước đã kết thúc) — chưa làm.
- `tripFactor` 0,2 (spec §4.3) vẫn chưa có trong engine — lệch spec/code còn tồn tại, ghi §7.
