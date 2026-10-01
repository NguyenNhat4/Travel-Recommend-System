# Xoá ba đề xuất chờ chốt khỏi docs/prd/update

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu bỏ commit chuyển ba đề xuất sang `docs/prd/update-archive/` (`778054e`, đã revert bằng `5839000`) và xoá ba file đó.

## File thay đổi

- `docs/prd/update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` — xóa.
- `docs/prd/update/2026-09-29-vong-react-co-chan-cho-node-tool.md` — xóa.
- `docs/prd/update/2026-09-30-classify-chi-nhan-lich-su-va-message.md` — xóa.
- `history/2026-09-30-xoa-ba-de-xuat-cho-chot.md` — thêm.

## Quyết định

- Theo yêu cầu người dùng. Ba đề xuất đều `chờ chốt`, chưa áp dụng vào PRD; xoá nghĩa là không còn đề xuất nào đang chờ trong `docs/prd/update/`. Nội dung còn tra được trong git (`git show 5839000^:docs/prd/update/<tên file>` hoặc lịch sử commit `81a2c6b` cho đề xuất `classify`).
- Không sửa các entry history cũ; chúng vẫn nhắc tới ba đường dẫn này (`history/2026-09-30-de-xuat-classify-chi-nhan-lich-su-va-message.md`, `history/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md`, `history/2026-09-29-vong-react-co-chan-cho-node-tool.md`).

## Kiểm tra

- `docs/prd/update/` không còn file nào (`ls`).

## Còn lại / rủi ro

- Các entry history trên có thể ghi `dang dở` chờ chốt một đề xuất không còn tồn tại; người đọc sau cần biết đề xuất đã bị xoá theo entry này.
- Việc thu gọn ngữ cảnh `classify` (chỉ lịch sử + message mới nhất) mà bạn từng muốn không còn đề xuất nào theo dõi; payload `classify` vẫn mang `known_intent`, `previous_selection`. Làm lại thì cần đề xuất mới.
