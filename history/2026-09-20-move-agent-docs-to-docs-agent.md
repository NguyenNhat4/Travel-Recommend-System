# Chuyển tài liệu agent sang docs/agent và tách nhỏ

- Ngày: 2026-09-20
- Tác giả: người dùng / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, evaluation

## Mục tiêu

`src/evaluation/agent/README.md` đã dài (186 dòng) và trộn hướng dẫn chạy, trace/node, response/lỗi, sinh fixture và cách chấm. Chuyển vào `docs/agent/` và tách theo chủ đề để dễ đọc, dễ sửa song song.

## File thay đổi

- `docs/agent/README.md` — thêm: mục lục và hướng dẫn chạy demo (nội dung phần mở đầu cũ, gồm lưu ý timeout).
- `docs/agent/langgraph-nodes.md` — thêm: đọc bảng trace, chín node, các luồng thực thi.
- `docs/agent/response-and-errors.md` — thêm: `status` so với `error.code`, luồng sau `UNSUPPORTED_DESTINATION`.
- `docs/agent/evaluation-suite.md` — thêm: chạy case/batch, dữ liệu và cách chấm, fixture còn thiếu, kiểm tra local.
- `docs/agent/fixture-generation.md` — thêm: sinh fixture và expected bằng LLM.
- `docs/agent/rubric.md` — đổi tên từ `src/evaluation/agent/agent_rublic.md` (sửa lỗi chính tả `rublic`), giữ nguyên nội dung.
- `src/evaluation/agent/README.md` — sửa: rút còn con trỏ tới `docs/agent/`, giữ file để quy ước "README của workstream" còn hiệu lực.
- `AGENTS.md` — sửa: dòng Itinerary Agent trong bảng 1.2 thêm `docs/agent/README.md`.
- `history/2026-09-20-move-agent-docs-to-docs-agent.md` — thêm: entry này.

## Quyết định

- Chỉ chia theo tiêu đề `##` cũ, giữ nguyên nội dung chữ; không viết lại. Mục nào đứng một mình (response, fixture) bỏ tiêu đề `##` trùng tên file.
- Các entry `history/` cũ vẫn ghi đường dẫn `src/evaluation/agent/README.md` và `agent_rublic.md` vì không sửa entry cũ; đường dẫn đó nay chỉ còn con trỏ hoặc đã đổi tên.
- Không đổi code hay contract.

## Kiểm tra

- Đối chiếu từ khóa đặc trưng của từng mục (`tphcm`, `passRate`, `oracleReviewed`, `conversation_id_of`, `draw_mermaid`, …) đều có trong file đích.
- Không còn file nào ngoài `history/` tham chiếu `agent_rublic.md` hoặc README cũ. `git diff --check`: pass.

## Còn lại / rủi ro

- Các lệnh trong tài liệu (chạy Streamlit, `unittest`) vẫn dùng đường dẫn tính từ repo root nên không đổi.
