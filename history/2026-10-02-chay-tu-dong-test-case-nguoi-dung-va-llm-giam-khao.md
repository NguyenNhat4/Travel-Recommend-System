# Chạy tự động TC-01..TC-03 và LLM giám khảo

- Ngày: 2026-10-02
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu:
- Trước khi sửa agent theo đề xuất `docs/prd/update/2026-10-02-hoi-tiep-khi-cau-hoi-bi-cat-ngang.md`, chạy tự động 3 case đầu của `src/evaluation/agent/agent-test-cases-nhat.md`, dùng LLM làm giám khảo.
- 3 case này là bộ chính; bỏ bộ golden cũ. Người dùng chọn giữ file golden cũ và đặt bộ mới làm mặc định, vì test-plan §2.4 vẫn yêu cầu bộ benchmark khoảng 50 câu.

Phục vụ FR-AGT-01, FR-AGT-03, FR-AGT-05, NFR-REL-01 và test-plan §2.4.

## File thay đổi

- `src/evaluation/datasets/agent_test_cases_nhat.yaml` — thêm: TC-01 (đổi ngày nhiều lượt), TC-02 (form khớp lời gợi ý), TC-03 (giải thích khi không dựng được lịch); có tiêu chí `judge` chép từ "Tiêu chí đạt đề xuất".
- `src/evaluation/agent/golden.py` — sửa:
  - placeholder `:dm` ("14/10") và `:vi` ("14 tháng 10");
  - khoá `formMatchesAnswer`;
  - khoá `judge` với `judge_findings`, `JUDGE_PROMPT` và `--judge-model`;
  - dataset mặc định là bộ mới (`DEFAULT_DATASET`), `--report-slug` suy từ dataset;
  - sửa `schedule_findings`: gọi `_stay_order(sources, product)` theo chữ ký mới (từ 264fdbe), chỉ xét hotel còn chỗ. Lỗi này làm runner crash ở mọi lượt `COMPLETED`.
- `src/evaluation/tests/test_golden.py` — sửa: thêm test cho định dạng ngày mới, `formMatchesAnswer`, `judge_findings` (LLM giả), `report_slug`, nạp dataset mới, Search trước Recommendation ở luật chỗ ở; fixture `_product` có `available`.
- `src/evaluation/reports/eval-2026-10-02-agent-test-cases.md` — thêm: biên bản lần chạy có giám khảo.
- `docs/spec/agent/golden-run.md`, `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — sửa: hai dataset, cờ mới, khoá `judge`/`formMatchesAnswer`, placeholder mới, luật chấm của giám khảo.
- `.agents/skills/building-itinerary-agent/references/eval-loop.md` — sửa: dataset mặc định.

## Quyết định

- Không xoá `itinerary_agent_golden.yaml`. Xoá sẽ lệch test-plan §2.4. Người dùng chọn đặt bộ 3 case làm mặc định; bộ cũ chạy bằng `--dataset`.
- Giám khảo chỉ bổ sung cho check tất định (status, intent, toolCalled, forbiddenText...), không thay chúng. Finding mang tiền tố `[judge]`. Giám khảo lỗi hoặc trả sai số kết luận thì lượt FAIL, không pass lặng lẽ.
- Giám khảo mặc định cùng model với agent (`gpt-4o-mini`), nhiệt độ 0; có `--judge-model` để đổi.
- Ngày trong PDF đổi sang placeholder giữ khoảng cách tới hôm nay (02/10 → `{today}`, 14/10 → `{today+12}`), để case không cũ đi và nằm trong cửa sổ đặt chỗ.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py`: 62 passed, 3 failed. Ba lỗi có từ trước, ở nội dung bộ golden cũ (79 case trong khi test khoá 14): `test_has_exactly_one_case_per_category_with_unique_ids`, `test_clear_requests_state_their_start_date_...`, `test_a_start_date_question_is_answered_...`. Hai lỗi `cheapest_hotel` có từ trước đã sửa.
- LLM thật, backend local `inprocess` (3183 sản phẩm), `--repeat 3`, trace `nhat-agent-tc`:
  - chưa có giám khảo: PASS 23/27. Bốn lượt fail đều ở một lần chạy TC-01: lượt 1 gặp 503 `LLM_UNAVAILABLE` (`extract` timeout 30s, `search_products` timeout), các lượt sau mất ngữ cảnh;
  - có giám khảo: PASS 27/27; Grounding 1.0, Structured Output 1.0, Tool Calling 1.0. Giám khảo chạy đủ 15 lượt có tiêu chí (xem trên LangSmith, tag `golden-judge`).
- Hiệu chỉnh giám khảo bằng 3 câu trả lời cố tình sai, mỗi câu 3 lần (script tạm, không commit). Cả `gpt-4o-mini` và `gpt-4o` đều làm lượt sai FAIL ở mọi lần:
  - TC-01 "đã hoàn tất": 3/3 tiêu chí fail với mini, 2/3 với 4o;
  - TC-03 FALLBACK cũ: 1/3 với cả hai;
  - TC-02 form trống: 2/2 với mini, 1–2/2 với 4o.

## Còn lại / rủi ro

- TC-03 cả 3 lần ra `COMPLETED` với catalog hiện tại, nên nhánh "giải thích khi không dựng được lịch" chưa được chạy thật. Muốn kiểm nhánh đó cần một điểm đến hoặc ngày chắc chắn không có sản phẩm.
- Giám khảo dùng cùng model với agent. Nên thử `--judge-model` mạnh hơn khi có key.
- Biên bản ghi commit `ea944b9` nhưng chạy trên working tree chưa commit phần runner này.
- `src/evaluation/agent/agent-test-cases-nhat.md` (file của người dùng, chưa commit) nằm trong `src/`, trái AGENTS.md mục 7; nên chuyển sang `docs/spec/agent/`.
