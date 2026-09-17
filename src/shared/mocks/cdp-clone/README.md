# Fixture cho CDP clone

Contract: [cdp-clone.openapi.yaml](../../contracts/cdp-clone.openapi.yaml). Chỉ Backend, seed và job gọi CDP clone bằng `X-Service-Token`; Web dùng `POST /api/v1/events` của Backend. Sản phẩm lấy từ sample thật; `cdpUserId`, `eventId`, thời gian và hồ sơ là dữ liệu kiểm thử.

| File | Schema | Dùng cho |
|---|---|---|
| `backend-browse-events.request.json` | `RecordEventsRequest` — `search`, `product_view`, `add_to_cart` do Backend ghi nền | Backend |
| `backend-purchase.request.json` | `RecordEventsRequest` — `purchase` ghi đồng bộ khi checkout | Backend |
| `record-events.201.json` | `RecordEventsResponse` | Backend |
| `record-events.401-invalid-token.json` | `ErrorResponse` — sai service token | Backend |
| `cancel-event.200.json` | `UserEvent` sau `PUT .../cancellation` | Backend |
| `user-events.200.json` | `EventListResponse` | Backend, Recommendation |
| `profile.200.json` | `Profile` | Backend, Recommendation |

Chạy từ repo root: `python3 src/shared/contracts/tests/validate_contract.py`.
