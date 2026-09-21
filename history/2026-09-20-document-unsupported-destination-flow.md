# Ghi tài liệu status/error.code và luồng UNSUPPORTED_DESTINATION

- Ngày: 2026-09-20
- Tác giả: người dùng / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, evaluation

## Mục tiêu

Người đọc dễ nhầm `UNSUPPORTED_DESTINATION` là một `status`. Cần ghi rõ khác biệt giữa `status` (HTTP 200) và `error.code`, khi nào có mã này và luồng tiếp tục hội thoại sau đó.

## File thay đổi

- `src/evaluation/agent/README.md` — sửa: thêm mục "`status` và `error.code`" gồm bảng hai nhóm response, dạng `UNSUPPORTED_DESTINATION`, luồng hai lượt và các lưu ý cho client.
- `history/2026-09-20-document-unsupported-destination-flow.md` — thêm: entry này.

## Quyết định

- Đặt trong README của agent (nơi đã mô tả 9 node và các luồng) thay vì tạo file mới. Nội dung bám hành vi đã ghi trong `history/2026-09-20-resume-after-unsupported-destination.md`.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy test. `git diff --check`: pass.

## Còn lại / rủi ro

- Danh sách `error.code` trong bảng lấy từ `common.yaml` và `nodes.py`; cần cập nhật khi thêm mã lỗi mới.
