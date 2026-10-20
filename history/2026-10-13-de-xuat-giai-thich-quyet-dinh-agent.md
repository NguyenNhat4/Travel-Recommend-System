# Đề xuất agent giải thích quyết định trong tiến trình

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng muốn thấy agent hiểu và quyết định gì, vì tiến trình tìm thêm tại TP. Hồ Chí Minh giống câu cố định.

## File thay đổi

- `docs/prd/update/2026-10-13-giai-thich-quyet-dinh-agent-trong-tien-trinh.md` — thêm: đề xuất lời giải thích công khai do agent viết theo vòng quyết định, chờ chốt.
- `history/2026-10-13-de-xuat-giai-thich-quyet-dinh-agent.md` — thêm: entry này.

## Quyết định

- Đối chiếu `widgetProgressLabels.ts`, `widgetProgressView.ts`, `steps/progress.py`, `orc_v2.py`, `widgetV2.ts` và contract v2: câu người dùng gửi là câu mẫu; số đếm do code. Không có bằng chứng runtime mới trong lượt này.
- Đọc PRD README, các đoạn tiến trình trong architecture §3, user-flow §4.2, requirements AC-AGT-09; đề xuất tiến trình 12/10 và plan tương ứng; history README, các entry mới nhất và lịch sử triển khai tiến trình/lượt chat. Lịch sử v2 xác nhận đang chuyển phiên bản, v1 vẫn là mặc định widget tại thời điểm ghi entry đó; chưa kiểm cấu hình chạy của người dùng.
- PRD hiện chỉ cho phép mã/số an toàn trên SSE. Theo AGENTS.md §8, tạo đề xuất và dừng thay đổi source tới khi người dùng chốt. Không tự coi yêu cầu chung là đã chốt đoạn PRD thay thế.
- Không dùng skill. Không thay PRD, code, contract; không commit/push/deploy.

## Kiểm tra

- Tìm trực tiếp câu người dùng gửi: có trong hai file frontend nêu trên.
- `git status --short` trước thay đổi: sạch.
- `git diff --check`: PASS cho diff tracked; hai file mới được kiểm riêng khoảng trắng cuối dòng và dấu conflict, PASS.
- Chưa chạy test code vì chỉ thêm đề xuất và lịch sử.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất; sau đó đọc đủ tài liệu theo phạm vi, cập nhật PRD trước, contract trước code.
- Lời giải thích công khai là bản giải thích quyết định, không chứng minh toàn bộ suy luận nội bộ model. Không tạo transcript giả cho lượt người dùng đã gửi.
