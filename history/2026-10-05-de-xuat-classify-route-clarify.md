# Đề xuất: classify route thẳng sang clarify

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Bị thay thế bởi: 2026-10-05-form-den-khi-du-truong-bat-buoc.md

## Mục tiêu

Baseline TC-10 qua giao diện eval (05/10) fail đúng như dự kiến: lượt "không biết" ra `COMPLETED`, tool chạy, thiếu node `clarify`, không có `clarificationForm`. Người dùng yêu cầu sửa prompt `classify` để route sang `clarify`. Việc này đổi sơ đồ graph ở `docs/prd/architecture.md` §3, nên cần đề xuất trước.

## File thay đổi

- `docs/prd/update/2026-10-05-classify-route-clarify.md` — thêm: đề xuất nhãn `vague` ở `classify`, cạnh `classify → clarify`, chờ chốt.

## Quyết định

- Giữ hành vi của đề xuất đã chốt `2026-10-05-form-khi-chua-chot-chi-tiet.md` (hiện form, mỗi hội thoại một lần), chỉ đổi chỗ quyết định từ `extract_result` sang `classify`.
- Khách sạn, hoạt động được tính khi xét câu có thêm thông tin hay không, nhưng không vào `missing_fields` vì form không có ô cho chúng.

## Kiểm tra

- Baseline TC-10 (người dùng chạy qua `make agent-eval`): lượt 2 fail với `status='COMPLETED'`, `missingFields` thiếu `startDate`/`party`/`budget`, `tool có chạy`, `thiếu node 'clarify'`, `không có clarificationForm`.
- Chưa sửa code.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất, rồi cập nhật `architecture.md` §3 trước và sửa source theo mục "Thay đổi source sau khi chốt".
