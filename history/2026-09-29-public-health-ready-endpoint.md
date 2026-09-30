# Thêm public readiness endpoint

- Ngày: 2026-09-29
- Trạng thái: code và test hoàn tất; image đã build/push, deploy VM còn chờ bước phát hành runtime

## Thay đổi

- Backend FastAPI thêm `GET /health/ready`.
- Endpoint trả `503` khi lifespan chưa hoàn tất hoặc đã shutdown, trả `200` với `ready: true` sau startup.
- Frontend thêm public route `/health/ready`, proxy tới Backend loopback và trả `503` nếu Backend không reachable.
- Thêm unit test backend và Vitest test cho public proxy.

## Kiểm tra

- Backend wiring test: `11 passed`.
- Frontend health-ready test: `2 passed`.
- Frontend typecheck: PASS.
- Frontend production build: PASS.
- Backend/frontend images đã build và push với tag `health-ready-20260929` và `latest`.

## Việc còn lại

- Deploy hai image lên App VM và xác nhận `https://v-ota.duckdns.org/health/ready` trả HTTP 200.
