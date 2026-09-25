# Slide agent: slide 7 chỉ giữ bốn đường chính

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng muốn slide 7 ("Bảy câu nhập, bảy đường đi") chỉ còn các route chính. Tiếp nối `2026-09-24-slide-thuyet-trinh-agent.md`.

## File thay đổi

- `docs/spec/agent/presentation-slides.html` — sửa: slide 7 còn bốn đường `converse`, `clarify`, `compose`, `dead_letter`; bỏ ba dòng biến thể (câu chưa nêu gì, điều kiện 5 sao, retry).
- `docs/spec/agent/presentation-script.md` — sửa: lời nói slide 7 theo bốn đường.

## Quyết định

- Chọn một đường cho mỗi node soạn trả lời, vì đó là bốn kiểu response người dùng nhận được (`docs/spec/agent/langgraph-nodes.md` §1). Retry vẫn có trên sơ đồ ở slide 5.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy test.

## Còn lại / rủi ro

- Không có.
