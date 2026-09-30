# Proxy không log lỗi khi trình duyệt huỷ; Home bớt huỷ request gợi ý

- Ngày: 2026-10-01
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Log dev của Next.js hiện `GET /api/v1/recommendations?k=4 200` kèm `Backend proxy error [ResponseAborted]`. Backend trả đúng; request bị
trình duyệt huỷ. Phục vụ FR-REC-01 (gợi ý ở Home) và giữ ngân sách request của Home (`docs/spec/hop-dong-tich-hop-frontend.md` §4.1). Không lệch PRD.

Nguyên nhân:
- `HomeView` có effect gọi `fetchRecommendations` với `AbortController`, cleanup luôn `abort()`.
- Deps của effect là `[currentPersona, activeEvents, recsRetry]`: đối tượng persona đổi tham chiếu mỗi lần nạp phiên, `resetClientState` gán
  `[]` mới cho `activeEvents`, nên request đang bay bị huỷ rồi gọi lại. Ở dev, `reactStrictMode: true` còn mount → cleanup → mount nên huỷ thêm một lần.
- `proxy.ts` truyền `request.signal` sang `fetch` backend; khi bị huỷ, `fetch` ném `ResponseAborted` và nhánh `catch` ghi `console.error` rồi trả 502.

## File thay đổi

- `src/frontend/src/services/server/proxy.ts` — sửa: `request.signal.aborted` thì trả 499 rỗng, không log; lỗi mạng thật vẫn log và trả 502.
- `src/frontend/src/components/home/HomeView.tsx` — sửa: deps effect gợi ý đổi sang `personaId`, `activeDestination`, `activeEvents.length`, `recsRetry`.
- `src/frontend/tests/api/bff-auth.test.ts` — sửa: thêm test client huỷ → 499 không log, lỗi mạng → 502 có log.

## Quyết định

- Giữ `activeEvents.length` trong deps: có event mới (xem sản phẩm...) thì gợi ý vẫn làm mới như trước; `[]` thay `[]` không còn kích hoạt.
- Không tắt `reactStrictMode`; Strict Mode vẫn huỷ một request ở dev nhưng giờ không còn log.
- Dùng 499 (client closed request) vì không có ai nhận response; không đổi contract.

## Kiểm tra

- `node_modules/.bin/vitest run tests/api/bff-auth.test.ts tests/unit/homeView.test.tsx` (từ `src/frontend`): 23 test pass.
- `node_modules/.bin/tsc --noEmit -p .`: không lỗi.
- Chưa chạy lại dev server để xem log thực tế.

## Còn lại / rủi ro

- Backend vẫn có thể chạy xong truy vấn recommendation của request đã bị huỷ (FastAPI không tự dừng); chỉ giảm số lần huỷ ở client.
