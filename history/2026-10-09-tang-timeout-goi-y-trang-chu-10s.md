# Tăng timeout gợi ý ở trang chủ lên 10 giây

- Ngày: 2026-10-09
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Khối "Gợi ý" ở trang chủ không hiện với người đã đăng nhập: `GET /recommendations` mất 3,2–9,6 giây (log backend, nhánh `recent_activity`/`cross_vertical`) trong khi frontend huỷ request sau 3 giây và hiện dòng "Thử lại". Người dùng yêu cầu tăng timeout lên 10 giây.

## File thay đổi

- `src/frontend/src/components/home/HomeView.tsx` — sửa: `RECOMMENDATION_TIMEOUT_MS` 3000 → 10000.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§4.1 ngân sách request, §6.4 bảng hằng số) — sửa: 3 giây → 10 giây.
- `docs/spec/product.md` (bảng lỗi Home ①) — sửa: timeout > 3 giây → > 10 giây.
- `history/2026-10-09-tang-timeout-goi-y-trang-chu-10s.md` — thêm: entry này.

## Quyết định

- Con số 3 giây chỉ có trong `docs/spec/`, không có trong `docs/prd/`, nên không cần đề xuất lệch PRD; spec được sửa theo trong cùng thay đổi.
- Đây là cách che độ trễ, không sửa nguyên nhân.

## Kiểm tra

- `vitest run tests/unit/homeView.test.tsx`: 8 test pass.

## Còn lại / rủi ro

- Backend vẫn chậm 3–10 giây cho người dùng đã đăng nhập; chưa điều tra bước tốn thời gian. Người dùng vẫn chờ tới 10 giây mới thấy dòng "Thử lại" nếu lỗi.
