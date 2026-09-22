# Hợp đồng API dùng chung

> **MVP 1.2.0:** ưu tiên hiển thị recommendation; [bộ trường tối thiểu](mvp-minimal-fields-1.2.0.md) và OpenAPI hiện hành thay thế danh sách required/optional cũ bên dưới. Các trường mở rộng vẫn được hỗ trợ nhưng không bắt buộc gửi.

Bắt đầu tại [openapi.yaml](../../src/shared/contracts/openapi.yaml). File này giữ thông tin phiên bản, danh sách endpoint và tham chiếu tới các file theo nghiệp vụ. Toàn bộ các file tạo thành một contract; không sửa bản bundle được sinh ra.

## Đọc file nào?

| Phần | Endpoint: nhận/trả gì, HTTP status | Schema: cấu trúc từng trường |
|---|---|---|
| Itinerary Agent | [paths/itinerary-agent.yaml](../../src/shared/contracts/paths/itinerary-agent.yaml) | [schemas/itinerary-agent.yaml](../../src/shared/contracts/schemas/itinerary-agent.yaml) |
| Search | [paths/search.yaml](../../src/shared/contracts/paths/search.yaml) | [schemas/search.yaml](../../src/shared/contracts/schemas/search.yaml) |
| Catalog / sản phẩm | [paths/catalog.yaml](../../src/shared/contracts/paths/catalog.yaml) | [schemas/catalog.yaml](../../src/shared/contracts/schemas/catalog.yaml) |
| Recommendation | [paths/recommendations.yaml](../../src/shared/contracts/paths/recommendations.yaml) | [schemas/recommendations.yaml](../../src/shared/contracts/schemas/recommendations.yaml) |
| Ghi hành vi (`POST /events`) | [paths/events.yaml](../../src/shared/contracts/paths/events.yaml) | [schemas/events.yaml](../../src/shared/contracts/schemas/events.yaml) |
| Auth | [paths/auth.yaml](../../src/shared/contracts/paths/auth.yaml) | [schemas/auth.yaml](../../src/shared/contracts/schemas/auth.yaml) |
| Booking / giỏ hàng | [paths/booking.yaml](../../src/shared/contracts/paths/booking.yaml) | [schemas/booking.yaml](../../src/shared/contracts/schemas/booking.yaml) |
| Enum và lỗi chung | — | [schemas/common.yaml](../../src/shared/contracts/schemas/common.yaml) |
| CDP clone — nội bộ, chỉ Backend/seed/job gọi (entry riêng [cdp-clone.openapi.yaml](../../src/shared/contracts/cdp-clone.openapi.yaml)) | [paths/cdp-clone.yaml](../../src/shared/contracts/paths/cdp-clone.yaml) | [schemas/cdp-clone.yaml](../../src/shared/contracts/schemas/cdp-clone.yaml) |

Ba schema chính:

- `SearchRequest`: trong `schemas/search.yaml`.
- `ProductSummary`: trong `schemas/catalog.yaml`, dùng chung cho Search, Agent và Web.
- `ItineraryResponse`: trong `schemas/itinerary-agent.yaml`.

`$ref` trong file con đi qua `../openapi.yaml#/components/...` để dùng cùng một định nghĩa. `openapi.yaml` giữ các tên component cũ, nên tên schema và dữ liệu API không đổi. File con là fragment, không phải một OpenAPI document độc lập; đưa file đầu vào chung cho công cụ đọc contract.

## Kiểm tra và tạo bản một file

Chạy từ repo root, cần PyYAML và jsonschema:

```bash
python3 src/shared/contracts/tests/validate_contract.py
```

Script tự ghép các file trước khi kiểm tra schema và fixture.

Nếu công cụ sinh client hoặc xem tài liệu cần một file YAML duy nhất:

```bash
python3 src/shared/contracts/scripts/bundle_openapi.py --output /tmp/travel-openapi.yaml
```

Dùng `/tmp/travel-openapi.yaml` làm đầu vào công cụ. CDP clone có base URL riêng nên có entry riêng; Web **không** sinh client cho nó. Hàm `bundle()` nhận đường dẫn entry, script validate kiểm tra cả hai. Nghiệp vụ tích hợp CDP: [hop-dong-tich-hop-cdp.md](hop-dong-tich-hop-cdp.md). Đây là bản sinh tự động; chỉnh sửa tại `paths/` hoặc `schemas/`, rồi tạo bundle lại. Script chỉ hỗ trợ local refs và bố cục contract của repo, không tải tài liệu qua mạng.

Fixture Agent: [../mocks/itinerary-agent](../../src/shared/mocks/itinerary-agent/README.md). Quyết định nghiệp vụ và phần chờ xác nhận: [baseline](contract-baseline-v1.1.md).
