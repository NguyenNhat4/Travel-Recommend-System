# Bộ golden kịch bản bản 5 và các lỗi chat thử 10/10 (lỗi I)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs
- Mã FR/NFR: FR-AGT-01, FR-AGT-03, FR-AGT-04, FR-AGT-05, FR-AGT-06, NFR-REL-01, NFR-SEC-04
- Plan: `docs/plan/2026-10-10-sua-loi-chat-thu-tro-ly.md`, đơn vị 6

## Mục tiêu

Chưa có dataset nào cho các cảnh của artifact "Kịch bản trợ lý V-OTA" bản 5, cũng như cho các lỗi chat thử 10/10 (A–H), nên
không đo lại được sau mỗi lần sửa.

## File thay đổi

- `src/evaluation/datasets/agent_scenarios_v5.yaml` — thêm: 11 case, 28 lượt: SC-A … SC-H (mỗi lỗi một case, câu nguyên
  văn), SC-MAIN (cảnh 1–9 của kịch bản, một hội thoại), SC-OUT (ngoài phạm vi), SC-H3 (tin nhắn rác).
- `src/evaluation/agent/golden.py` — sửa: khoá `textIncludes`, `phraseMaxCount`, `cardsMin`, `cardsMax`, `cardTaxonomies`,
  `suggestionsMin`, `warningsInclude` (`scenario_findings`).
- `src/evaluation/agent/case_builder.py` — sửa: hướng dẫn `FIELD_HELP` và nhóm form cho 7 khoá mới; mã cảnh báo
  `PRODUCT_NOT_ON_SALE_FOR_DATE`.
- `src/evaluation/agent/eval_app.py` — sửa: ô nhập cho các khoá mới (số, danh sách, dòng, "cụm=số").
- `src/evaluation/tests/test_golden.py` — sửa: kiểm dataset mới (cùng các kiểm tra của dataset cũ) và 4 test cho khoá mới.
- `src/evaluation/reports/eval-2026-10-10-agent-scenarios-v5.md` — thêm: biên bản chạy LLM thật.
- `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — sửa: bảng dataset, 7 khoá mới.
- `history/2026-10-10-golden-kich-ban-ban-5.md` — thêm: entry này.

## Quyết định

- Id dạng `SC-*` theo mã cảnh của artifact và mã lỗi của plan, riêng file với `agent_test_cases_nhat.yaml` (`TC-*`).
- Câu do code viết (hỏi loại vé, câu mở đầu lịch tham khảo, giờ mở cửa) kiểm bằng `textIncludes`; giọng văn kể chuyện kiểm
  bằng `phraseMaxCount` và `judge`.
- Các cảnh cần lịch có sẵn (đổi vé, đổi khách sạn, người dùng khó còn lại) chưa đưa vào: phụ thuộc chuyến bay/phương án
  của catalog từng ngày, dễ sai khi seed lại.

## Kiểm tra

- `pytest src/evaluation/tests/test_golden.py src/evaluation/tests/test_case_builder.py`: 92 passed.
- Golden LLM thật trên backend local (biên bản `src/evaluation/reports/eval-2026-10-10-agent-scenarios-v5.md`, commit
  `4a1a644`): cả bộ PASS 25/28, Grounding 100%, Structured Output 100%, Tool Calling 100%; 3 lượt fail đều do giám khảo
  lỗi gọi API khi chạy runner thiếu `ITINERARY_LLM_REASONING_EFFORT`. Chạy lại SC-A, SC-MAIN với môi trường gốc: 10/11 PASS;
  còn SC-MAIN lượt 8.

## Còn lại / rủi ro

- SC-MAIN lượt 8 ("Ok, lên lịch Hà Nội luôn"): trợ lý chỉ hỏi số ngày, kịch bản cảnh 7 muốn hỏi gộp số ngày, ngày đi, số
  người trong một câu. Ngoài 9 lỗi của đợt này; chưa sửa.
- Latency p95 40 giây (lượt lập lịch); lượt khám phá 4–15 giây.
