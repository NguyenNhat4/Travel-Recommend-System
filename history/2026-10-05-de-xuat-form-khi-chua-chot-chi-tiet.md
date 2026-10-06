# Đề xuất đưa form gợi ý khi người dùng không trả lời được ngày đi, số người, ngân sách

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Bị thay thế bởi: 2026-10-05-form-khi-chua-chot-chi-tiet.md
- Phạm vi: docs, agent

## Mục tiêu

Người dùng gặp hội thoại "Đi Đà Nẵng → 3 ngày → không biết": agent lập lịch ngay thay vì hiện form gợi ý. Trace LangSmith (`nhat-10-1`, conversation `9841548a-089e-4fd7-9d12-129112ce3b4a`) cho thấy agent làm đúng AC-AGT-01 hiện hành: `extract` ra `decision=tool`, `missing_fields=[]` vì `start_date_asked=true` và form chỉ hiện khi thiếu điểm đến/số ngày. Muốn hiện form thì phải đổi AC-AGT-01, nên tạo đề xuất.

## File thay đổi

- `docs/prd/update/2026-10-05-form-khi-chua-chot-chi-tiet.md` — thêm: đề xuất, trạng thái chờ chốt.

## Quyết định

- Chọn hướng A (hiện form, chờ xác nhận) thay vì hướng B (lập lịch theo giả định kèm form chỉnh) theo lựa chọn của người dùng.
- Điều kiện hiện form là luật tất định (lượt này không thêm được trường nào), không nhờ LLM phân biệt "không biết" với "cứ lập lịch đi".
- Ghi rõ quan hệ với đề xuất đang chờ `2026-10-02-hoi-tiep-khi-cau-hoi-bi-cat-ngang.md` (cùng chạm AC-AGT-01).

## Kiểm tra

- Không chạy lệnh: chỉ thêm tài liệu đề xuất.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất; chưa sửa PRD, spec hay code.
- Cùng trace có lỗi riêng: `get_recommendations` trả `INVALID_TOOL_RESPONSE` ở cả hai lần gọi (<100ms), lần đầu `search_products` timeout cả 3 lời gọi. Lỗi này làm hỏng lịch trình kể cả khi đã có form; chưa điều tra.
