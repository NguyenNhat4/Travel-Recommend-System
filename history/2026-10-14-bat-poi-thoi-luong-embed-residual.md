# Bật POI, thời lượng, embed residual làm mặc định production cho /search

- Ngày: 2026-10-14
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-evidence-gate
- Trạng thái: hoàn thành
- Phạm vi: backend, docs

## Mục tiêu

Người dùng xác nhận cấu hình đề xuất (14/10, sau khi test local và probe VM staging): bật mặc định `SEARCH_POI_RESOLVE`,
`SEARCH_DURATION_FILTER`, `SEARCH_DURATION_MASK`, `SEARCH_EMBED_RESIDUAL` (VM đang tắt POI nên "khách sạn gần Hồ Hoàn Kiếm" không lọc về Hà Nội).

## File thay đổi

- `src/backend/app/core/config.py` — sửa: 4 mặc định → `true`.
- `src/backend/tests/unit/api/test_search_settings_wiring.py` — sửa: ghim mặc định mới.
- `docs/prd/deployment-plan.md` — sửa: dòng biến môi trường cho 4 cờ + `SEARCH_EMIT_BACKGROUND`.

## Quyết định

- Căn cứ bench `src/evaluation/reports/eval-2026-10-14-search-evidence-gate-gold-v7.md`: `poi_resolution` +20,9 dev / +13,0 test; thời lượng + embed residual (r3) test +2,03 nDCG, không slice tụt trên test.
- `SEARCH_ENTITY_FILTER` giữ `false`: plan 07/10 yêu cầu Web xác nhận (đổi số đếm tab). `SEARCH_TAXONOMY_FILTER`, `SEARCH_EMIT_BACKGROUND` giữ `false`.

## Kiểm tra

- `pytest` api + application (search/settings) + contract: 198 passed; agents + architecture + application: 1188 passed, 3 xfailed.

## Còn lại / rủi ro

- Câu POI không dấu ít kết quả sau lọc (ngưỡng 0,84); ngưỡng tuyệt đối còn nhận rác ở đuôi — cần phương án ngưỡng tương đối.
