# Sửa lỗi 422 khi bấm "Viết bằng AI"

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend
- Bị thay thế bởi: `history/2026-10-12-so-thich-chip-co-dinh.md`

## Mục tiêu

Người dùng bấm "Viết bằng AI" trong form luôn thấy "AI chưa viết được gợi ý"; log backend: `POST /api/v1/assistant/preferences` 422 `VALIDATION_ERROR`, `request_bytes` 74 (AC-AGT-01, `history/2026-10-12-so-thich-mot-doan-mo-ta.md`).

## File thay đổi

- `src/frontend/src/services/tripPreferences.ts` — sửa: gửi header `Content-Type: application/json`.
- `src/frontend/tests/unit/tripDetailsForm.test.tsx` — sửa: kiểm header này trong request Viết bằng AI.

## Quyết định

- Nguyên nhân đã tái hiện bằng curl vào backend: cùng body, thiếu `Content-Type` → 422; có `application/json` → 200 `status: ready`. `apiFetch` không tự đặt header này; các service khác (`auth.ts`, `catalog.ts`) tự đặt.

## Kiểm tra

- `vitest run tests/unit/tripDetailsForm.test.tsx`: 13 passed; `tsc --noEmit` sạch.
- curl backend có header: 200, trả đoạn văn.

## Còn lại / rủi ro

- Người dùng thử lại trên trình duyệt (dev server tự nạp lại).
