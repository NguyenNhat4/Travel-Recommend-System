# Áp dụng đề xuất [D]: chuyến đã đặt được ưu tiên hơn lượt xem lẻ đến sau (sửa I-3)

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành
- Phạm vi: backend, evaluation, docs

## Mục tiêu

Áp đề xuất `docs/prd/update-archive/2026-10-09-recsys-uu-tien-chuyen-da-dat.md` (người dùng chốt 09/10) theo AGENTS.md §8: PRD trước, rồi engine, spec, test. FR-REC-02, AC-REC-02. Đây là bậc O3 của `docs/plan/2026-10-09-recsys-cong-thuc-oph.md`, gộp vào PR-A theo quyết định 09/10.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-REC-02 thêm câu "chuyến đã đặt chưa diễn ra xong luôn được ưu tiên hơn lượt xem / giỏ lẻ đến sau"
- `src/backend/app/domain/recommendation/profile.py` — sửa: `active_trip` = chuyến mở có purchase trẻ nhất, không có thì chuyến mở trẻ nhất; `ENGINE_RULES_VERSION = "2026-10-09-booked-first"`
- `src/backend/tests/unit/domain/test_recommendation_trip_open.py` — sửa: version mới; thêm `test_booked_trip_stays_active_over_later_stray_view`
- `src/evaluation/recsys_bench/ceiling.py`, `splits.py` (`excluded_taxonomies`), `arms.py` (`trip_destination`) — sửa: gương harness theo luật mới (không đổi sha split đóng băng: `canonical` không chứa phần này)
- `src/evaluation/recsys_bench/tests/test_engine_no_leak.py`, `test_ceiling.py`, `test_analysis.py`, `test_metrics_open_trip_gini.py`, `test_splits.py`, `test_oph.py` — sửa: kỳ vọng cho khách fixture `u1` (chuyến đã đặt T1 + view lẻ A1 đến sau) theo luật mới
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.4 bổ sung 2026-10-09
- `docs/prd/update/2026-10-09-recsys-uu-tien-chuyen-da-dat.md` → `docs/prd/update-archive/` — đổi tên (git mv), trạng thái "đã áp dụng"
- `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` — sửa: đường dẫn đề xuất [D]

## Quyết định

- Không thêm hằng mới; chỉ đổi luật chọn `active_trip` nên tăng `ENGINE_RULES_VERSION` (configHash bench đổi).
- Contract OpenAPI không đổi (`strategy`, `diagnostics` giữ nghĩa).

## Kiểm tra

- `PYTHONUTF8=1 pytest src/evaluation/recsys_bench/tests src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract`: 2068 passed, 5 skipped. (Không có `PYTHONUTF8=1` thì `test_recommendation_cdp_fallback.py` lỗi đọc YAML bằng cp1252 trên Windows — lỗi môi trường có sẵn.)

## Còn lại / rủi ro

- `baseline_v3` của lane A không còn so được (configHash đổi) — ghi baseline mới sau khi áp xong [E] và (nếu chốt) [F].
