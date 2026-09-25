# Cập nhật báo cáo golden 2026-09-24 và khối seed-report

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, data

## Mục tiêu

Chạy lại bộ golden Itinerary Agent trên commit `82d077f` để số liệu trong slide thuyết trình khớp báo cáo, và đồng bộ khối seed-report trong README data collection với pipeline vector hiện tại (Weaviate).

## File thay đổi

- `src/evaluation/reports/eval-2026-09-24-golden.md` — sửa: báo cáo chạy lại (mode `dataset`, 89 lượt, PASS 74, FAIL 15; Grounding 100%, Structured Output 100%, Tool Calling 100% trên 77 lượt).
- `src/data_collection/README.md` — sửa: khối seed-report ghi ngày `2026-09-24` và dòng Search units nói vector được index sang Weaviate bằng `make index-vectors`.
- `docs/spec/agent/README.md` — sửa: thêm hai dòng mục lục cho `presentation-slides.html` và `presentation-script.md` (xem các entry `slide-*` cùng ngày).

## Quyết định

- Báo cáo mới chỉ chạy `dataset` (không kèm `sweep`) nên số lượt ít hơn báo cáo trước; latency p95 11339ms cao hơn mục tiêu 5000ms (không gate).
- Không đổi hành vi sản phẩm, contract hay DDL nên không lệch PRD.

## Kiểm tra

- Báo cáo do `python -m src.evaluation.agent.golden` sinh ra; ba chỉ số gate đều đạt.
- Không đổi contract hay mock nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- 15 lượt FAIL (G-006, G-008, G-012, G-047, G-051...) chưa xử lý; chi tiết trong báo cáo.
