# Cập nhật slide và kịch bản thuyết trình agent theo graph 11 node

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu cập nhật `docs/spec/agent/presentation-slides.html` và `presentation-script.md` cho khớp code hiện tại: tách `classify`/`extract`, ngữ cảnh hội thoại chung cho mọi lượt gọi LLM, câu hỏi gộp ngày đi – số người – ngân sách, lưu hội thoại Redis + Postgres. Tiếp nối `2026-09-25-tach-classify-extract-hoi-chi-tiet-chuyen-di.md` (entry đó đã sửa slide 1, 5, 7, 9).

## File thay đổi

- `docs/spec/agent/presentation-slides.html` — sửa: slide 1 (ngày 25/09); slide 2 (AC-AGT-01 mới); slide 3 (LLM lập tool plan, ngữ cảnh chung); slide 4 (hội thoại Redis 24 giờ + Postgres lâu dài); slide 10 (năm lượt: hỏi điểm đến → hỏi gộp → trả lời ngắn → đổi điểm đến → bỏ khách sạn); slide 11–12 (ghi rõ số liệu 24/09 là trước khi tách `classify`/`extract`); slide 14 (bỏ ba việc đã làm: từ chối đặt chỗ, không tự suy ngày, lưu hội thoại bền; thêm chạy lại golden 14 case, đo latency, cửa sổ mở bán khách sạn).
- `docs/spec/agent/presentation-script.md` — sửa: ghi chú nguồn số liệu; lời nói slide 2, 3, 4, 10, 11, 12, 14; bảng demo trực tiếp theo luồng mới; câu hỏi dễ gặp về độ trễ, backend restart; thêm câu hỏi "Sao lại tách classify và extract?".

## Quyết định

- Không sửa số liệu golden ở slide 11–12: đó là kết quả thật của lần chạy 24/09; chỉ ghi rõ là trước khi đổi kiến trúc. Chạy golden mới thì thay.
- Slide 12 và kịch bản nói G-047 ("không từ chối đặt phòng") là lý do tách `classify`, nhưng ghi rõ chưa đo lại.

## Kiểm tra

- Chụp slide 2, 3, 4, 10, 14 bằng Playwright chromium headless (chặn Google Fonts để trang tải được): không slide nào tràn (`scrollHeight - clientHeight = 0`).
- Không có code thay đổi; không chạy test.

## Còn lại / rủi ro

- Slide 11–12 cần cập nhật sau khi chạy golden rút gọn.
