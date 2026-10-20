# Áp dụng đề xuất [F]: chuyến bay theo điểm xuất phát (O1) và chuyến ảo gộp lượt xem gần đây (O4)

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành
- Phạm vi: backend, evaluation, docs

## Mục tiêu

Người dùng chốt [F] 09/10 (`docs/prd/update-archive/2026-10-09-recsys-diem-xuat-phat-va-phien-xem.md`). Áp theo AGENTS.md §8: PRD → engine → spec → test → gate / latency. Hoàn tất chuỗi O của `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` trên engine (gộp PR-A). FR-REC-02, FR-REC-04, NFR-PERF-01.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-REC-02 (nhiều lượt xem gần đây = một ý định), FR-REC-04 (điểm xuất phát chuyến bay)
- `src/backend/app/domain/recommendation/profile.py` — sửa: `W_ORIGIN = 0.15`, `H_SESSION_DAYS = 7`, `session_trip`, `ScoreContext`, `infer_origin`, `origin_mismatch`, `score_candidates(..., context)`, `build_profile` chọn chuyến ảo; `ENGINE_RULES_VERSION = "2026-10-09-origin-session"`
- `src/backend/app/domain/recommendation/__init__.py` — sửa: xuất `ScoreContext`, `infer_origin`
- `src/backend/app/application/recommendation/use_cases.py` — sửa: `_LocalSpace.origin_city`; dựng `ScoreContext` trước khi chấm điểm (không thêm I/O)
- `src/backend/tests/unit/domain/test_recommendation_origin_session.py` — thêm: chuyến ảo, chuyến đã đặt vẫn đứng trước, `infer_origin`, phạt / loại route sai điểm xuất phát
- `src/backend/tests/unit/domain/test_recommendation_trip_open.py` — sửa: version mới; hai chuyến chỉ-xem mở → chuyến ảo
- `src/evaluation/recsys_bench/ceiling.py` — sửa: `TripView.confidence`, `session_view`, `EngineView.session` (gương chuyến ảo)
- `src/evaluation/recsys_bench/arms.py` — sửa: `trip_destination` theo chuyến ảo (canary `most_popular_in_destination`)
- `src/evaluation/recsys_bench/theme_study/{eval_formula,step2_scorers,oph_scorer}.py` — sửa: hàm điểm thử nghiệm nhận `context` của engine và áp luật loại route sai điểm xuất phát ở nhánh không chuyến mở (`engine_origin_mask`)
- `src/evaluation/recsys_bench/theme_study/registry.py` — sửa: ghi chú `B0` nay = chuỗi F_O cũ, token `orig` / `book` / `sess` áp lần hai
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.4 bổ sung chuyến ảo, §4.7 điểm xuất phát
- `src/evaluation/recsys_bench/frozen/baseline_v5-{llbo,temporal,nexttrip,coldstart}-prodcopy-asof20261008.json` — thêm
- `src/evaluation/reports/eval-2026-10-09-recsys-gate-v5-diem-xuat-phat-phien-xem.md` — thêm: parity, gate v4 → v5, latency
- `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` — sửa: §0.2 trạng thái
- `docs/prd/update/2026-10-09-recsys-diem-xuat-phat-va-phien-xem.md` → `docs/prd/update-archive/` — đổi tên (git mv), trạng thái "đã áp dụng"

## Quyết định

- Engine cài đúng phép tính của bản thí nghiệm `B0+orig:pen:0.15+sess`: parity nDiscordant4 = nDiscordant20 = 0 trên toàn bộ khách (llbo 4.023, temporal 773, nexttrip 1.835, coldstart 5.233, 1.152 khách giả lập).
- Chuyến ảo không nằm trong `Profile.trips` → `diagnostics.trips`, `eventsUsed` không đổi; contract OpenAPI không đổi.
- Không hằng nào thêm vào `popularity.py` (pop_h đã bỏ) nên mục "hash popularity.py trong engine_config" của plan không còn cần.

## Kiểm tra

- `PYTHONHASHSEED=0 PYTHONUTF8=1 pytest src/backend/tests src/evaluation/recsys_bench/tests`: 2072 passed, 39 skipped.
- `test_engines.py::test_ac_rec_02_…` lỗi ở một số seed băm (vd `PYTHONHASHSEED=13/14/20/24/51/53/59`) **cả trên code trước thay đổi** (`24cdd40`): `FakeEmbedder` băm bằng `hash()` nên `because[]` có thể rỗng (đúng ghi chú trong test). Có sẵn, không sửa ở đây.
- Gate v5: run exit 0 4/4; `regress` vs v4 exit 2 (không so được, theo thiết kế); `regress` vs v5 exit 0 4/4. recall@20 llbo 0,8069 → 0,8377, temporal 0,1565 → 0,1721, nexttrip 0,0747 → 0,0845, coldstart 0,8091 → 0,9717.
- Latency đầu-cuối 4 lượt xen kẽ: p95 SAU ≤ TRƯỚC, chênh theo strategy tối đa +4,5 ms → đạt G1; parity HTTP SAU 60/60.

## Còn lại / rủi ro

- Lợi gate tập trung ở khách mà món đích đã có trong lịch sử xem (caveat report §2).
- Track F14c + destCap2 (PR-B) vẫn theo lane B / G2.
- Lệch 1 khách (ngày UTC) giữa arm `content_profile` và engine ở nexttrip có sẵn từ v3.
