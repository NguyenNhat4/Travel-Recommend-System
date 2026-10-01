# Đề xuất hỏi lại khi ngày khởi hành đã qua

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng nêu ngày khởi hành đã qua (ví dụ "từ hôm qua") thì agent vẫn gọi tool và trả `NO_RESULTS` sai lý do. Cần hỏi lại ngày thay vì lập lịch.

## File thay đổi

- `docs/prd/update-archive/2026-09-30-hoi-lai-khi-ngay-di-da-qua.md` — thêm: đề xuất (tạo ở `docs/prd/update/`, đã chốt và chuyển sang archive cùng ngày) hỏi lại qua `clarify` (LLM viết câu) khi `startDate` < hôm nay, áp dụng cho chat, chip và ngày đã lưu.

## Quyết định

- Người dùng chọn hành vi "hỏi lại ngày" (`NEEDS_CLARIFICATION`, `missingFields` có `startDate`), không trả lỗi 400.
- Câu hỏi lại do LLM viết qua node `clarify` (người dùng yêu cầu, không dùng câu cố định); backend đưa sẵn hai ngày dd/mm/yyyy vào payload, câu cố định chỉ là dự phòng khi LLM lỗi.
- Người dùng yêu cầu không sửa `docs/prd/requirements.md`; quy tắc ghi ở spec agent. AC-AGT-01 đã có chuẩn "ngày khởi hành không trước ngày hôm nay" cho form.
- Theo AGENTS.md §8: dừng ở đề xuất cho tới khi người dùng chốt (2026-09-30). Phần áp dụng ghi ở `history/2026-09-30-hoi-lai-khi-ngay-di-da-qua.md`.

## Kiểm tra

- Không có (chỉ thêm tài liệu).

## Còn lại / rủi ro

- Không có; xem entry áp dụng.
