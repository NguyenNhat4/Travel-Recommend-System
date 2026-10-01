# Hỏi lại khi người dùng muốn đổi mà chưa nói đổi thành gì

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Thay thế: 2026-09-30-de-xuat-hoi-lai-khi-doi-ma-chua-noi-cu-the.md
- Phạm vi: agent, evaluation, docs

## Mục tiêu

Sau khi đã có lịch, "đổi ngày" / "đổi địa điểm" không kèm giá trị mới làm agent lập lại lịch cũ và trả "Lịch trình đã
được hoàn tất.". Nay LLM ở `extract` nhận ra và điền `change_without_value`; backend hỏi lại đúng trường đó qua
`clarify`, giữ intent cũ, không gọi tool. Áp dụng đề xuất `docs/prd/update-archive/2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md`
(FR-AGT-01, FR-AGT-05), chốt bởi Nguyễn Minh Nhật ngày 2026-09-30.

## File thay đổi

- `docs/prd/architecture.md` — sửa: sơ đồ §3 thêm nhánh `CheckClarification --> AskUser` cho "muốn đổi mà chưa nói đổi thành gì".
- `docs/prd/update-archive/2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md` — thêm: đề xuất, trạng thái `đã áp dụng` (tạo ở `docs/prd/update/`, chuyển sang archive; file chưa từng được git theo dõi nên dùng `mv`).
- `src/backend/app/agents/models.py` — sửa: `Extraction.change_without_value` (danh sách trong `destination`/`days`/`startDate`/`party`/`budget`).
- `src/backend/app/agents/steps/classification.py` — sửa: `extract_result` trả `missing_info` (`clarification_reason = "change_without_value"`, `missing_fields` = các trường LLM báo) trước khối hỏi chi tiết; chốt an toàn `_supplies_a_change` (không hỏi khi intent sau gộp khác intent đã lưu hoặc ràng buộc đổi món `exclude_products`/`specific_hotel`/`specific_activity`/`require_hotel` đổi; giá trị rỗng coi như chưa có) và bỏ qua với `intent_override`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `EXTRACT_PROMPT` (khi nào điền `change_without_value`, không đặt `start_date_undecided` cho "đổi ngày"); `CONVERSATION_PROMPT` (luật `change_without_value`: nêu giá trị hiện tại, hỏi giá trị mới, một ví dụ).
- `src/backend/app/agents/steps/conversation.py` — sửa: `reply_title` và `clarification_fallback` cho lý do mới.
- `src/backend/app/agents/steps/messages.py` — sửa: khoá vi/en `title_change_without_value`, `change_without_value`, `change_field_*`.
- `src/backend/app/agents/nodes.py` — sửa: docstring `extract_node`.
- `src/backend/tests/unit/agents/test_classify.py` — sửa: `ChangeWithoutValueTests` (13 test, gồm các ca LLM thật: chép intent vào patch, liệt kê thừa trường, `exclude_products: []`, đổi khách sạn).
- `src/backend/tests/unit/agents/test_reply_titles.py` — sửa: tiêu đề cố định, tiêu đề tiếng Anh, câu dự phòng vi/en.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: test qua graph "đổi ngày" → `NEEDS_CLARIFICATION`, `missingFields == ["startDate"]`, không có node `tool`.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: G-079 viết lại (đổi ngày → hỏi lại; đổi sang ngày mới → lập lịch; đổi địa điểm → hỏi lại; "không đi nữa" chỉ kiểm phân luồng).
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.3) — sửa: lý do `change_without_value` và bảng tiêu đề.
- `history/2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md` — thêm. `history/2026-09-30-de-xuat-hoi-lai-khi-doi-ma-chua-noi-cu-the.md` (thêm dòng `Bị thay thế bởi`), `history/2026-09-30-payload-llm-dang-yaml.md` (cập nhật trạng thái) — sửa.

## Quyết định

- LLM quyết định nhận ra "đổi mà chưa nói cụ thể" (theo yêu cầu người dùng), backend chỉ làm theo và chặn trường hợp LLM tự mâu thuẫn (báo chưa có giá trị mà patch lại có giá trị).
- Không thêm node, không thêm lượt gọi LLM; contract không đổi (`NEEDS_CLARIFICATION`, `missingFields` đã có đủ năm trường).
- Không tăng `clarification_rounds` nên không bật form gợi ý.
- Không sửa `docs/prd/requirements.md` (theo tiền lệ các đề xuất 30/09); quy tắc ghi ở spec agent.
- Ngoài phạm vi: "không đi nữa", "ngày nào cũng được", "gợi ý lịch khác", tiêu đề `COMPLETED`.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture src/evaluation/tests`: xem số liệu cuối entry; chỉ còn 5 fail có sẵn trước thay đổi (3 `DatasetTests` và 2 `ScheduleFindingsTests` trong `test_golden.py`, xem `history/2026-09-30-sua-prompt-classify.md`).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS. `src/backend/tests/contract`: 70 passed.
- **Chạy `extract_node_async` với `gpt-4o-mini` thật** (nhiệt độ 0, intent Nha Trang 1 ngày có khách sạn + tour trong lịch, mỗi câu 10 lần): "đổi ngày", "đổi địa điểm", "đổi số người", "đổi ngân sách", "đổi số ngày" → hỏi lại 10/10; "đổi sang ngày 5/10", "đổi sang Đà Nẵng", "tăng ngân sách lên 10 triệu", "đổi khách sạn khác đi", "bỏ tour đảo đi", "thêm 1 bé" → lập lịch 10/10. Câu hỏi do `clarify` viết có tiêu đề, nêu giá trị hiện tại và ví dụ trả lời.
- Đo lần đầu (bản chưa có chốt an toàn) cho thấy hai lỗi đã sửa trong cùng thay đổi: (1) "đổi sang ngày 5/10" bị hỏi nhầm vì LLM liệt kê thừa `days`/`party`/`budget`; (2) LLM đặt `exclude_products` cho "đổi ngày", sẽ loại ngầm một sản phẩm ở lượt sau. Bản chốt an toàn đầu tiên (patch có giá trị thì không hỏi) vẫn sai vì LLM chép cả intent đang có vào patch (kể cả prompt cũ), và so `[]` với khoá chưa có làm khoảng nửa số lần "đổi ngày" lập lịch lại; đã sửa bằng so với intent đã lưu và coi giá trị rỗng như chưa có.

## Còn lại / rủi ro

- Kết quả trên là một môi trường và một model (`gpt-4o-mini`); LLM không tất định nên vẫn nên chạy G-079 lặp (`--repeat`) và xem trace `extract_node` trước khi merge.
- "đi 5 ngày" khi lịch đang 1 ngày bị LLM đặt `conflict=true` (7/10 lần) nên bị hỏi lại thay vì lập lịch. Lỗi có sẵn: prompt cũ cũng cho `conflict: True` với "đi 3 ngày". Chưa sửa, cần điều tra riêng (đây là yêu cầu đổi số ngày hợp lệ).
- "không đi nữa", "ngày nào cũng được" vẫn lập lại lịch cũ (ngoài phạm vi đề xuất); `COMPLETED` vẫn hiện "Lịch trình đã được hoàn tất." (`itinerary.title` để trống); form gợi ý làm mất thông tin lượt đầu chưa điều tra.
- Thu gọn ngữ cảnh `classify` và node tóm tắt lịch sử > 4000 token chưa làm.
- Đề xuất ReAct `docs/prd/update/2026-09-29-vong-react-co-chan-cho-node-tool.md` vẫn chờ chốt.
- Chưa commit.
