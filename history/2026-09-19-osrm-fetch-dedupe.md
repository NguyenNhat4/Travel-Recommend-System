# Sửa OSRM fetch và gộp request đang bay

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: data_contract
- Trạng thái: hoàn thành có giới hạn môi trường
- Phạm vi: frontend

## Mục tiêu

Khắc phục việc map fullscreen chỉ hiện marker mà không gửi request OSRM hoặc không vẽ route; đồng thời tránh request trùng khi React Strict Mode gọi route lookup đồng thời.

## File thay đổi

- `src/frontend/src/services/routeGeometry.ts` — sửa: bind injected/native fetch với globalThis; dedupe các cache miss đang bay theo cùng cache key.
- `src/frontend/tests/routeGeometry.test.ts` — sửa: kiểm tra fetch receiver và in-flight dedupe, giữ regression coverage cho profile, geometry và lỗi provider.

## Quyết định

- Giữ OSRM public FOSSGIS, profile car/foot/bike, GeoJSON geometry và quy tắc road route lỗi thì unavailable, không vẽ đường thẳng thay thế.
- Gọi fetch bằng receiver globalThis để tránh lỗi “Illegal invocation”. Dedupe chỉ trong thời gian request còn chạy; caller nhận lại id/point IDs/titles riêng của chính request.
- Không đổi OpenAPI, backend, layout fullscreen hoặc dữ liệu itinerary.

## Kiểm tra

- Các kiểm tra ghi nhận routeGeometry tests 17/17, typecheck, ESLint, web/API build và Chromium fullscreen live smoke pass; smoke thấy 5 request OSRM duy nhất, 5 response 200/code Ok và 5 polyline.
- Full test suite có 17 route tests pass; 5 API tests bị sandbox chặn khi bind 0.0.0.0 (EPERM). Contract validation bị chặn bởi fixture/catalog có sẵn thiếu priceUnit.
- Không chạy lại các lệnh này trong lần gộp tài liệu.

## Còn lại / rủi ro

- OSRM public là best-effort, không có SLA; cần giới hạn lưu lượng hoặc chuyển provider có SLA/self-host khi triển khai production.
- Các file dirty/untracked ngoài phạm vi task được giữ nguyên.
