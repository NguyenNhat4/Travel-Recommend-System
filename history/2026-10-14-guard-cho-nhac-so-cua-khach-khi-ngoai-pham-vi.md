# Guard cho câu ngoài phạm vi nhắc lại con số khách vừa viết

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng chọn không dùng NeMo Guardrails; triển khai phương án đã đề xuất: giữ precheck tất định + orc tự hiểu câu
ngoài lề (prompt ở `history/2026-10-14-sua-freeonly-gateway-va-cau-ngoai-pham-vi.md`), và cho guard chấp nhận con số
khách tự viết để câu từ chối như "xin 50 k" không rơi vào `NUMBER_WITHOUT_FACT` → `ITINERARY_VALIDATION_FAILED`.
AC-AGT-07, NFR-REL-01.

## File thay đổi

- `src/backend/app/domain/itinerary/orc_guardrails.py` — sửa: `final_issues` nhận `user_message`; số khớp tin hiện tại
  được bỏ qua chỉ khi câu trả lời không có sản phẩm, fact, thẻ hay phương án.
- `src/backend/app/agents/orc_v2.py` — sửa: guard truyền `state["message"]`.
- `src/backend/tests/unit/domain/test_orc_guardrails.py` — sửa: hồi quy số khách viết, số khác và câu có thẻ sản phẩm.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: ghi cách trả lời việc ngoài du lịch và ngoại lệ số.
- `history/2026-10-14-guard-cho-nhac-so-cua-khach-khi-ngoai-pham-vi.md` — thêm: entry này.

## Quyết định

- Không dùng NeMo Guardrails: NFR-SEC-04 quy định lọc trước LLM là luật tất định; topical rail là bước phân loại
  trước orc, đã gỡ theo AGENTS.md mục 3.
- Không lệch PRD: AC-AGT-07 đã yêu cầu trả 200 cho việc ngoài du lịch. Ngoại lệ số chỉ áp cho câu không nhắc sản
  phẩm/dữ kiện, nên số khách nói ("phòng 300k phải không") không thể thành giá sản phẩm; grounding giữ nguyên.
- So khớp bằng chuỗi bỏ khoảng trắng, chữ thường ("50 k" ≈ "50k"); số khác tin nhắn vẫn bị chặn.
- `public_explanation` (Think) không đổi: vẫn bỏ mọi số.

## Kiểm tra

- `pytest test_orc_guardrails.py test_orc_loop.py test_orc_contracts.py test_orc_tool_dispatch.py
  test_itinerary_tools.py test_assistant_v2_final.py test_assistant_v2_use_case.py test_assistant_v2_contract.py
  tests/architecture`: 132 passed, 1 warning có sẵn (model giả).
- Chưa thử model thật; backend đang chạy không `--reload`, cần khởi động lại.

## Còn lại / rủi ro

- Thử lại trên giao diện: "xin 50 k", "cho mượn tiền", "Tìm phương án tiết kiệm hơn" (Vũng Tàu, ngân sách 5 triệu).
