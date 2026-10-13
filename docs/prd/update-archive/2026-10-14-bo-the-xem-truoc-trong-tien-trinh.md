# Bỏ thẻ xem trước trong khung tiến trình trợ lý

- Ngày: 2026-10-14
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-14 (chat: "bỏ nhanh vào luôn")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-09; `docs/prd/user-flow.md` §4 (Khung tiến trình);
  `docs/prd/architecture.md` §3 (Grounding, guardrail và commit hội thoại)
- Mã FR/NFR: AC-AGT-09 (phục vụ FR-AGT-01, FR-AGT-06)

## Lý do

Thẻ xem trước được chốt ngày 13/10 (phần C của `update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md`). Khi lượt lập lịch
quá 5 giây và lịch đã xếp xong, widget hiện khối "Đã chọn xong, đang viết lời tư vấn" gồm thẻ các sản phẩm của lịch.

Dùng thật trên web local (lượt 14/10 00:13, Đà Nẵng 3 ngày), người dùng thấy khối này giống lỗi:

- Lưới 2 cột × 3 dòng, không ảnh, không chia theo ngày, trông như danh sách rời trước câu trả lời.
- Chỉ hiện tối đa 6 thẻ: lịch 7 sản phẩm thì mất khách sạn ở cuối.
- Khoảng 6 giây sau, cùng các thẻ đó hiện lại trong câu trả lời.
- Chữ "Đã chọn xong" nhưng orc vẫn có thể sửa lịch sau đó.

Người dùng quyết định bỏ hẳn (chat 14/10: "Bỏ hẳn đi"), không sửa thành lịch nháp.

## Nội dung đề xuất

### `docs/prd/requirements.md` §3, AC-AGT-09

Bỏ câu:

> Preview chỉ xuất hiện sau refs đã được orc chọn và kiểm, chỉ xem, không đặt/chọn, không commit shown/lịch.

Thay bằng:

> Trong lúc chờ không hiện thẻ sản phẩm; thẻ chỉ có trong câu trả lời.

### `docs/prd/user-flow.md` §4, đoạn "Khung tiến trình"

Bỏ câu:

> Preview chỉ refs orc đã chọn và kiểm, chỉ xem, không đặt/chọn và không commit shown/lịch.

Thay bằng:

> Khung tiến trình không hiện thẻ sản phẩm trước câu trả lời.

### `docs/prd/architecture.md` §3, Grounding, guardrail và commit hội thoại

- Bỏ dòng "Preview chỉ refs đã chọn/kiểm, không có hành động đặt/chọn, không ghi shown hay committed plan."
- Dòng "Preview và tool thử lịch không commit." đổi thành "Tool thử lịch không commit."

### Không đổi

- "Xem trước phương án" (thẻ phương án khác có `itinerary` để xem trước khi chọn, `user-flow.md` sơ đồ §2) giữ nguyên;
  đó là nội dung của câu trả lời, không phải khối trong lúc chờ.
- Think → Act → Observe, số đếm, đồng hồ chậm của khung tiến trình giữ nguyên.

## Thay đổi source sau khi chốt

- Backend thôi phát sự kiện: v2 `preview` (`src/backend/app/agents/orc_v2.py`), v1 `run.preview`
  (`src/backend/app/agents/steps/progress.py`, `src/backend/app/api/v1/routes/assistant.py`); test liên quan.
- Contract: giữ schema `EventPreview` (v2) và `AssistantRunPreview`/`run.preview` (v1) để không phá client cũ, ghi
  mô tả "server không còn phát"; chạy `validate_contract.py`.
- Frontend: xoá `WidgetProgressPreview.tsx`, state `preview`/`previewVisible` và hẹn giờ 5 giây trong
  `assistantState.ts`, `AssistantProvider.tsx`, `WidgetChat.tsx`, `assistantStream.ts`; sửa test.
- Spec: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`,
  `docs/spec/product.md`, `docs/spec/agent/working-context.md` bỏ phần preview.
