# `/search` 1.28.0 P0: cổng bằng chứng theo cụm, câu không giải thích được → rỗng, thời lượng theo vai trò, embed residual, phục hồi dấu, backgroundScore

- Ngày: 2026-10-13
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-evidence-gate (từ docs/search-evidence-gate-plan)
- Trạng thái: dang dở
- Phạm vi: backend, contract, frontend, evaluation, docs

## Mục tiêu

Làm P0 của `docs/plan/2026-10-13-search-evidence-gate-no-answer.md` (đề xuất `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md`
đã chốt 13/10; FR-SRC-01/03/04, AC-SRC-01, NFR-PERF-01): hết lớp lỗi "khớp một âm tiết khi câu không có đáp án"
("Nguyễn Khắc Tiệp", "2 ngày 1 đêm" → "Chợ Đêm", "Trần Thị Mai" → "Thị trấn Hoàng Hôn"). Mọi cờ mới mặc định tắt.

## File thay đổi

- `src/backend/app/domain/search/explain.py` — thêm: token giữ dấu (kiểu dấu cũ), `Grams` unigram/bigram, `phrase_hit`, `name_evidence`, `explain_residual` (đoạn cắt tại từ chức năng/span điều kiện; tên riêng chiếm toàn bộ residual → unexplained; cụm lạ → unparsed; chỉ còn chữ chung → unexplained), `has_content`, `SURNAMES`, `GENERIC_WORDS`, `TONE_STOPWORDS`.
- `src/backend/app/domain/search/hybrid.py` — sửa: `HybridConfig.evidence_gate`; `rrf_admissible` lọc phần cộng RRF của BM25.
- `src/backend/app/domain/search/query_plan.py` — sửa: `PlanFlags.duration_mask/embed_residual/unexplained`, `PlanGazetteers.vocab`, `QueryPlan.duration_role/dense_text/filter_only/unexplained/unparsed`; vai trò thời lượng gate/stay; mask + bước `families_in_order` cho duration; khai `denseText`/`unexplained`/`unparsed`/`duration.role`; hằng `ROLE_STAY`, `EMPTY_UNEXPLAINED`.
- `src/backend/app/domain/search/constraints.py` — sửa: `vertical_cue_spans` (mọi cue loại, không xét ngữ cảnh).
- `src/backend/app/domain/search/normalize.py` — sửa: `QueryNormalizer(restore=…)` phục hồi dấu theo cụm 2–4 âm tiết (≥ 80 % một cách viết), chạy trước alias; `NormalizedQuery.restored`.
- `src/backend/app/domain/catalog/unit_attributes.py` — sửa: `duration_days/duration_nights` suy từ tên / `suggestedDuration` / `attributes.nights` cho attraction, combo (`DURATION_TAXONOMIES`).
- `src/backend/app/application/ports/unit_index.py` — sửa: `mask(duration_days, duration_nights)` (gate: chỉ vé/combo khớp).
- `src/backend/app/application/search/use_cases.py` — sửa: cờ `duration_mask/embed_residual/unexplained_empty/emit_background/no_diacritics_restore`; plan dựng trước embed; rỗng sớm (không embed) khi unexplained; embed `denseText`; chế độ chỉ-filter; bằng chứng tên / mô tả trong `_hybrid`; `backgroundScore`, `saturated`, `accentRestored`, `evidenceGate`; `_mode_diagnostics`; `unit_text`.
- `src/backend/app/core/config.py` — sửa: `SEARCH_EVIDENCE_GATE`, `SEARCH_DURATION_MASK`, `SEARCH_EMBED_RESIDUAL`, `SEARCH_UNEXPLAINED_EMPTY`, `SEARCH_EMIT_BACKGROUND`, `SEARCH_NO_DIACRITICS_MODE=restore`.
- `src/backend/app/main.py` — sửa: nối cờ; version 1.28.0.
- `src/shared/contracts/openapi.yaml`, `schemas/search.yaml`, `schemas/common.yaml` — sửa: 1.28.0 additive (duration.role, denseText, unexplained, unparsed, emptyReason `unexplained`, định nghĩa R khi evidenceGate/filterOnly, ghi chú backgroundScore).
- `src/frontend/src/types/api.gen.ts` — sửa: regen.
- `src/frontend/src/services/search.ts`, `src/frontend/src/components/search/SearchView.tsx` — sửa: `isWeakMatch` (margin 0,058 + trần 0,88 + |F| ≥ 20, bỏ qua chỉ-filter; không có backgroundScore → luật 0,35 cũ), `unexplained` vào empty state, nhãn "Kết quả gần nhất".
- `src/evaluation/search_bench/app_adapter.py` — sửa: khoá tuỳ chọn `evidence_gate`, `duration_mask`, `embed_residual`, `unexplained_empty`, `emit_background`, `no_diacritics_mode: restore` (vắng ≡ tắt, arm cũ giữ hash).
- `src/evaluation/search_bench/arms/APP.e5s.prod_f12356_{ev,dm,er,ue,rs,all}.yaml` — thêm: 6 arm.
- `src/backend/tests/unit/domain/test_explain.py`, `src/backend/tests/unit/application/test_search_v128_evidence_gate.py` — thêm; `src/backend/tests/contract/test_search_contract.py` (thêm test 1.28.0), `test_search_llm_contract.py` (ghim 1.28.0) — sửa; `src/frontend/tests/unit/searchService.test.ts` — sửa (2 test mới).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` (§2.4 núm, AC 10g), `docs/spec/hop-dong-tich-hop-frontend.md` (băng kết quả gần nhất) — sửa.

## Quyết định

- Bước 0.2 (đo catalog snapshot): không combo nào có `nights` (cả sau `parse_combos.combo_attributes`); suy được số ngày cho 42 unit qua tên (30 attraction, 12 combo) + 55 qua `suggestedDuration` ("1 ngày"). "1 đêm" chỉ khai; câu chỉ nêu đêm → gate làm F rỗng (emptyReason duration), không giả định.
- Bước 0.3 (offline, normalizer + query plan thật, vocab 3.183 unit, mọi cờ bật): gold_v6 175 câu active — chặn nhầm câu có đáp án **0/168 (0,0 %)** (cổng ≤ 2 %), câu ngoài catalog trả rỗng **6/7**; probe 43 câu đúng kỳ vọng ("Nguyễn Khắc Tiệp" / "khách sạn Nguyễn Khắc Tiệp" / "Trần Thị Mai" / "xkcd" rỗng; "khách sạn Đà Lạt rẻ bèo", "Sông Bằng", "VinWonders", "Phạm Văn Đồng" giữ; "Nguyễn Khắc Tiệp gần biển" → unparsed tên, embed "gần biển"). Script `scratchpad/m03.py` (ngoài repo).
- "Có điều kiện" của luật residual = có filter đang áp, hoặc câu nêu điểm đến catalog (kể cả khi F1 tắt); cue loại một mình không tính — để "combo du lịch Cà Mau" rỗng mà "khách sạn Đà Lạt rẻ bèo" vẫn tìm.
- Stopword so ở dạng giữ dấu cho token có dấu ("chợ" là nội dung, "cho" mới là từ chức năng) — test bắt được lỗi này.
- Chế độ chỉ-filter: retrieve không cutoff (−1 nội bộ), response khai `cutoff: 0`.
- `backgroundScore` = trung vị top-K dense trong F (xấp xỉ định nghĩa §3.4 "toàn bộ F"), ghi rõ trong contract.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py`: PASS (120 schemas…).
- `pytest src/backend/tests/unit/domain/test_explain.py src/backend/tests/unit/application/test_search_v128_evidence_gate.py`: 48 passed.
- `pytest src/backend/tests/contract/test_search_contract.py test_search_llm_contract.py`: 10 passed.
- `pytest src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`: 3084 passed, 2 skipped.
- `npx vitest run` (frontend): 81 file — lần chạy đầy đủ 849/850 pass, test hỏng là test mới (mock Response dùng lại), đã sửa; `tests/unit/searchService.test.ts` 20/20. `npx tsc --noEmit`: sạch.
- `pytest evaluation/search_bench/tests` (.venv-sbench): 596 passed, 1 failed `test_prewarm_list_matches_gold_active_of_its_tag` — có sẵn (file prewarm lệch tag gold, không liên quan thay đổi này).

## Còn lại / rủi ro

- Bước 2 (gold_v7: slice `no_answer`, `name_collision`, `duration_only`, `duration_stay`, `slang_residual`, 10 câu âm AC 7) chưa làm.
- Bước 11 (bench 6 arm trên gold, compare dev/test, guards, regress, report `src/evaluation/reports/`) chưa chạy: cần `sb app-load --recreate` lên Weaviate bench dùng chung (127.0.0.1:58080) — chờ người dùng đồng ý. Ngưỡng frontend (0,058 / 0,88 / 20) là giá trị tạm, chốt trên dev ở bước này.
- Bước 13 rollout (bật cờ ở VM) chưa làm; đề xuất 2026-10-13 giữ ở `docs/prd/update/` tới khi xong (chuyển `update-archive/`, trạng thái `đã áp dụng`).
- P1 (trường BM25 riêng + ablation T0–T5) chưa làm.
- Dựng vocab cho cờ `unexplained_empty` mất ~23 s trên 3.183 unit ở máy dev (lúc nạp catalog, chạy lại mỗi chu kỳ nạp) — đo lại trên VM; nếu chậm thì cache theo `catalog version`.
