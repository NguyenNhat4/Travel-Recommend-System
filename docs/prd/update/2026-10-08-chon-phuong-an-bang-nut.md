# Chọn "Phương án khác" bằng một lần bấm, đổi lịch tức thì

- Ngày: 2026-10-08
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-05, FR-AGT-04, NFR-REL-01, AC-AGT-04

## Lý do

1. **Chậm.** Trace LangSmith ngày 08/10/2026 (hội thoại "di hcm 3 ngay 2 dem 2 vo chong 1 dua" → "di ngay 15"): một lượt
   lập lịch mất 16,5 s — phân luồng 1,7 s, trích ý định 2,9 s, lập tool plan 4,1 s, xếp lịch 0,01 s, viết lời 7,4 s.
   Nhắn "lấy phương án 1" hiện đi lại gần đủ chừng ấy bước (trích ý định, lập tool plan, tìm lại, viết lại toàn bộ lịch),
   dù lịch của phương án đã được tính xong ở lượt trước.
2. **Không giữ lời.** Vì tìm lại từ đầu, lịch nhận được có thể khác lịch đã báo: chênh tiền, chênh km trong mục "Phương án
   khác" không còn đúng.
3. **Khó dùng.** Người dùng phải gõ đúng câu "lấy phương án 1". Một nút bấm cạnh từng phương án nhanh và rõ hơn.

## Nội dung đề xuất

### `docs/prd/requirements.md` §3, AC-AGT-04

Hiện tại:

> Người dùng chọn phương án bằng lượt nhắn tiếp theo.

Thay bằng:

> Người dùng chọn phương án bằng một lần bấm vào phương án đó, hoặc nhắn "lấy phương án N" / tên khách sạn. Khi chọn đúng
> một phương án đã hiện, lịch đổi đúng như phương án đã báo (cùng khách sạn, cùng chênh tiền và chênh km), không tìm lại
> sản phẩm; câu trả lời chỉ nêu ngắn phần thay đổi, kèm các phương án còn lại, trong đó có lịch vừa bỏ để quay lại được.
> Mục tiêu thời gian phản hồi của lượt chọn: dưới 3 giây.

Phần còn lại của AC-AGT-04 giữ nguyên. Nhắn đổi khách sạn bằng câu khác (không phải chọn một phương án đã hiện) vẫn đi
luồng lập lịch thường.

### Grounding (FR-AGT-04, NFR-REL-01) không đổi

Lịch của từng phương án vẫn do luật tất định dựng ở lượt trước, từ đúng các sản phẩm Search/Recommendation đã trả về, và
đã qua kiểm tra như lịch chính. Lượt chọn chỉ lấy lịch đó ra; LLM chỉ viết lời ngắn, không thêm sản phẩm hay con số.

## Thay đổi source sau khi chốt

- Contract (thêm field, không phá v1): `src/shared/contracts/schemas/itinerary-agent.yaml`
  - response lịch trình có thêm `stayOptions` (khách sạn theo đêm, chênh tiền, chênh km, vượt ngân sách);
  - request có thêm `selectStayOption: {index}` (cần `conversationId`, không cần `message`), như `intentOverride`.
- Backend: `src/backend/app/domain/itinerary/routing.py`, `planning.py` (giữ lịch đã giải của từng phương án);
  `src/backend/app/agents/` — node mới `apply_option` (intake → apply_option → narrate → finalize), narrate chế độ ngắn,
  lưu lịch từng phương án vào hội thoại.
- Frontend: `src/frontend/src/features/itinerary/widget/` — thẻ phương án bấm được dưới câu trả lời, panel lịch cập nhật
  ngay khi chọn.
- Spec: `docs/spec/agent/langgraph-nodes.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Test: unit domain/agent, golden case cho lượt chọn phương án, vitest cho widget.
