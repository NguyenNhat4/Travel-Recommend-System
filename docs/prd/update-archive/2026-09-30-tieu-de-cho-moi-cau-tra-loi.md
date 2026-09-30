# Dòng tiêu đề in đậm cho các câu trả lời của trợ lý

- Ngày: 2026-09-30
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-30 ("oke code di")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01) — **không sửa câu chữ**, quy tắc ghi ở spec agent. Mở rộng đề xuất đã áp dụng `docs/prd/update-archive/2026-09-30-bao-loi-dau-vao-khong-hop-le.md` (đang chỉ áp dụng cho giá trị không hợp lệ).
- Mã FR/NFR: FR-AGT-01, FR-AGT-03

## Lý do

Câu báo giá trị không hợp lệ đã có dòng đầu in đậm tóm tắt phần chi tiết bên dưới. Người dùng muốn các câu trả lời khác của trợ lý cũng có dạng đó: dòng đầu là **bản tóm tắt** của cả câu, để đọc lướt là hiểu trợ lý đang nói gì.

## Nội dung đề xuất

Dạng chung: dòng đầu `**Tiêu đề**` (khoảng 3–8 từ, không dấu chấm cuối, cùng ngôn ngữ với câu trả lời), xuống dòng, rồi phần chi tiết. Tiêu đề **tóm tắt điều câu nói**, không phải lời kêu gọi hành động. Không thêm field mới: tiêu đề nằm trong chuỗi sẵn có (`question`, `message`, `error.message`).

**Danh sách trường hợp (các dòng "Có" là phạm vi mặc định; người đề xuất sẽ rà lại và chọn):**

| # | Trường hợp | Tiêu đề đề xuất (vi) | Ai viết | Mặc định |
|---|---|---|---|---|
| A1 | Thiếu cả điểm đến và số ngày | Cần biết điểm đến và số ngày | LLM (dự phòng cố định) | Có |
| A2 | Thiếu điểm đến | Bạn muốn đi đâu? | LLM (dự phòng cố định) | Có |
| A3 | Thiếu số ngày | Chuyến đi kéo dài mấy ngày? | LLM (dự phòng cố định) | Có |
| A4 | Hỏi gộp ngày đi, số người, ngân sách | Thêm vài chi tiết cho chuyến đi | LLM (dự phòng cố định) | Có |
| A5 | Hỏi lại lần hai, kèm form điền sẵn | Điền nhanh thông tin chuyến đi | LLM (dự phòng cố định) | Có |
| A6 | Thông tin mâu thuẫn (ngày và số ngày) | Thông tin chuyến đi chưa khớp nhau | LLM (dự phòng cố định) | Có |
| A7 | Điều kiện bắt buộc không xác minh được | Chưa xác minh được yêu cầu của bạn | LLM (dự phòng cố định) | Có |
| A8 | Điều kiện bắt buộc không có sản phẩm nào | Chưa có sản phẩm đáp ứng yêu cầu bắt buộc | Cố định | Có |
| A9 | Giá trị không hợp lệ | (đã áp dụng) | LLM | Đã xong |
| B1 | Chào hỏi, cảm ơn | Không có tiêu đề | — | Không |
| B2 | Ngoài phạm vi (ví dụ hỏi thời tiết) | Ngoài phạm vi hỗ trợ | LLM (dự phòng cố định) | Có |
| B3 | Đầu vào bị chặn bởi guardrail | Mình chưa thể hỗ trợ yêu cầu này | Cố định | Có |
| C1 | `NO_RESULTS`, không khớp sản phẩm nào | Chưa tìm thấy sản phẩm phù hợp | Cố định | Có |
| C2 | `NO_RESULTS`, do ngày đi ngoài thời gian mở bán | Chưa có sản phẩm mở bán cho ngày này | Cố định | Có |
| C3 | `FALLBACK`, chỉ có ứng viên tham khảo | Chưa dựng được lịch trình hoàn chỉnh | Cố định | Có |
| C4 | `COMPLETED` | Không có văn bản `message`; lịch trình đã có `title` riêng | — | Không áp dụng |
| D1 | Lỗi hệ thống khác (`LLM_UNAVAILABLE`, `SEARCH_UNAVAILABLE`, …) | — | — | Không (giao diện đã có khung lỗi riêng, và `error.message` dùng chung cho toàn API) |

