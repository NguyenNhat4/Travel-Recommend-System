# Đề xuất: hỏi lại khi người dùng muốn đổi mà chưa nói đổi thành gì

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Bị thay thế bởi: 2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md
- Phạm vi: docs

## Mục tiêu

Sau khi đã có lịch, "đổi ngày" / "đổi địa điểm" không kèm giá trị mới làm agent lập lại lịch cũ và trả "Lịch trình đã
được hoàn tất.". Người dùng yêu cầu: trường hợp này đi qua node `clarify` và hỏi lại; việc nhận ra do LLM hiểu, không
dùng luật tất định. Hành vi mới so với `docs/prd/architecture.md` §3 nên tạo đề xuất trước (AGENTS.md §8).

## File thay đổi

- `docs/prd/update/2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-09-30-de-xuat-hoi-lai-khi-doi-ma-chua-noi-cu-the.md` — thêm.

## Quyết định

- Thay cho hướng "backend so intent cũ/mới" đã bàn trước: LLM ở `extract` điền `change_without_value`, backend làm
  theo. Không thêm node, không thêm lượt gọi LLM.
- Phạm vi hẹp: chỉ năm trường của intent. "không đi nữa", "ngày nào cũng được", "gợi ý lịch khác" để ngoài.
- Contract không đổi.

## Kiểm tra

- Chưa có thay đổi code nên chưa chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất; chốt xong mới sửa PRD và source theo mục "Thay đổi source sau khi chốt".
- LLM không tất định: đo bằng golden G-079 chạy lặp trước khi merge.
