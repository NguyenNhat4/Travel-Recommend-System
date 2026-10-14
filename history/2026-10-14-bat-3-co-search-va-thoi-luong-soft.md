# Bật 3 cờ search 1.28.0 làm mặc định production; thời lượng chỉ lọc cứng khi câu chỉ có thời lượng

- Ngày: 2026-10-14
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-evidence-gate
- Trạng thái: dang dở
- Phạm vi: backend, contract, docs

## Mục tiêu

Người dùng chốt 14/10 sau bench gold_v7 (`src/evaluation/reports/eval-2026-10-14-search-evidence-gate-gold-v7.md`): bật
`SEARCH_EVIDENCE_GATE`, `SEARCH_UNEXPLAINED_EMPTY`, `SEARCH_NO_DIACRITICS_MODE=restore` (Bước 13, plan
`docs/plan/2026-10-13-search-evidence-gate-no-answer.md`) và đổi luật thời lượng: chỉ lọc cứng khi câu chỉ có thời lượng.

## File thay đổi

- `docs/prd/update/2026-10-14-search-thoi-luong-chi-loc-khi-chi-co-thoi-luong.md` — thêm: đề xuất (đã chốt bởi tqanh123 14/10).
- `docs/prd/requirements.md` — sửa: FR-SRC-03 ý thời lượng (chỉ lọc khi câu chỉ nêu thời lượng).
- `docs/prd/deployment-plan.md` — sửa: mặc định production mới của `SEARCH_NO_DIACRITICS_MODE`, `SEARCH_EVIDENCE_GATE`, `SEARCH_UNEXPLAINED_EMPTY`; tách dòng 3 cờ còn tắt.
- `src/backend/app/core/config.py` — sửa: 3 mặc định.
- `src/backend/app/domain/search/query_plan.py` — sửa: `ROLE_SOFT`; `_understood_spans` (dùng chung cho residual và vai trò thời lượng; `names_are_content` cho tên điểm vui chơi / entity).
- `src/shared/contracts/schemas/search.yaml` — sửa: `queryPlan.duration.role` enum `[gate, soft, stay]` (1.28.0 chưa phát hành).
- `src/backend/app/application/itinerary/contracts.py` — sửa: `validator(name)` lưu đệm validator theo schema.
- `src/backend/app/agents/tools/itinerary_gateway.py` — sửa: dựng sẵn bundle contract + validator `ProductDetail` / `DestinationListResponse` khi tạo gateway.
- `src/backend/tests/unit/api/test_search_settings_wiring.py`, `src/backend/tests/unit/application/test_search_v128_evidence_gate.py` — sửa / thêm test.
- `src/evaluation/reports/eval-2026-10-14-search-evidence-gate-gold-v7.md` — sửa: thêm r3 + quyết định bật cờ.

## Quyết định

- Câu "VinWonders 3 ngày 2 đêm": tên điểm vui chơi tính là nội dung → `soft`; bench r3 duration_false_positive dev −25.7 → −5.7, test −7.0 → +8.0. `SEARCH_DURATION_MASK` vẫn tắt (dev còn −5.7).
- Test agent `test_catalog_hydration_is_concurrent_and_bounded` hỏng từ commit 64cf011f: contract lớn hơn làm lần dựng bundle + validator đầu tiên (≈1,1–1,3 s) rơi vào timeout 1 s của lời gọi tool `get_product_detail`. Đây cũng là rủi ro production (request đầu sau khởi động) → sửa ở gateway (dựng sẵn) và `contracts.valid` (lưu đệm validator), không nới timeout.

## Kiểm tra

- `pytest src/backend/tests/unit/agents`: 664 passed. `pytest` test search v128 / explain / settings wiring: 53 passed. `validate_contract.py`: PASS (chạy lại khi commit).
- Bench r3 `2026-10-14-gold-v7-r3`: số ở report.
- `pytest src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`: 3085 passed, 2 skipped.

## Còn lại / rủi ro

- Merge PR vào `release-mvp-v2` để CD deploy lên VM — chờ người dùng đồng ý; sau deploy: probe live, theo dõi `total = 0` 48 h, đo thời gian dựng vocab trên VM.
- `SEARCH_DURATION_MASK` / `SEARCH_EMBED_RESIDUAL` / `SEARCH_EMIT_BACKGROUND` còn tắt; duyệt nhãn máy gold_v7; P1.
