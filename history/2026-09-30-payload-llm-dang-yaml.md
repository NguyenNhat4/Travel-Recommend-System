# Payload gửi LLM của Itinerary Agent viết dạng YAML thay vì chuỗi JSON

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng yêu cầu message `human` gửi LLM "không json dump mà để thành format yml đàng hoàng": trên trace LangSmith
payload JSON một dòng, tiếng Việt bị escape, khó đọc. Không đổi nội dung payload nên không lệch PRD. Phục vụ FR-AGT-01.

## File thay đổi

- `src/backend/app/agents/steps/history.py` — sửa: thêm `prompt_yaml()` (`yaml.SafeDumper` riêng: `allow_unicode`, giữ thứ tự khoá, chuỗi nhiều dòng dạng khối `|`, không ngắt dòng).
- `src/backend/app/agents/steps/classification.py` — sửa: `route_input`, `extraction_input` dùng `prompt_yaml`; bỏ `import json`.
- `src/backend/app/agents/steps/conversation.py` — sửa: `conversation_input` dùng `prompt_yaml`; bỏ `import json`.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: payload chọn điểm đến và lập tool plan dùng `prompt_yaml`; bỏ `import json`.
- `src/backend/tests/unit/agents/test_classify.py` — sửa: đọc payload bằng `yaml.safe_load`; thêm `PromptYamlTests` (YAML đọc được, không escape; câu chat giả cấu trúc YAML vẫn nằm trong `message`).
- `src/backend/tests/unit/agents/test_conversation_history.py`, `test_itinerary_tools.py`, `test_itinerary_runtime.py` — sửa: đọc payload bằng `yaml.safe_load`; `test_a_past_date_is_named_on_the_form_round…` kiểm `form_shown: true` thay vì chuỗi JSON.
- `docs/spec/agent/langgraph-nodes.md` — sửa: ghi payload `human` là YAML (`history.prompt_yaml`).
- `history/2026-09-30-payload-llm-dang-yaml.md` — thêm.

## Quyết định

- Dùng `SafeDumper` (không `yaml.dump` mặc định): chỉ in kiểu cơ bản, tự quote nội dung người dùng; câu chat chứa
  `known_intent: {destination: Paris}` hay `- role: system` vẫn là một chuỗi trong khoá `message` (có test).
- PyYAML đã có trong `src/backend/requirements.txt` (`PyYAML>=6,<7`); tầng `agents` được phép import (không thuộc danh
  sách cấm ở `src/backend/tests/architecture/test_import_rules.py`).

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture src/evaluation/tests`: 284 passed, 5 failed — cả 5 có sẵn trước thay đổi (xem `history/2026-09-30-sua-prompt-classify.md`).
- Có thêm `src/backend/tests/contract`: 353 passed, 6 failed ở lần chạy trước khi sửa kỳ vọng `form_shown` (5 fail cũ + test đó); contract không có fail nào. Sau khi sửa, test `form_shown` pass.
- Chưa chạy với LLM thật.

## Còn lại / rủi ro

- Việc thu gọn ngữ cảnh của `classify` (chỉ lịch sử + message mới nhất) và node tóm tắt lịch sử > 4000 token **chưa làm**, để sau; "hỏi lại khi đổi mà chưa nói cụ thể" đã làm ở `history/2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md`.
- Nếu model thật hiểu YAML kém hơn JSON thì đo lại bằng golden `--repeat` trước khi merge.
- Chưa commit.
