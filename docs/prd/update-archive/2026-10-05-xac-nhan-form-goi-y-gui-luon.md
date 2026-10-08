# Bấm "Xác nhận" ở form gợi ý thì gửi luôn

- Ngày: 2026-10-05
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-05
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01), `docs/prd/architecture.md` §3 (sơ đồ, cạnh `SuggestForm --> [*]`), `docs/prd/user-flow.md` (đoạn "Form gợi ý thông tin chuyến đi", dòng 181)
- Mã FR/NFR: FR-AGT-01, FR-AGT-03, FR-AGT-05

## Lý do

Đề xuất đã chốt 2026-09-29 (`update-archive/2026-09-29-form-goi-y-thong-tin-chuyen-di.md`) quy định bấm Xác nhận chỉ **đặt câu yêu cầu vào ô nhập, không tự gửi**. Người dùng muốn bỏ bước đó: người dùng vừa chọn xong điểm đến, số ngày, ngày đi, số người, ngân sách trên form, nên thêm một lần bấm gửi nữa là thừa.

## Nội dung đề xuất

`docs/prd/user-flow.md` (dòng 181):

- Hiện tại: "Bấm xác nhận đặt câu yêu cầu hoàn chỉnh vào ô nhập tin nhắn để người dùng sửa hoặc gửi."
- Đề xuất: "Bấm xác nhận gửi ngay câu yêu cầu hoàn chỉnh dựng từ form như một tin nhắn của người dùng; trợ lý coi đó là yêu cầu đầy đủ và lập lịch, không hỏi thêm."

`docs/prd/requirements.md` AC-AGT-01, câu cuối:

- Hiện tại: "Người dùng bấm xác nhận thì câu yêu cầu hoàn chỉnh được đặt sẵn vào ô nhập tin nhắn để họ sửa hoặc gửi ngay; gửi đi thì trợ lý coi đó là một yêu cầu đầy đủ và lập lịch, không hỏi thêm."
- Đề xuất: "Người dùng bấm xác nhận thì câu yêu cầu hoàn chỉnh được gửi ngay; trợ lý coi đó là một yêu cầu đầy đủ và lập lịch, không hỏi thêm."

`docs/prd/architecture.md` §3: `SuggestForm --> [*]: Form đã điền sẵn gợi ý; xác nhận gửi ngay câu yêu cầu` (thay "đổ câu yêu cầu vào ô nhập").

Đánh đổi: người dùng không còn xem lại hoặc sửa câu trước khi gửi. Giá trị vẫn sửa được ngay trên form trước khi bấm Xác nhận, và form chặn giá trị không hợp lệ (số ngày 1–7, ngày đi không trước hôm nay), nên rủi ro gửi sai thấp. Không đổi contract, backend hay agent.

## Thay đổi source sau khi chốt

- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — `handleConfirmTripDetails` gửi thẳng `prompt` qua đường gửi tin nhắn hiện có thay vì `setInputVal(prompt)`; bỏ qua nếu `isRunning`.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — không đổi hành vi; chỉ cân nhắc đổi nhãn nút nếu cần.
- Cập nhật `docs/prd/user-flow.md`, `docs/prd/requirements.md`, `docs/prd/architecture.md` như trên **trước** khi sửa code; kiểm tra `docs/spec/hop-dong-tich-hop-frontend.md` xem có mô tả hành vi cũ không.
