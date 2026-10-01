# Đưa prompt các node lên LangSmith Prompt Hub (seed) và đề xuất nạp theo tag

- Ngày: 2026-10-01
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Phạm vi: agent, docs

## Mục tiêu

Cho phép versioning và thử nghiệm prompt của các node LLM (`classify`, `extract`, `converse`, `tool`) trên LangSmith.
Phục vụ FR-AGT-01, FR-AGT-03. Phần seed hub không đổi hành vi chạy; phần backend nạp prompt từ hub lúc chạy lệch PRD
(thêm phụ thuộc ngoài + biến môi trường) nên chỉ có đề xuất, chưa code.

## File thay đổi

- `src/backend/scripts/push_prompts_to_langsmith.py` — thêm: đẩy 6 hằng số của `steps/prompts.py` lên hub (mustache, private) và gắn tag `prod`; có `--dry-run`, `--tag`.
- `docs/prd/update/2026-10-01-langsmith-prompt-hub.md` — thêm: đề xuất `chờ chốt` nạp prompt theo tag, tắt mặc định, fallback về hằng số.
- `history/2026-10-01-langsmith-prompt-hub.md` — thêm.

## Quyết định

- Mỗi lệnh gọi LLM một prompt hub, tên `vota-itinerary-{classify,extract,converse,tool-plan,similar-hint,destination}`; chỉ system text tĩnh, hậu tố ngôn ngữ và payload YAML ở lại code.
- Đẩy dạng mustache vì `EXTRACT_PROMPT` có `{adults: N, ...}` mà f-string coi là biến (prompts.py không có `{{`).
- Hằng số trong `prompts.py` vẫn là nguồn gốc và fallback; hub chưa được backend đọc.
- Prompt đẩy lên `private`, tag `prod` ở commit đầu.

## Kiểm tra

- `--dry-run`: liệt kê đủ 6 prompt.
- Chạy thật với `LANGSMITH_API_KEY` từ `.env`: 6 prompt tạo thành công; `pull_prompt("<tên>:prod")` trả text trùng từng ký tự với hằng số (6/6 True).
- Chưa chạy pytest vì không sửa code ứng dụng; chưa có test cho script.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất `docs/prd/update/2026-10-01-langsmith-prompt-hub.md`; sau đó mới làm `prompt_hub.py`, nối vào 3 file step, cờ cấu hình, test, cập nhật PRD và spec agent.
- Cho đến khi chốt, sửa prompt trên hub chưa ảnh hưởng chatbot.
- Chưa commit.
