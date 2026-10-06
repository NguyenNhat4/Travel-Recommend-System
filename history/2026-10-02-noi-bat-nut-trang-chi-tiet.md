# Làm nổi bật nút trang chi tiết

- Ngày: 2026-10-02
- Tác giả: người dùng / Codex
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Làm nút “Xem trang chi tiết” dễ nhận ra và ẩn nút cho sản phẩm “Tham quan tự do” theo yêu cầu đã chốt. Phục vụ FR-AGT-03/04 và NFR-REL-01.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetProductDetail.tsx` — sửa: viền xanh rõ, nền xanh nhạt và chữ xanh; chỉ hiện link khi `isFreeToVisit` trả về false.
- `src/frontend/tests/unit/widgetProductDetail.test.tsx` — sửa: kiểm tra sản phẩm thiếu giá và `ticketed=false` không có link, sản phẩm có giá vẫn có link đúng.
- `docs/prd/user-flow.md` — sửa: áp dụng ngoại lệ đã chốt vào §4.2 mục 3 trước khi sửa source.
- `docs/prd/update-archive/2026-10-02-an-link-chi-tiet-tham-quan-tu-do.md` — thêm: đề xuất người dùng chốt ngày 2026-10-02, đã áp dụng và chuyển khỏi `update/`.
- `history/2026-10-02-noi-bat-nut-trang-chi-tiet.md` — thêm: ghi thay đổi và phần đang chờ.

## Quyết định

- Nút chi tiết có màu xanh và viền rõ; nút thêm giỏ vẫn là nút nền xanh đậm.
- Người dùng chốt “Chốt: ẩn với Tham quan tự do”; cập nhật PRD trước rồi triển khai cùng helper đang dùng cho nhãn. Không đổi API/catalog hoặc suy luận từ tên.
- Commit các thay đổi UI đã kiểm tra theo yêu cầu trước đó; giữ riêng `next-env.d.ts` đã dirty trước task.

## Kiểm tra

- `npm run build:web` — PASS trên source cuối, gồm kiểm tra TypeScript.
- ESLint trên toàn bộ component/test UI của task — PASS; chạy lại 2 file sửa cuối cũng PASS.
- Vitest trên 5 file widget liên quan với `--maxWorkers=2` — PASS: 36 test, gồm điều kiện link cho sản phẩm có giá, thiếu giá và `ticketed=false`.
- `npm exec -- playwright test tests/e2e/widget-opening.spec.ts tests/e2e/widget-detail.spec.ts` — PASS: 8 test Chromium, 45 giây, exit 0.
- `git diff --check` và `git diff --cached --check` — PASS.

## Còn lại / rủi ro

- Kiểm thử UI dùng API mô phỏng, không xác minh backend trực tiếp.
