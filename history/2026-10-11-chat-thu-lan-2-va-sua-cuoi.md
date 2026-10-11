# Chat thử lần 2 (16 kiểu người dùng) và các sửa cuối: link thiếu "[", "hn", nút chỉ cho việc làm được

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: fix/chat-messy
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation

## Mục tiêu

Phần "Bàn giao" của `docs/plan/2026-10-10-chia-viec-sua-loi-chat-thu-16-kieu.md`:
- chạy lại cả 16 hội thoại;
- ghi báo cáo so với lần 1 (10/10).

Khi chạy, gặp 4 lỗi mới; sửa ngay rồi nhắn lại (FR-AGT-01, FR-AGT-06).

## File thay đổi

- `src/backend/app/agents/steps/exploration.py` — sửa: `_relinked` chèn lại "[" khi LLM bỏ dấu mở link ("Lăng Chủ tịch Hồ Chí Minh](product:…)", trace LangSmith xác nhận). Bước này chạy sau bước gỡ in đậm, để không ra "[[Tên]" khi LLM viết "[**Tên**](…)".
- `src/backend/app/agents/steps/prompts.py` — sửa:
  - `CLASSIFY_PROMPT`:
    - loại nơi ("biển", "núi", "chỗ mát") không phải `place`;
    - tên điểm đến trơn trả lời câu hỏi "đi đâu" là `travel`, không phải `explore` (M13 "hn");
  - `CONVERSATION_PROMPT`: không đòi người dùng gửi tên thành phố khi không kiểm được thông tin (câu thời tiết M14);
  - `EXTRACT_PROMPT`: thêm ví dụ viết tắt "2 ng" = 2 người, "2 lớn 1 nhỏ";
  - `EXPLORE_PROMPT`: nút chỉ cho việc trợ lý làm được, không thời tiết, tin tức, đặt chỗ hay thanh toán.
- `src/backend/app/agents/steps/conversation.py` — sửa: câu cố định "chưa tìm thấy <nơi>" chỉ dùng khi không hỏi chỗ ở (`explore_focus` ≠ `hotels`). Trước đây M07 "có ks nào gần biển không" ra "chưa tìm thấy biển…".
- `src/evaluation/reports/eval-2026-10-11-chat-thu-16-kieu-lan-2.md` — thêm: báo cáo lần 2, bảng trước/sau và toàn văn hội thoại.

## Quyết định

- Sửa link markdown hỏng là sửa cú pháp đầu ra LLM, không phải luật về ngôn ngữ. Chỉ chèn "[" khi đúng tên một thẻ đứng ngay trước "](product:".
- Các lỗi hiểu ý (M07, M13, M14) sửa ở prompt, không thêm luật.

## Kiểm tra

- Hội thoại thật: backend local `inprocess`, LLM thật. Toàn văn 16 hội thoại nằm trong báo cáo.
  - Lần 1: 4 tốt, 6 tạm, 6 lỗi.
  - Lần 2: 15 tốt, 1 tạm (M02), 0 lỗi.
- Nhắn lại sau sửa:

  | Ca | Kết quả |
  |---|---|
  | M03 "lăng bác mấy giờ mở cửa vậy" | link đúng, một thẻ |
  | M06 lượt 2 | "[Bao Chau Hotel]" đúng |
  | M07 | hỏi Đà Nẵng hay Nha Trang, có nút |
  | M10 "2 ng" | ghi 2 người |
  | M13 "hn" | "Còn thiếu số ngày" (2/2 lần) |
  | M14 | không còn câu đòi tên thành phố |

- `pytest src/backend/tests src/evaluation/tests/test_golden.py` (chạy một lần trước commit): 2845 passed, 36 skipped, 1 warning in 25.43s.

## Còn lại / rủi ro

- M02: sau hai lần chê, nên tự chọn một nơi và hiện thẻ.
- Nút "Thứ 7 tuần sau (24/10)" lệch với cách hiểu "thứ 7 tuần sau" vào Chủ nhật (17/10). Lỗi có từ trước.
- `classify` chạy ở nhiệt độ 1.
- Search trả 0 kết quả với "ko" và với "gần <nơi>" không kèm thành phố khi đã lọc thành phố. Cần báo team Search.
