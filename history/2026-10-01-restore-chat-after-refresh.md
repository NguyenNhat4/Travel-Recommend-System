# Khôi phục hội thoại của người dùng sau khi tải lại trang

- Ngày: 2026-10-01
- Tác giả: người yêu cầu / Codex
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Sửa chat biến mất khi refresh: khôi phục transcript và response gần nhất của người dùng đã đăng nhập từ archive backend, phục vụ FR-AGT-01 và hỗ trợ hội thoại đa lượt của AC-AGT-01.

## File thay đổi

- `src/frontend/src/context/AssistantProvider.tsx` — sửa: chờ authReady, nạp archive của ID đã lưu, so sánh user ID khi đổi tài khoản, bỏ response lịch sử đến muộn; giữ mã lỗi API và hỗ trợ thử nạp lại khi lỗi tạm thời.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — sửa: kiểm soát trạng thái phiên trong test; thêm regression cho refresh, auth loading, StrictMode, structured itinerary, reset/gửi tin/đổi tài khoản/unmount khi history đang tải, archive 404 và retry.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa §9.6: mô tả khôi phục hội thoại sau refresh.
- `history/2026-10-01-restore-chat-after-refresh.md` — thêm: entry này.

## Quyết định

- Nguyên nhân: provider chỉ hydrate ID, không nạp messages. Khi auth khôi phục từ null sang người dùng, effect cũ còn coi đó là đổi persona và reset chat.
- Chờ phiên ban đầu hoàn tất rồi hydrate và gọi service history hiện có. Backend/Postgres vẫn là nguồn dữ liệu; sessionStorage chỉ chứa ID. Không đổi API, DDL, PRD hoặc dùng skill.
- So sánh `currentPersona.id` thay vì `code`: hai tài khoản cùng code vẫn phải được cách ly. Account switch/reset/request mới/unmount làm vô hiệu các response archive đang bay.
- Hội thoại không còn tồn tại thì xóa ID; lỗi tạm thời giữ ID, hiển thị lỗi và cho thử tải lại. Khách giữ cơ chế ngữ cảnh tạm thời, không đọc archive lâu dài.
- Hiện thực PRD architecture §3 và FR-AGT-01 hiện hành; không lệch PRD. Quyết định ID-only reload trong `2026-09-21-assistant-backend-frontend.md` được bổ sung bằng archive đã triển khai theo `2026-09-25-luu-hoi-thoai-redis-postgres.md`.
- Spec UX cũ có nội dung không duy trì lịch sử và không stream; PRD và contract hiện hành thắng. Không mở rộng sửa các tồn đọng đó trong task này.

## Kiểm tra

- `cd src/frontend && node_modules/.bin/vitest run`: 49 files, 498 tests PASS trước khi thêm test structured itinerary cuối cùng.
- `cd src/frontend && node_modules/.bin/vitest run tests/unit/assistantProvider.test.tsx`: 18 tests PASS với test structured itinerary cuối cùng.
- `cd src/frontend && node_modules/.bin/eslint src/context/AssistantProvider.tsx tests/unit/assistantProvider.test.tsx`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (102 schemas, 70 fixtures; CDP clone 12 schemas, 7 fixtures).
- `git diff --check`: PASS.
- `cd src/frontend && node_modules/.bin/tsc --noEmit`: FAIL, exit 2; ba lỗi TS2307 trong `.next/types` tham chiếu trang `/assistant` đã bị xóa, không có lỗi tại source/test đã sửa.

## Còn lại / rủi ro

- Chưa kiểm tra trên browser với phiên đăng nhập và backend/Postgres thật; kết quả runtime phụ thuộc archive backend đang hoạt động và các lượt chat đã được lưu thành công.
- Không khôi phục transcript lâu dài cho khách theo FR-AGT-01. Không deploy hoặc commit.
