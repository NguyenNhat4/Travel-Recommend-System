# Merge release-mvp-v2 vào feat/fix-bug

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend | agent | docs

## Mục tiêu

Lấy code mới nhất của `origin/release-mvp-v2` (tới `85cea82`, 14 commit: vé máy bay trong lịch trình, lịch sử hội thoại của widget nối backend, HA/Patroni/crawler, trọng số RecSys) về nhánh `feat/fix-bug` đang có 5 commit riêng (tới `5d3e9be`).

## File thay đổi

Chỉ liệt kê file phải xử lý conflict bằng tay; các file còn lại git tự gộp hoặc lấy nguyên từ release.

- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: giữ ô "Nơi đi" + nút "Dùng vị trí hiện tại" của release, đổi lớp màu `blue-*` sang `ai-*`.
- `src/frontend/src/features/itinerary/widget/WidgetHistory.tsx` — sửa: giữ thông báo đăng nhập, trạng thái lỗi/đang tải lịch sử của release, đổi màu hội thoại đang chọn sang `ai-*`.
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — sửa: giữ `flightsBefore.map(renderFlight)` của release, viền timeline dùng `border-brand-200`.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: giá trị trả về bỏ cả `handleCheckoutPlan` lẫn `handleDeleteConversation`.

## Quyết định

- Merge (không rebase) vì 5 commit của nhánh đã được push lên `origin/feat/fix-bug`.
- Trong các đoạn conflict: lấy tính năng mới của release, giữ token màu của nhánh này (`ai-*` cho trợ lý, `brand-*` cho timeline) theo `history/2026-10-08-chatbot-agent-mau-xanh.md` và `history/2026-10-08-thang-mau-thuong-hieu-chung.md`. `ai-*` và `blue-*` hiện cùng giá trị màu nên giao diện không đổi.
- `useFloatingWidget`: nhánh này đã gỡ `handleCheckoutPlan`/`isCheckingOut` (trợ lý bỏ thanh toán gộp), release đã gỡ `handleDeleteConversation` (lịch sử lấy từ backend). Cả hai hàm đều không còn định nghĩa sau khi gộp nên bỏ cả hai khỏi giá trị trả về.

## Kiểm tra

- `.venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (117 schemas, 93 fixtures).
- `openapi-typescript` sinh lại so với `src/frontend/src/types/api.gen.ts`: trùng khớp.
- `node_modules/.bin/tsc --noEmit`: không lỗi.
- `node_modules/.bin/eslint` trên 4 file conflict: không lỗi.
- `node_modules/.bin/vitest run tests/unit`: 710/711 pass; `flightResultsView.test.tsx` có 1 test quá 5000ms khi chạy cả bộ, chạy riêng file đó thì 12/12 pass (merge không chạm file này).
- `.venv/bin/python -m pytest -q src/backend/tests -x`: pass (không bật `RUN_POSTGRES_INTEGRATION`).

## Còn lại / rủi ro

- Chưa chạy test tích hợp Postgres và chưa kiểm tra giao diện trên trình duyệt.
- `WidgetDays.tsx` dòng thẻ sản phẩm còn `ring-blue-500` đến từ release, ngoài đoạn conflict nên chưa đổi sang token của nhánh.
- Phần "gợi ý ở mọi ô tìm kiếm theo loại dịch vụ" đã bỏ khỏi working tree trước khi merge, đang nằm trong `git stash` (stash@{0}), không thuộc commit này.
