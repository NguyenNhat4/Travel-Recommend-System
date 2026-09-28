# Gộp release-mvp-v1 (lần 2, PR #30 feat/booking) vào feat/agent

- Ngày: 2026-09-25
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng yêu cầu merge code `release-mvp-v1` vào `feat/agent`. `origin/release-mvp-v1` (commit `8ce8ca6`) có thêm
5 commit so với lần merge trước: PR #30 `feat/booking` (widget trợ lý thêm giỏ hàng tuần tự và thanh toán, backend
catalog endpoint) và thư mục `docs/guide`. Không có xung đột; các file đang sửa dở trong working tree
không trùng file nào của release.

## File thay đổi

- `AGENTS.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/architecture.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update/2026-09-24-them-thu-muc-docs-guide.md` → `docs/prd/update-archive/` — đổi tên: nhận từ release.
- `history/2026-09-25-ap-dung-thu-muc-docs-guide.md` — thêm: nhận từ release.
- `history/2026-09-25-widget-thanh-toan-them-du-gio.md` — thêm: nhận từ release.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: nhận từ release.
- `src/frontend/src/hooks/useAssistantCart.ts` — sửa: nhận từ release.
- `src/frontend/tests/unit/useAssistantCart.test.tsx` — thêm: nhận từ release.
- `history/2026-09-25-merge-release-mvp-v1-lan-2-vao-feat-agent.md` — thêm: entry này.

## Quyết định

- Merge `origin/release-mvp-v1` (không dùng nhánh local cũ), `--no-ff`, không rebase — giống lần merge trước.
- Không gỡ xung đột nào; không sửa code của hai phía.
- Thay đổi chưa commit của người dùng (tool plan 5 loại sản phẩm, slide agent, các entry history tương ứng) không
  nằm trong commit merge.

## Kiểm tra

- Không chạy test sau merge (thay đổi từ release chỉ chạm frontend widget/hook và docs; không chạm contract/DB).

## Còn lại / rủi ro

- Chưa có kết quả test frontend sau merge; xem CI khi tạo PR.
