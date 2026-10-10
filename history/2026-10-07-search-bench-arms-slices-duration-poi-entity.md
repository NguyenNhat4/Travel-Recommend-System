# Bench search cho 1.18.0: cờ tuỳ chọn, 4 arm, 2 slice gold mới, trường parse mới, nháp gold v6a + probe fixture

- Ngày: 2026-10-07
- Tác giả: tqanh123 (người dùng chốt) / Claude (Fable 5.1, agent bench)
- Nhánh: fix/search-production
- Trạng thái: dang dở — wiring + nháp xong; **chưa chạy** `sb run` (identity `topids-diff`, probe, 5 arm) vì cần Weaviate bench local;
  gold_v6 chờ QAnh gán nhãn
- Phạm vi: evaluation, docs

## Mục tiêu

Plan `docs/plan/2026-10-07-search-duration-entity-poi.md` Bước 8: bench đo được ba cờ mới (`duration_filter`, `poi_resolve`,
`entity_filter`) trước khi bật production; slice gold `duration_false_positive`, `poi_resolution`; probe fixture để đo parse accuracy +
Forbidden@10 không cần nhãn (quyết định 07/10: probe trước, gold_v6 sau). Phục vụ FR-SRC-01, FR-SRC-03, FR-SRC-04; AC-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/app_adapter.py` — sửa: `V118_FLAG_KEYS` tuỳ chọn (`p.setdefault(k, False)`, kiểm bool, `NEUTRAL`,
  `supported_kwargs`) — KHÔNG vào `APP_DEFAULTS` nên 55 arm YAML và `regression/baseline_v1.json` giữ nguyên hash (tiền lệ `app.llm`).
- `src/evaluation/search_bench/metrics.py` — sửa: `PARSE_FIELDS` += `duration_days`, `duration_nights` (INT), `entity` (LIST),
  `entity_role`, `location_entity` (STR); `plan_fields` đọc `queryPlan.duration/entity/location`.
- `src/evaluation/search_bench/config.py`, `config/sbench.yaml` — sửa: slice mới quota 9 + 12 → `gold.target` 232, `minimum` 51;
  comment `DEFAULT_GOLD_FIELDS`. `config/query_annotations.yaml` — sửa: comment đầu file (trường mới).
- `src/evaluation/search_bench/gold_schema.py` — sửa: `SLICES` nối CUỐI `duration_false_positive`, `poi_resolution` (RNG `sb gold split`
  theo index — golden test giữ nguyên).
- `src/evaluation/search_bench/__main__.py` — sửa: `qu gold-scan` nhận ba cờ, hai kiểm tra theo slice mới.
- `src/evaluation/search_bench/debug_search_app.py` — sửa: badge 1.18.0, ba checkbox, `_plan_gazetteers(..., entities=, destinations=)`.
- `src/evaluation/search_bench/arms/APP.e5s.prod_f12356_{dur,poi,ent,dur_poi_ent}.yaml` — thêm (parent `APP.e5s.prod_f12356`).
- `src/evaluation/search_bench/gold/v6a/{drafts_raw.tsv, drafts.txt, probe.jsonl}` — thêm: 21 câu c0736–c0756 (bảng plan §5) +
  fixture probe ngoài `gold/` (version `fixture:<sha>`, không trích dẫn).
- `src/evaluation/search_bench/tests/{test_app_adapter,test_metrics_phase_a,test_config}.py` — sửa.
- `docs/spec/bench/arms.md` — sửa: đoạn "Knob 07/10 (contract 1.18.0, tuỳ chọn như `app.llm`)" + bảng 4 arm.

## Quyết định

- Cờ mới là khoá **tuỳ chọn** của khối `app:` (vắng ≡ off) để không đổi `config_hash` của 55 arm và baseline regress.
- Hai kỳ vọng probe lệch bảng plan theo hành vi backend thật (ghi ở `review_note`): c0752 "homestay phố cổ Hội An" →
  `location_entity` null (alias chồng span "Hội An" của normalizer; điểm đến vẫn Hội An); c0756 "Hồ Gươm hoặc Cầu Rồng" →
  `location_entity` ho_hoan_kiem (POI đầu tiên) nhưng destination null (multi).
- `drafts_raw.tsv` `source_refs` ngăn bằng `;` như v4a; không thêm README trong `gold/v6a` (AGENTS §7).

## Kiểm tra

- `.venv-sbench` `pytest src/evaluation/search_bench/tests -q`: trước sửa **54 failed / 523 passed / 11 skipped**; sau sửa
  **54 failed / 543 passed / 11 skipped** — tập test lỗi y hệt (checksum pool CRLF trên Windows, có sẵn), +20 test mới pass.
- `pytest tests/test_app_adapter.py tests/test_metrics_phase_a.py tests/test_config.py tests/test_gold.py`: 184 passed, 2 skipped;
  `config_hash` của `APP.e5s.prod_f12356` không đổi so với `regression/baseline_v1.json`.
- Smoke: `metrics.load_gold(gold/v6a/probe.jsonl)` → 21 bản ghi; parse_ok dry-run trên plan luật backend khớp `expected_parse`.
- **Chưa chạy**: `sb --run-id 2026-10-07-identity run --arm APP.e5s.prod_f12356` + `topids-diff` với `2026-10-06-gold-v4-r2` (kỳ vọng rỗng);
  `sb --run-id 2026-10-07-v6a-probe run --gold gold/v6a/probe.jsonl --arm …` + `guards`; `sb gold pool/split` cho v6a.

## Còn lại / rủi ro

1. Chạy identity + probe + 5 arm (cần `docker compose -f evaluation/search_bench/docker/compose.yml up -d weaviate` và `app-load`);
   viết report `src/evaluation/reports/eval-2026-10-07-search-duration-entity-poi.md`.
2. Gold v6a: pool (`--arm E2.e5s`) → split `--overlap 0` → QAnh gán nhãn → merge → `import --append --provenance pool@gold_v6` →
   annotations c0736–c0756 (chỉ sau import) → check / verify-append → holes → người dùng `git tag gold_v6` → devtest.
3. c0753 "khach san gan san bay Noi Bai": catalog bench có thể không có khách sạn gần Nội Bài — QAnh cân nhắc `expected_no_result`.
4. `gold-scan` dùng bảng entity đầy đủ (không thu hẹp theo catalog) — chỉ là chẩn đoán định nghĩa.
5. Đề xuất chờ `docs/prd/update/2026-10-06-search-hybrid-min-coverage-rrf.md` nên bench lại cùng slice `duration_false_positive`.
