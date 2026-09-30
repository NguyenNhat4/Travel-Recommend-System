# Chuyển ba đề xuất chờ chốt sang docs/prd/update-archive

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu chuyển các file trong `docs/prd/update/` sang `docs/prd/update-archive/`.

## File thay đổi

- `docs/prd/update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` → `docs/prd/update-archive/` — đổi chỗ, nội dung giữ nguyên, trạng thái vẫn `chờ chốt`.
- `docs/prd/update/2026-09-29-vong-react-co-chan-cho-node-tool.md` → `docs/prd/update-archive/` — như trên.
- `docs/prd/update/2026-09-30-classify-chi-nhan-lich-su-va-message.md` → `docs/prd/update-archive/` — như trên.
- `history/2026-09-30-chuyen-de-xuat-sang-update-archive.md` — thêm.

## Quyết định

- Theo yêu cầu người dùng; không đổi trạng thái vì agent không tự chốt hay từ chối đề xuất (AGENTS.md §8).
- Các entry history cũ vẫn trỏ tới đường dẫn `docs/prd/update/...` (không sửa entry cũ).

## Kiểm tra

- `docs/prd/update/` không còn file nào; `git status` sạch sau commit.

## Còn lại / rủi ro

- AGENTS.md §1.1 bảo agent không cần đọc `docs/prd/update-archive/` vì coi nội dung ở đó đã nằm trong PRD. Ba đề xuất này chưa được áp dụng vào PRD, nên agent sau sẽ không thấy chúng và có thể bỏ qua hoặc làm trái. Muốn làm tiếp các đề xuất này thì chuyển lại `docs/prd/update/` hoặc đổi trạng thái (`đã chốt`/`từ chối`) trước.
