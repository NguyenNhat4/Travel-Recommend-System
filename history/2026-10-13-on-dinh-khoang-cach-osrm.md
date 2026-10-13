# Sửa test OSRM không ổn định: chờ đủ khoảng tối thiểu theo vòng lặp

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/xoa-monitoring-staging-cu
- Trạng thái: hoàn thành
- Phạm vi: frontend (services)

## Mục tiêu

Job `Frontend quality checks` của PR #191 fail ở `tests/routeGeometry.test.ts:324`: "expected 19 to be greater than or equal to 20". Test kiểm các yêu cầu OSRM tuần tự cách nhau tối thiểu 25 ms. Thay đổi của PR không chạm frontend, nên đây là lỗi có sẵn của test (không ổn định trên runner), không phải do PR gây ra.

## Nguyên nhân

`enqueueOsrmRequest` (`src/frontend/src/services/routeGeometry.ts`) chờ đúng một lần `setTimeout(wait)`. Node có thể đánh thức timer sớm vài mili giây so với `Date.now()`, nên khoảng cách thực tế giữa hai lần gửi có thể nhỏ hơn `minimumIntervalMs`. Hàm này hứa khoảng cách tối thiểu, nên lời hứa bị vi phạm đúng lúc timer đến sớm; test chỉ phát hiện ra điều đó.

## File thay đổi

- `src/frontend/src/services/routeGeometry.ts` — sửa: `enqueueOsrmRequest` chờ lặp đến khi `Date.now() - lastOsrmRequestStartedAt` đủ `minimumIntervalMs`, thay vì một lần `setTimeout`.
- `history/2026-10-13-on-dinh-khoang-cach-osrm.md` — thêm: entry này.

Test không đổi.

## Quyết định

- Sửa hành vi bên trong thay vì nới ngưỡng test (`>= 20` → thấp hơn): ngưỡng test đúng với cấu hình (25 ms), chỉ có cơ chế chờ là chưa đảm bảo.
- Không đổi hành vi bên ngoài: số yêu cầu, thứ tự và khoảng cách tối thiểu giữ nguyên, chỉ không còn gửi sớm hơn khoảng đã cấu hình.
- Không có tài liệu nào trong `docs/` quy định cơ chế này (đã tìm `osrm` trong `docs/spec`, `docs/prd`, `docs/guide`).

## Kiểm tra

- `npx vitest run tests/routeGeometry.test.ts`: 21/21 pass; chạy lặp 10 lần liên tiếp đều pass.
- `npm run lint`: 0 error, 3 warning có sẵn ở `ItineraryMap.tsx` và `useFloatingWidget.ts` (không thuộc thay đổi này).
- `npm run typecheck`: pass.
- `npm run test`: 80 file, 841 test pass.
- `npm run build`: pass.

## Còn lại / rủi ro

- Nếu đồng hồ hệ thống nhảy lùi, vòng lặp chờ thêm đúng độ nhảy rồi kết thúc (không treo). Hành vi này giống code cũ, chỉ khác là nay cũng áp dụng cho lần đánh thức sớm.
