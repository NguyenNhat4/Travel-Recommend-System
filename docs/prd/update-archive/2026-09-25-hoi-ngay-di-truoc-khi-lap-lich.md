# Hỏi ngày đi trước khi lập lịch trình

- Ngày: 2026-09-25
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-25 (chốt kèm yêu cầu sửa golden dataset)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01)
- Mã FR/NFR: FR-AGT-01, FR-AGT-03

## Lý do

Hiện trợ lý chỉ bắt buộc có điểm đến và số ngày. Khi người dùng không nói ngày đi, LLM đôi khi tự điền ngày hôm nay (`startDate`). Ngày tự đoán đó sai lệch thực tế: mọi sản phẩm không mở bán vào ngày đó đều bị loại. Ví dụ thật ngày 25/09: "Hà Nội, 1 ngày thôi" ra FALLBACK, vì toàn bộ khách sạn Hà Nội chỉ mở bán 15–16/10.

Người dùng muốn: nếu chưa nói ngày đi thì trợ lý hỏi lại ngày đi, không tự đoán.

## Nội dung đề xuất

**`docs/prd/requirements.md` §3, AC-AGT-01**

- Hiện tại: Kịch bản *"Lập lịch trình 3 ngày 2 đêm tại Nha Trang ngân sách 5 triệu"* → "Trợ lý xuất ra lịch trình 3 ngày có cấu trúc; …"
- Thay bằng: Kịch bản *"Lập lịch trình 3 ngày 2 đêm tại Nha Trang ngân sách 5 triệu"* → "Trợ lý hỏi ngày đi. Người dùng trả lời một ngày cụ thể, hoặc trả lời chưa chốt ngày; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; …". Nếu câu đầu đã có ngày đi (*"… từ 10/10"*) thì trợ lý xuất lịch ngay, như hiện nay.

Quy tắc hành vi đi kèm, ghi ở spec:
- Thứ tự hỏi: điểm đến → số ngày → ngày đi. Mỗi lượt chỉ hỏi một câu, như quy tắc hiện có.
- Chỉ hỏi ngày đi **một lần** mỗi hội thoại. Người dùng trả lời "chưa biết" hoặc "linh hoạt" thì lập lịch không kèm ngày (`startDate = null`), không hỏi lại.
- LLM không bao giờ tự điền `startDate` khi người dùng không nói ngày.

## Ảnh hưởng

- **Thêm một lượt hỏi đáp** cho mọi yêu cầu không có ngày đi, trong khi đa số câu trong golden dataset không có ngày đi. Khoảng 29 lượt đang kỳ vọng `COMPLETED` phải sửa kỳ vọng thành "hỏi ngày trước". Chỉ số độ trễ và số lượt sẽ thay đổi.
- **Contract (thay đổi thêm, không phá vỡ):** thêm giá trị `startDate` vào enum `ItineraryNeedsClarification.missingFields`. Web hiện hiển thị `question` như một tin nhắn thường nên không vỡ. Tuy vậy, client nào kiểm enum chặt sẽ cần cập nhật `api.gen.ts`.
- Test E2E của Web có thể phải thêm một lượt trả lời ngày.

## Thay đổi source sau khi chốt

- `src/shared/contracts/schemas/itinerary-agent.yaml`: thêm `startDate` vào enum `missingFields`; chạy `validate_contract.py`; sinh lại `src/frontend/src/types/api.gen.ts`.
- `src/backend/app/agents/steps/prompts.py`: cấm tự điền `startDate`; nhận biết câu trả lời "chưa biết / linh hoạt".
- `src/backend/app/agents/steps/classification.py`: `missing` thêm `startDate` khi chưa có và chưa hỏi lần nào; nhớ đã hỏi (cờ trong `constraints`, được lưu theo hội thoại).
- `src/backend/app/agents/steps/messages.py`, `steps/conversation.py`: câu hỏi ngày đi (vi/en).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/agent/langgraph-nodes.md`.
- `src/evaluation/datasets/itinerary_agent_golden.yaml`: sửa kỳ vọng các lượt bị ảnh hưởng, thêm case hỏi ngày và case "chưa biết ngày".
- Test unit cho `classify_result`; test E2E Web nếu cần.
