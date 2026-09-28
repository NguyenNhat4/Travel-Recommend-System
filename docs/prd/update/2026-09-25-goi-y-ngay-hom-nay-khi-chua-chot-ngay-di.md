# Gợi ý ngày hôm nay khi người dùng chưa chốt ngày đi

- Ngày: 2026-09-25
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01)
- Mã FR/NFR: FR-AGT-01, FR-AGT-03

## Lý do

Đề xuất `update-archive/2026-09-25-hoi-ngay-di-truoc-khi-lap-lich.md` (đã áp dụng) quy định: người dùng trả lời "chưa chốt ngày" thì trợ lý lập lịch **không kèm ngày** (`startDate = null`). Người dùng muốn đổi: nếu không có ngày đi thì trợ lý **gợi ý lấy hôm nay làm ngày khởi hành** và nêu rõ ngày đó, thay vì lập lịch không kèm ngày.

Khác với lỗi cũ (LLM tự điền ngày hôm nay mà người dùng không hay biết), ở đây việc lấy hôm nay là do trợ lý nói ra công khai và người dùng có cơ hội đổi.

## Quyết định người dùng đã đưa ra

| Câu hỏi | Chọn |
|---|---|
| Người dùng nói "chưa chốt ngày đi" thì trợ lý làm gì? | Gợi ý hôm nay và chờ xác nhận. |
| Sau gợi ý, người dùng không xác nhận và cũng không nói ngày nào? | Lấy hôm nay luôn, không hỏi lại. |

## Nội dung đề xuất

**`docs/prd/requirements.md` §3, AC-AGT-01, cột "Hành vi kỳ vọng"**

- Hiện tại: "Trợ lý hỏi ngày đi (một lần, không tự đoán ngày). Người dùng trả lời một ngày cụ thể hoặc trả lời chưa chốt ngày; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; các địa điểm nghỉ ngơi và hoạt động đều là thẻ sản phẩm thật kèm giá rõ ràng và nút bấm xem chi tiết. Câu đầu đã có ngày đi thì xuất lịch ngay."
- Thay bằng: "Trợ lý hỏi ngày đi (không tự đoán ngày). Người dùng nói một ngày cụ thể thì lập lịch với ngày đó. Người dùng chưa chốt ngày hoặc không nói ngày thì trợ lý gợi ý khởi hành hôm nay, nêu rõ ngày, và chờ xác nhận; sau gợi ý, dù người dùng xác nhận, không xác nhận hay không nói ngày, trợ lý lấy ngày hôm nay và xuất ra lịch trình 3 ngày có cấu trúc; các địa điểm nghỉ ngơi và hoạt động đều là thẻ sản phẩm thật kèm giá rõ ràng và nút bấm xem chi tiết. Người dùng nêu một ngày khác ở bất kỳ lượt nào thì dùng ngày đó. Câu đầu đã có ngày đi thì xuất lịch ngay."

Quy tắc hành vi đi kèm, ghi ở spec:

- Mỗi hội thoại có tối đa **hai** lượt hỏi về ngày: lượt 1 hỏi ngày; lượt 2 gợi ý hôm nay (chỉ khi lượt 1 chưa có ngày). Sau đó không hỏi nữa, không kẹt vòng hỏi.
- Người dùng nói chưa chốt ngày ngay ở câu đầu thì bỏ qua lượt 1, vào thẳng lượt gợi ý.
- Câu gợi ý dùng **câu cố định** (vi/en) có nêu ngày hôm nay theo giờ Việt Nam, không để LLM viết, để ngày luôn đúng.
- Lượt gợi ý vẫn trả `NEEDS_CLARIFICATION` với `missingFields = ["startDate"]` và chưa gọi tool. Contract không đổi.
- Yêu cầu chỉ có `intentOverride` (chip sửa tay) không bị hỏi ngày, như hiện nay.

## Ảnh hưởng và rủi ro

- **Ngày hôm nay có thể nằm ngoài cửa sổ mở bán của sản phẩm.** Hiện khách sạn Hà Nội trong catalog chỉ mở bán 15–16/10; với ngày đi hôm nay, khách sạn bị loại vì sai ngày và lịch dễ ra `FALLBACK`. Đây chính là nguyên nhân lượt "1 ngày thôi" ra FALLBACK. Đề xuất này không sửa dữ liệu; cần team Data đưa cửa sổ mở bán về 30 ngày từ ngày nạp (AGENTS.md mục 6.2) thì hành vi mới mới cho ra lịch đầy đủ.
- **Thêm lượt hỏi đáp:** người dùng không nêu ngày phải qua tối đa hai lượt (hỏi, gợi ý) trước khi có lịch.
- **Đảo một quy tắc vừa áp dụng** (chưa chốt ngày → lập lịch không kèm ngày). Slide, kịch bản và golden đã cập nhật theo quy tắc cũ phải sửa lại.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/state.py`, `nodes.py` (`intake`, `finalize`): đổi cờ `start_date_asked` (bool) thành `start_date_prompts` (số lần đã hỏi về ngày: 0, 1, 2), lưu theo hội thoại.
- `src/backend/app/agents/steps/classification.py`: chưa có ngày và `start_date_prompts` = 0 → hỏi ngày (=1); = 1 → gợi ý hôm nay (=2, `clarification_reason = "start_date_suggestion"`); ≥ 2 → `startDate` = `vietnam_today()` rồi đi tiếp tới `tool`. `start_date_undecided` ở lượt đầu đi thẳng vào gợi ý.
- `src/backend/app/agents/steps/messages.py`, `conversation.py`, `nodes.py` (`clarify` sync/async): câu gợi ý cố định vi/en có ngày; bỏ qua LLM cho lý do này.
- `src/backend/app/agents/steps/prompts.py`: chỉnh mô tả `start_date_undecided`.
- Test unit cho `classify` (ba nấc), test qua graph (hỏi → gợi ý → lập lịch với ngày hôm nay; hỏi → nêu ngày → lập lịch với ngày đó).
- `src/evaluation/datasets/itinerary_agent_golden.yaml`: 6 case có lượt hỏi ngày (G-057, G-059, G-062, G-071, G-072, G-073): lượt "chưa chốt ngày đi" kỳ vọng `NEEDS_CLARIFICATION` gợi ý hôm nay và chưa gọi tool; thêm lượt "đồng ý" mang kỳ vọng kết quả gốc và kiểm `intent.startDate: "{today:iso}"`; đánh số lại `excludeProductsFromTurn`. Có thể thêm khoá `expect` `textInclude` để kiểm câu gợi ý nêu đúng ngày hôm nay.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3, `docs/spec/agent/state-fields.md`, `langgraph-nodes.md`, `golden-dataset-how-to-add-more-case.md`, `presentation-script.md` (nếu nhắc): cập nhật quy tắc.
