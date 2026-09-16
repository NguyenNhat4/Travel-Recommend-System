# Hợp đồng API dùng chung

> **MVP 1.2.0:** ưu tiên hiển thị recommendation; [bộ trường tối thiểu](MVP.md) và OpenAPI hiện hành thay thế danh sách required/optional cũ bên dưới. Các trường mở rộng vẫn được hỗ trợ nhưng không bắt buộc gửi.

Bắt đầu tại [openapi.yaml](openapi.yaml). File này giữ thông tin phiên bản, danh sách endpoint và tham chiếu tới các file theo nghiệp vụ. Toàn bộ các file tạo thành một contract; không sửa bản bundle được sinh ra.

## Đọc file nào?

| Phần | Endpoint: nhận/trả gì, HTTP status | Schema: cấu trúc từng trường |
|---|---|---|
| Itinerary Agent | [paths/itinerary-agent.yaml](paths/itinerary-agent.yaml) | [schemas/itinerary-agent.yaml](schemas/itinerary-agent.yaml) |
| Search | [paths/search.yaml](paths/search.yaml) | [schemas/search.yaml](schemas/search.yaml) |
| Catalog / sản phẩm | [paths/catalog.yaml](paths/catalog.yaml) | [schemas/catalog.yaml](schemas/catalog.yaml) |
| Recommendation | [paths/recommendations.yaml](paths/recommendations.yaml) | [schemas/recommendations.yaml](schemas/recommendations.yaml) |
| Auth | [paths/auth.yaml](paths/auth.yaml) | [schemas/auth.yaml](schemas/auth.yaml) |
| Booking / giỏ hàng | [paths/booking.yaml](paths/booking.yaml) | [schemas/booking.yaml](schemas/booking.yaml) |
| Enum và lỗi chung | — | [schemas/common.yaml](schemas/common.yaml) |

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

Dùng `/tmp/travel-openapi.yaml` làm đầu vào công cụ. Đây là bản sinh tự động; chỉnh sửa tại `paths/` hoặc `schemas/`, rồi tạo bundle lại. Script chỉ hỗ trợ local refs và bố cục contract của repo, không tải tài liệu qua mạng.

Fixture Agent: [../mocks/itinerary-agent](../mocks/itinerary-agent/README.md). Quyết định nghiệp vụ và phần chờ xác nhận: [baseline](../../../docs/spec/contract-baseline-v1.1.md).
