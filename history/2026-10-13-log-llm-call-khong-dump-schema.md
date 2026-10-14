# Log `assistant.llm.call` không dump cả JSON schema

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Log local cho thấy mỗi dòng `assistant.llm.call` của orc v2 chứa nguyên JSON schema `OrcDecision` (hàng chục KB). Orc truyền
schema dạng dict vào `with_structured_output`, còn `_LoggedStructured` dùng `str(schema)` khi không có `__name__`.

## File thay đổi

- `src/backend/app/agents/steps/messages.py` — sửa: schema dạng dict chỉ ghi `title`; không có tên thì ghi tên kiểu.

## Quyết định

- Giữ field `schema` của log là tên ngắn như với schema Pydantic (`docs/spec/logging-schema.md` §4 chỉ ghi schema, thời
  gian, kết quả).

## Kiểm tra

- `pytest tests/unit/agents` (từ `src/backend`, loại test snapshot): 628 passed, 3 xfailed. Hai test của
  `test_behavior_snapshot.py` cũng FAIL khi chưa sửa file này (do thay đổi prompt đang có trong working tree), không liên
  quan.

## Còn lại / rủi ro

- Cassette của `test_behavior_snapshot.py` cần ghi lại sau khi chốt prompt.
