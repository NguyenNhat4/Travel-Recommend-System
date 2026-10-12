# Sửa E2E chi tiết widget theo trình xem ảnh phóng to

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Sửa frontend CI của PR #169, run 38226175000, job 114737684676. Hai ca widget-detail ở 1024/1440px fail vì locator ảnh khớp cả ảnh panel và ảnh phóng to sau khi bấm thumbnail. Phục vụ FR-AGT-03/04, luồng panel trong PRD user-flow §4.2 và kiểm thử E2E theo test-plan.

## File thay đổi

- `src/frontend/tests/e2e/widget-detail.spec.ts` — sửa: giới hạn ảnh panel trong nút phóng to; kiểm tra hộp ảnh mở, ảnh được chọn, Esc/nút đóng chỉ đóng hộp ảnh; giữ kiểm tra chiều cao gallery, footer, cuộn và quay lại lịch trình.
- `history/2026-10-12-fix-ci-widget-detail-lightbox.md` — thêm: entry này.

## Quyết định

- Chỉ cập nhật test theo hành vi phóng to đã chốt trong PRD user-flow §4.2 và triển khai được ghi trong `2026-10-12-trien-khai-gop-y-widget-tro-ly.md`; không đổi sản phẩm, contract hoặc fixture.
- CI còn ba ca flaky ở navigation và widget-opening; không sửa suy đoán vì cả ba pass lần đầu khi chạy local với retry tắt.
- Khôi phục `next-env.d.ts` do build tự sinh về bản trước task; giữ các file untracked của task khác.

## Kiểm tra

- Đọc log CI qua `gh run view 38226175000 --job 114737684676 --log-failed`: build và TypeScript pass; 2 failed, 3 flaky, 34 passed.
- `npm run build:web`: PASS ngoài sandbox. Lần chạy trong sandbox lỗi `Could not parse output from TypeScript's --showConfig`.
- `node_modules/.bin/eslint tests/e2e/widget-detail.spec.ts`: PASS.
- `npm exec -- playwright test --retries=0`: PASS, 39/39 Chromium tests, 2.7 phút, exit 0. Lần gọi Playwright trực tiếp trước đó không khởi động được server vì thiếu cross-env trong PATH; chạy qua npm khắc phục.
- `git diff --check`: PASS.

## Còn lại / rủi ro

- Chưa commit/push hoặc chạy lại CI GitHub.
- E2E dùng API mô phỏng, không xác minh backend/LLM thật. Server local báo thiếu SESSION_REDIS_URL ở các request auth refresh chưa mô phỏng; bộ smoke vẫn pass.
- Ba ca flaky của CI chưa chứng minh đã hết chập chờn; lần chạy local không tái hiện.
