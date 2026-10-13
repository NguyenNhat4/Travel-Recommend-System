# Đồng bộ AC-AGT-06 với nút mở form đã chốt ở AC-AGT-01

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-06
- Mã FR/NFR: FR-AGT-01, FR-AGT-06

## Lý do

AC-AGT-01 (chốt 12/10) ghi: người dùng đã đồng ý lời mời lập lịch mà còn thiếu điểm đến, số ngày, ngày đi hoặc số người thì câu trả lời kèm nút **Điền thông tin chuyến đi**; bấm mới mở form. AC-AGT-06 (bổ sung 11/10) vẫn ghi "vừa đồng ý bằng *"ok"* thì hỏi gộp một câu trước, chưa đưa form" và "câu "không biết", "tuỳ bạn" chỉ dẫn tới form sau khi người dùng đã đồng ý". Hai câu này viết khi form còn tự hiện; giờ đọc chung dễ hiểu là lượt "ok" không được có nút mở form.

Code hiện theo AC-AGT-01: lượt "ok" hỏi gộp một câu và kèm nút (`clarificationForm.autoOpen = false`); form chỉ tự mở khi người dùng xin form.

## Nội dung đề xuất

AC-AGT-06, đoạn **Đồng ý lập lịch**:

- Hiện tại: "vừa đồng ý bằng *"ok"* thì hỏi gộp một câu trước, chưa đưa form."
- Thay bằng: "vừa đồng ý bằng *"ok"* thì hỏi gộp một câu, kèm nút **Điền thông tin chuyến đi** theo AC-AGT-01; form chưa tự mở."

- Hiện tại: "Câu "không biết", "tuỳ bạn" chỉ dẫn tới form sau khi người dùng đã đồng ý lập lịch."
- Thay bằng: "Câu "không biết", "tuỳ bạn" chỉ kèm nút mở form sau khi người dùng đã đồng ý lập lịch."

## Thay đổi source sau khi chốt

Không cần sửa code; test `test_exploration.py::test_yes_after_the_offer_starts_planning_with_one_question_and_a_closed_form` đã kiểm hành vi này. Từ chối thì phải bỏ nút ở lượt "ok" trong `src/backend/app/agents/steps/conversation.py` (`_form_shown`) và sửa lại test.
