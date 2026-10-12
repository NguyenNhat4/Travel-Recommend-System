# Áp dụng đề xuất [E]: persona = 4 trạng thái cold-start, phong cách du lịch là đặc trưng của khách, dormant 365 ngày

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành
- Phạm vi: docs, backend, data, evaluation

## Mục tiêu

Áp `docs/prd/update-archive/2026-10-09-persona-trang-thai-cold-start-va-phong-cach-du-lich.md` (người dùng chốt Q7, Q8 ngày 09/10) theo AGENTS.md §8: PRD trước rồi source. FR-REC-01, FR-REC-03, AC-REC-01.

## File thay đổi

- `docs/prd/project-brief.md` — sửa: §5 bảng persona = 4 trạng thái cold-start; đoạn "phong cách du lịch là đặc trưng của khách"
- `docs/prd/data-model.md` — sửa: `APP_USERS.persona` theo DDL
- `docs/prd/api-contract.md` — sửa: `/auth/me` bỏ `personaTag` (khớp contract)
- `docs/prd/user-flow.md` — sửa: §1 tiêu đề hành trình theo phong cách du lịch
- `docs/prd/requirements.md` — sửa: AC-REC-01
- `docs/prd/test-plan.md` — sửa: bảng E2E dòng 4
- `AGENTS.md` — sửa: §6.4 thay mục "bộ persona lệch" bằng quyết định đã chốt
- `src/backend/app/domain/recommendation/profile.py` — sửa: `DORMANT_AFTER_DAYS` 180 → 365 (configHash đổi)
- `src/backend/tests/conftest.py` — sửa: purchase của khách fixture `P3` lùi về 2025-08-01 (> 365 ngày) để vẫn là dormant
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: `dormantDays` 365, bảng §4.4, ghi chú §4.4, §4.8 (bỏ `halfLifeDays × 3` / `lastDestination` chưa cài, có số bench)
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: định nghĩa `strategy = dormant`
- `docs/spec/DATABASE_SCHEMA.md`, `docs/spec/MOCK_DATA_SPEC.md` — sửa: persona P3 chuyến cuối 400 ngày, `lifecycle_stage` CDP = churned
- `src/data_collection/seed/config.py` — sửa: `P3.trip_days_ago` (470, 190) → (700, 400); `seed_histories.py` — sửa chú thích
- `src/data_collection/tests/test_seed_histories.py` — sửa: P3 ("churned", 400); `test_seed_theme_profile.py` — sửa: golden demo / eval-v2 / append-v1
- `src/evaluation/recsys_bench/models/because.py`, `theme_study/layered_profile.py` — sửa: chú thích ngưỡng / đường dẫn đề xuất
- `docs/plan/2026-10-09-recsys-cong-thuc-oph.md`, `docs/spec/bench/recommendation_persona_profile_latency.md` — sửa: đường dẫn đề xuất
- `docs/prd/update/2026-10-09-persona-…md` → `docs/prd/update-archive/` — đổi tên (git mv), trạng thái "đã áp dụng"

## Quyết định

- `diagnostics.dormant` (contract, "event gần nhất > 90 ngày") không đổi nghĩa; ràng buộc "dormant ⟹ because daysAgo > 90" vẫn đúng.
- `cdp.profiles.lifecycle_stage` theo luật seed (181–365 dormant, > 365 churned) không đổi → tài khoản demo P3 có lifecycle CDP = churned, còn `strategy` engine = dormant.
- Golden hash của seed đổi: so dump cũ / mới chỉ khác lịch sử VP0000003 và số thứ tự trong ngày của mã nhóm `OFF<ngày><stt>` (VP0000272, VP0000522), nội dung event của khách khác giữ nguyên.
- Không thêm cột / trường API cho phong cách du lịch (ngoài phạm vi đề xuất).

## Kiểm tra

- `PYTHONUTF8=1 pytest src/backend/tests src/evaluation/recsys_bench/tests`: 2068 passed, 39 skipped.
- `PYTHONPATH=src pytest src/data_collection/tests/test_seed_*.py`: 73 passed (các test crawler khác thiếu thư viện `protego` trong `.venv` — lỗi môi trường có sẵn).
- Seed thật vào DB nháp `vota_seedchk` / `insider_seedchk` (container `vota-prodcopy-pg`, `--as-of 2026-10-09 --seed 42`, snapshot 2026-09-30, `--reset`): `db/verify.sql` toàn PASS, `db/verify_insider.sql` toàn PASS; VP0000003 = churned / 400 ngày. DB nháp đã xoá; khối seed-report trong `src/data_collection/README.md` không cập nhật (không phải lượt demo).

## Còn lại / rủi ro

- Môi trường dev / staging cần chạy lại seed (`make demo-db-reset` ở máy dev; job seed staging) để tài khoản P3 ra `dormant`.
- Baseline gate (`baseline_v3`) không còn so được — ghi baseline mới cùng lúc với [F] nếu chốt.
