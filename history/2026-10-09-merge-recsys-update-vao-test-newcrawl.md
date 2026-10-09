# Gộp công thức RecSys mới (`feat/recSys_update`) vào `test/newcrawl`

- Ngày: 2026-10-09
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `test/newcrawl`
- Trạng thái: hoàn thành
- Phạm vi: backend, data, evaluation

## Mục tiêu

Người dùng yêu cầu đưa công thức RecSys mới nhất của tqanh123 vào `test/newcrawl` mà không chờ PR #139 (`feat/recSys_update` →
`release-mvp-v2`, còn mở; CI của PR không chạy vì GitHub báo lỗi thanh toán / spending limit — job không được khởi động, không phải lỗi
code). Bản gộp: `origin/feat/recSys_update @ 1b7b3722` (gồm PR #130, #132, #138). FR-REC-01, FR-REC-02, FR-REC-03, FR-REC-04.

Công thức mang vào (đề xuất đã chốt trong `docs/prd/update-archive/`): loại sản phẩm đã mua + combo ↔ thành phần, ô khám phá khi có chuyến
mở, độ tin cậy chuyến trong `u_long`, purchase / cart không bị cap lặp, ưu tiên chuyến đã đặt, chuyến ảo gộp lượt xem, `W_ORIGIN` 0,15 cho
chuyến bay sai điểm xuất phát, persona = 4 trạng thái cold-start với dormant 365 ngày, và PR-B: khi không có chuyến mở dùng F14c
(cos(u_long) chuẩn hoá phân vị 0,8529–0,9387, trọng số 0,50 / 0,35 / 0,15) + tối đa 2 món mỗi điểm đến.
`ENGINE_RULES_VERSION = "2026-10-09-next-trip-f14c"`.

## File thay đổi

- `history/2026-10-09-merge-recsys-update-vao-test-newcrawl.md` — thêm: entry này.
- Các file còn lại do merge mang vào từ `feat/recSys_update`, không sửa tay; merge tự động, không xung đột (auto-merge
  `src/backend/app/core/config.py`, `src/backend/app/main.py`). Nhóm chính: `src/backend/app/{domain,application}/recommendation`,
  `src/backend/app/application/ports/unit_index.py`, `src/backend/app/infrastructure/vectors/postgres_store.py`, `core/config.py`
  (`RECOMMEND_EXPLORE_FILL`, `RECOMMEND_NEXT_TRIP_SCORING`, `RECOMMEND_MAX_PER_DESTINATION`), `src/data_collection/seed` (P3 dormant, profile
  `g6-pref-v1`), `src/evaluation/recsys_bench`, `docs/prd` (PRD đã cập nhật theo đề xuất đã chốt), `AGENTS.md` §6.4, 31 entry `history/`.
  Không đổi `db/`, contract (`src/shared/contracts`) hay frontend.

## Quyết định

- Gộp thẳng nhánh RecSys thay vì chờ #139: khi #139 vào `release-mvp-v2`, lần gộp `release-mvp-v2` → `test/newcrawl` sau đó không phải
  làm lại các commit này.
- Không sửa test flaky của nhánh RecSys (mục Còn lại) — thuộc phần của tqanh123.

## Kiểm tra

- `pytest src/backend/tests/unit src/backend/tests/architecture` (vsf2): lượt 1 **2509 passed, 1 failed, 2 skipped**; chạy lại 2 lượt:
  **2510 passed, 2 skipped** cả hai. Test fail là test flaky (mục Còn lại).
- `pytest src/data_collection/tests` (vsf2, `PYTHONPATH=src`): **640 passed, 27 skipped**.
- `pytest src/evaluation/recsys_bench/tests`: **190 passed, 3 skipped**.
- `python3 src/shared/contracts/tests/validate_contract.py`: **PASS** (120 schemas, 94 fixtures; CDP clone 12 schemas).

## Còn lại / rủi ro

- Test flaky `src/backend/tests/unit/application/test_engines.py::test_ac_rec_02_booking_prioritises_flights_and_activities_at_the_destination`
  (thêm ở `a4f57e1d`, nhánh RecSys): `FakeEmbedder` băm text bằng `hash()` nên kết quả đổi theo `PYTHONHASHSEED`; fail với seed 13, 14, 20,
  24 trên 40 seed thử (`assert any(x["because"] for x in recs)`), y hệt trên `origin/feat/recSys_update` chưa gộp. Cần báo tqanh123.
- PR #139 chưa chạy CI (lỗi thanh toán GitHub Actions); `release-mvp-v2` đã chuyển sang self-hosted runner (#137) — chạy lại CI của #139.
- Chưa push. Seed thay đổi persona P3 (chuyến cuối 400 ngày): DB demo cần seed lại mới thấy P3 ở trạng thái dormant theo ngưỡng 365 ngày.
