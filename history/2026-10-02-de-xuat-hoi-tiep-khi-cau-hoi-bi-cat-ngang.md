# Đề xuất hỏi tiếp khi câu hỏi chi tiết bị cắt ngang

- Ngày: 2026-10-02
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: agent, docs

## Mục tiêu

Tái hiện TC-04 (`src/evaluation/agent/agent-test-cases-nhat.md`) trên LangSmith `nhat-10-1`, run `01a0fba2-32b3-7ca3-b81e-b71101762192`. Chuỗi "đi hà nội 3 ngày" → "đổi điểm đi" → "không đổi nữa" ra lịch Hà Nội ngay, không hỏi ngày đi và không xác nhận giữ Hà Nội. Phục vụ FR-AGT-01, FR-AGT-05.

## File thay đổi

- `docs/prd/update/2026-10-02-hoi-tiep-khi-cau-hoi-bi-cat-ngang.md` — thêm: đề xuất, trạng thái `chờ chốt`.

## Quyết định

- Nguyên nhân nằm ở code, không ở LLM. `extract` trả `patch: {}` và `change_without_value: []` cho "không đổi nữa", tức là đúng. Nhưng `start_date_asked` đã bật từ lượt hỏi chi tiết T1 dù người dùng chưa trả lời, nên `extract_result` ra `decision: tool`. State cũng không lưu lượt trước hỏi gì, nên code không phân biệt được câu rút lại yêu cầu đổi với một câu "ok".
- Sửa cần lệch chữ AC-AGT-01 ("hỏi một lần"). Đây cũng là thêm hành vi mà PRD chưa có: xác nhận khi rút lại yêu cầu đổi. Vì vậy tạo đề xuất và dừng, chưa sửa code (AGENTS.md mục 8).
- Đề xuất đảo quyết định "rút lại thì lập lịch nếu đã hỏi" trong `history/2026-10-01-khong-hoi-lai-khi-rut-lai-yeu-cau-doi.md`.

## Kiểm tra

- Chỉ thêm tài liệu, không chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt. Sau khi chốt: cập nhật AC-AGT-01, rồi sửa code, test và golden theo mục "Thay đổi source sau khi chốt" của đề xuất.
