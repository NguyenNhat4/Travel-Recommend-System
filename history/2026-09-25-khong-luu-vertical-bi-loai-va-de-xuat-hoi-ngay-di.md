# Không lưu vertical Recommendation bỏ sang lượt sau; đề xuất hỏi ngày đi

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: agent, docs

## Mục tiêu

Người dùng báo lượt "1 ngày thôi" (sau "gợi ý lịch trình đi hà nội 3 ngày") ra FALLBACK. State của lượt đó cho thấy ba nguyên nhân:

1. `constraints.exclude_taxonomies = ["attraction"]`. `evaluate` (`_relaxed_constraints`) chép `diagnostics.excludedVerticals` của Recommendation vào `constraints`, và `finalize` lưu nó sang các lượt sau. Vì thế ở lượt sau `tool` cấm tìm điểm tham quan, và lịch lượt 1 chỉ có khách sạn.
2. `startDate = 2026-09-25`: người dùng không nói ngày nhưng LLM tự điền ngày hôm nay. Toàn bộ khách sạn Hà Nội trong DB local chỉ mở bán 15–16/10, nên bị loại vì sai ngày.
3. `exclude_products` chứa khách sạn của lượt 1. Có vẻ LLM hiểu "…thôi" là "bỏ đi"; state không cho biết lý do.

Người dùng yêu cầu: sửa lỗi 1; và khi người dùng không nói ngày thì đi qua `clarify` để hỏi ngày đi.

## File thay đổi

- `src/backend/app/agents/steps/evaluation.py` — sửa: vertical Recommendation bỏ chỉ dùng để lọc candidate của lượt hiện tại; `evaluate_retrieval` không trả `constraints` nữa.
- `src/backend/app/agents/nodes.py` — sửa: docstring `evaluate_node` bỏ `constraints` khỏi mục "Ghi".
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm `test_cross_sell_exclusion_is_not_saved_for_the_next_turn` (lượt 1 vẫn lọc; `constraints` trong state và trong store không chứa vertical đó; lượt 2 có lại điểm tham quan).
- `docs/prd/update/2026-09-25-hoi-ngay-di-truoc-khi-lap-lich.md` — thêm: đề xuất `chờ chốt`.

## Quyết định

- Lỗi 1 là sửa code cho khớp spec: `docs/spec/agent/state-fields.md` ghi `constraints` chỉ do `intake`, `classify` và `tool` ghi. Hành vi cross-sell trong một lượt vẫn giữ nguyên vì có test riêng (`test_cross_sell_excludes_hotel_and_preserves_real_because`).
- Hỏi ngày đi làm đổi AC-AGT-01 (PRD kỳ vọng ra lịch ngay khi không có ngày), đổi enum contract `missingFields` và golden dataset. Vì vậy đã viết đề xuất theo AGENTS.md mục 8 và dừng phần này, chưa code.
- Không sửa lỗi 3 (phụ thuộc LLM) trong entry này.

## Kiểm tra

- `pytest test_itinerary_runtime.py -k cross_sell`: 2 passed. Với `evaluation.py` cũ (dùng `git stash`), test mới trượt, đúng như mong đợi.
- Toàn bộ `src/backend/tests/unit/agents`, `tests/contract/test_assistant_contract.py`, `tests/architecture`: xem kết quả ở commit.

## Còn lại / rủi ro

- Chờ chốt đề xuất hỏi ngày đi.
- Phía Recommendation (`application/recommendation/use_cases.py` dòng 103–105): khi truyền `destination`, `excludedVerticals` vẫn lấy từ chuyến đang diễn ra của user dù chuyến đó ở thành phố khác. Chưa sửa; thuộc workstream RecSys.
- Dữ liệu: 529/529 khách sạn Hà Nội có cửa sổ mở bán 15–16/10, trái quy tắc 30 ngày ở AGENTS.md mục 6.2. Cần báo team Data.
- `itinerary.title` vẫn chưa được backend điền.

Bị thay thế bởi: 2026-09-25-hoi-ngay-di-truoc-khi-lap-lich.md (phần hỏi ngày đi)
