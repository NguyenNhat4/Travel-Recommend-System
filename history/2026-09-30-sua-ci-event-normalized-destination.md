# Sửa CI đỏ: event "normalized destination" không còn được phát

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

CI job "Run backend tests" fail ở `test_itinerary_runtime.py::RuntimeTests::test_abbreviation_is_resolved_by_llm_from_catalog_names_only`.

## Nguyên nhân

Commit `ce726c3` chuyển bước chuẩn hoá điểm đến sang node `extract` (`check_destination`), gọi `canonical_destination` với danh sách `changed` bỏ đi. Khi tới node `tool`, điểm đến đã chuẩn nên `changed` rỗng và event chỉ còn "retrieval completed"; không còn event nào báo điểm đến đã được chuẩn hoá.

## File thay đổi

- `src/backend/app/agents/steps/tool_planning.py` — sửa: `check_destination` giữ `changed` và phát event `extract` "normalized destination" khi tên điểm đến đổi.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: test tìm event ở node `extract` thay vì `tool`.

## Quyết định

Khôi phục event ở nơi việc chuẩn hoá thực sự xảy ra, không đưa lại việc chuẩn hoá vào `tool` (sẽ gọi LLM chọn điểm đến hai lần).

## Kiểm tra

- `python3 -m pytest -q src/backend/tests/unit/agents`: 214 passed.

## Còn lại / rủi ro

Không.
