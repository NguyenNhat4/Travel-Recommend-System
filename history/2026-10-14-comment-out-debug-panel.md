# Comment toàn bộ DebugPanel

- Ngày: 2026-10-14
- Tác giả: Khoa15 / Claude Code
- Nhánh: khoa/lighthouse-staging-fixes
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Theo yêu cầu, comment hẳn `DebugPanel` để panel không còn được render ở bất kỳ trang nào. Bước trước đó chỉ xóa nút "DEBUG (Shift+D)" (commit `c191e44a`, PR #210), nay mở rộng thành toàn bộ panel.

## File thay đổi

- `src/frontend/src/components/common/DebugPanel.tsx` — sửa: bọc toàn bộ code trong block comment, thêm ghi chú đầu file cách khôi phục.
- `src/frontend/src/components/layout/AppShell.tsx` — sửa: comment import và `<DebugPanel />`.
- `src/frontend/tests/unit/debugPanelAssistant.test.tsx` — sửa: comment hai test cũ (chúng import `DebugPanel`), thay bằng `it.todo` để suite không lỗi.

## Quyết định

- Không xóa file, chỉ comment, để khôi phục nhanh khi cần.
- Giữ nguyên `TravelContext` (state `debugMode`, phím tắt Shift+D). Không còn UI nào đọc `debugMode` ngoài DebugPanel, nên phím tắt không còn tác dụng hiển thị. Gỡ hẳn state là thay đổi lớn hơn, để riêng nếu cần.
- Giữ nguyên `features/itinerary/widget/AssistantProgressDiagnostics.tsx`; hiện không còn ai import nó.
- Test cũ không xoá mà comment, kèm `it.todo`, để lần khôi phục sau biết cần viết lại test.

## Kiểm tra

- `npx eslint` trên `AppShell.tsx`, `DebugPanel.tsx`, `debugPanelAssistant.test.tsx`: pass.
- `npx tsc --noEmit`: pass.
- `npx vitest run tests/unit`: 80 file pass, 1 file todo; 872 test pass, 1 todo. Trước thay đổi: 874 test (hai test của DebugPanel đã comment).

## Còn lại / rủi ro

- Nội dung PR #210 đang mô tả "bỏ nút DEBUG"; cần cập nhật để ghi rõ toàn bộ panel đã comment.
- Chưa push commit này lên `origin/khoa/lighthouse-staging-fixes`.
