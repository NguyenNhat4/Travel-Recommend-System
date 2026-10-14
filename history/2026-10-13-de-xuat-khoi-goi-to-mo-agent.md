# Đề xuất khơi tò mò khi người dùng mất hứng

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng muốn agent có chút níu bằng gợi ý hay từ dữ liệu khi khách không muốn đi hoặc chưa biết gì, thay vì lời hẹn chung chung.

## File thay đổi

- `docs/prd/update/2026-10-13-khoi-goi-to-mo-khi-khach-mat-hung.md` — thêm: đổi quy tắc dừng thành phân biệt mất hứng với dừng rõ, chờ chốt.
- `history/2026-10-13-de-xuat-khoi-goi-to-mo-agent.md` — thêm: entry này.

## Quyết định

- Kiểm trực tiếp requirements AC-AGT-01, user-flow §4.2 và prompt orc_v2: quy tắc hiện tại cảm ơn/hẹn gặp lại và không thuyết phục có trong PRD, không phải kết luận model từ trace.
- Đề xuất một lần gợi ý mới có nguồn khi mất hứng, tôn trọng dừng rõ và giữ consent lập lịch riêng. Chưa sửa source của hành vi này theo AGENTS.md §8.
- Không dùng skill. Công việc cải thiện agent đã được cho phép trước đó không bị đề xuất này chặn.

## Kiểm tra

- Kiểm source và PRD trực tiếp; không chạy runtime/model cho đề xuất.
- Kiểm khoảng trắng và conflict marker trên tài liệu mới trước bàn giao.

## Còn lại / rủi ro

- Chờ người dùng chốt nội dung thay thế PRD; chưa được coi là hành vi đã triển khai.
