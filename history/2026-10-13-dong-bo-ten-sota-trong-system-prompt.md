# Đồng bộ tên Sota trong system prompt của agent

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người dùng xác nhận đã đổi tên V-OTA thành Sota và yêu cầu chỉnh system prompt. Hai prompt hiện ghi S-OTA, còn widget ghi Sota; thống nhất cách viết tên hiển thị.

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa: dòng giới thiệu trong PROMPT từ S-OTA sang Sota.
- `src/backend/app/agents/steps/prompts.py` — sửa: dòng giới thiệu trong ORCHESTRATOR_PROMPT từ S-OTA sang Sota.
- `history/2026-10-13-dong-bo-ten-sota-trong-system-prompt.md` — thêm: entry này.

## Quyết định

- Sota là cách viết tên hiển thị hiện dùng trong WidgetChat và được người dùng xác nhận trực tiếp. Chuẩn hóa tên của cùng thương hiệu, không đổi hành vi, FR/AC, tên kỹ thuật hay tên mã trong PRD.
- Không dùng skill. Giữ nguyên mọi chỉ dẫn và các thay đổi đang có trong hai file; không commit/push/deploy.
- Đọc history README và các đề xuất đổi tên hiển thị 09/10, logo Sota 12/10; đối chiếu trực tiếp prompt v1/v2 và widget. Tài liệu PRD/architecture/agent và lịch sử liên quan đã đọc trong cùng phiên trước sửa trước đó.

## Kiểm tra

- Duyệt AST hai file Python để xác nhận cú pháp và nội dung hằng prompt có Sota, không có V-OTA/S-OTA/X-OTA: PASS.
- Tìm tên cũ trong `src/backend/app/agents`, `src/backend/app/infrastructure/llm`: không còn kết quả.
- `git diff --check`: PASS. Không chạy lại eval/unit vì chỉ đổi tên hiển thị ở hai dòng.

## Còn lại / rủi ro

- Cần backend đang chạy nạp lại code mới để model nhận system prompt mới; chưa deploy hay kiểm model thật trong task này.