Quy tắc kèm theo:

1. LLM viết `title` cùng phần chi tiết; backend ghép `**title**` + xuống dòng + chi tiết. LLM không đặt tiêu đề hoặc bị lỗi thì backend dùng tiêu đề cố định của trường hợp đó. Trường hợp câu cố định (A8, B3, C1–C3) thì tiêu đề nằm sẵn trong câu.
2. Tiêu đề không lọt vào ngữ cảnh gửi lại cho LLM (backend cắt dòng tiêu đề khỏi tin nhắn trợ lý cũ), để mô hình không bắt chước hay trả lời tiêu đề.
3. Chào hỏi/cảm ơn không có tiêu đề.
4. Giao diện: thẻ kết quả `NO_RESULTS`/`FALLBACK` tách tiêu đề thành tiêu đề thẻ; khung lỗi của widget hiển thị `**…**` thành chữ đậm (B2, B3 đến dưới dạng lỗi `VALIDATION_ERROR` 400).
5. Bộ golden có thêm khoá kiểm `titleFirstLine`: dòng đầu của câu trả lời phải là `**…**`.

## Ảnh hưởng và rủi ro

- **Chất lượng tiêu đề do LLM viết:** có thể quá chung chung hoặc không khớp phần chi tiết. Giảm thiểu bằng luật trong prompt (3–8 từ) và tiêu đề cố định làm dự phòng; chất lượng thật chỉ đánh giá được khi chạy golden với LLM thật.
- **Client khác đọc `error.message`** (app Streamlit, curl) sẽ thấy dấu `**` (B2, B3). Có thể chấp nhận vì không đổi hợp đồng dữ liệu.
- **Sửa câu chữ đã khoá:** các hằng câu cố định (`FALLBACK`, `REFUSAL`, `CLARIFY_*`, `no_results*`) và test/golden/spec nhắc chúng phải cập nhật.
- Không ảnh hưởng độ trễ; tăng nhẹ số token đầu ra của LLM.

## Thay đổi source sau khi chốt

- Backend `src/backend/app/agents/steps/`: `messages.py` (helper `titled`, `reply_title`, tiêu đề vi/en, sửa hằng câu cố định và `no_results*`), `conversation.py` (`conversational_update`, `clarification_fallback`), `prompts.py` (luật `title` cho mọi lý do hỏi lại), `history.py` (cắt dòng tiêu đề khỏi tin nhắn trợ lý cũ), `composition.py` (dùng câu có tiêu đề).
- Frontend: `components/assistant/AssistantResultPanel.tsx` (NO_RESULTS, FALLBACK), `features/itinerary/widget/WidgetChat.tsx` (khung lỗi), dùng `inlineBold.tsx` sẵn có.
- Contract: chỉ ghi chú mô tả `question`, `NO_RESULTS.message`, `FALLBACK.message`, `error.message` (`src/shared/contracts/schemas/`). Sinh lại `src/frontend/src/types/api.gen.ts`.
- Đánh giá: `src/evaluation/agent/golden.py` (khoá `titleFirstLine`), `src/evaluation/tests/test_golden.py`, `src/evaluation/datasets/itinerary_agent_golden.yaml` (đặt `titleFirstLine` ở mỗi nhóm).
- Test: `src/backend/tests/unit/agents/` (`test_classify.py`, `test_itinerary_runtime.py`, `test_guardrails.py`, `test_conversation_history.py`), `src/frontend/tests/unit/inlineBold.test.ts`.
- Spec: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3–§4.5, `docs/spec/agent/response-and-errors.md`, `langgraph-nodes.md`, `golden-dataset-how-to-add-more-case.md`, `docs/spec/hop-dong-tich-hop-frontend.md`.
