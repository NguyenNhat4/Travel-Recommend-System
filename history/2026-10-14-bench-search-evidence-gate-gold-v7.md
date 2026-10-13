# Bench /search 1.28.0 trên gold_v7 (Bước 11) và sửa hai lỗi bench lộ ra

- Ngày: 2026-10-14
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-evidence-gate
- Trạng thái: dang dở
- Phạm vi: backend, evaluation

## Mục tiêu

Bước 11 của `docs/plan/2026-10-13-search-evidence-gate-no-answer.md`: đo 6 arm 1.28.0 trên gold_v7 (kiểm lại `gold check` xanh,
252 câu) để quyết định bật cờ nào ở VM (Bước 13).

## File thay đổi

- `src/backend/app/domain/search/query_plan.py` — sửa: span "đã hiểu" khi giải thích residual luôn gồm thời lượng, địa danh gazetteer, alias entity (kể cả khi cờ họ đó tắt); thêm `PlanGazetteers.entity_spans`.
- `src/backend/app/domain/search/explain.py` — sửa: thêm `token_hit`.
- `src/backend/app/application/search/use_cases.py` — sửa: phần cộng RRF dưới cổng bằng chứng chỉ cần một âm tiết giữ dấu (vớt BM25 vẫn đòi cụm).
- `src/evaluation/reports/eval-2026-10-14-search-evidence-gate-gold-v7.md` — thêm: report.

## Quyết định

- r1: `_ue` chặn nhầm 3 câu có đáp án, `_ev` làm tụt câu mô tả (abbrev_typo −10.4, dest_type −14.3) → sửa như trên; r2: hai arm TIE, không slice tụt ≥ 3 (trừ `_ev` test parent_child −3.27, n 5).
- `duration_mask` giữ hành vi đã chốt (gate cứng) dù tụt duration_false_positive −25.7 dev: chuyển sang gate mềm khi câu còn nội dung là quyết định mới, cần người dùng chốt.

## Kiểm tra

- `pytest src/backend/tests/unit/domain/test_explain.py src/backend/tests/unit/application/test_search_v128_evidence_gate.py src/backend/tests/contract/test_search_contract.py`: 52 passed.
- `sb gold check`: xanh (252 câu). Bench r1 + r2: số ở report.

## Còn lại / rủi ro

- Người dùng chốt cờ bật ở VM (Bước 13); `duration_mask` cần quyết định gate mềm / cứng.
- Duyệt nhãn máy gold_v7 (name_collision tên đường; holes của duration_stay / slang_residual).
- Đo thời gian dựng vocab (`unexplained_empty`) trên VM.
