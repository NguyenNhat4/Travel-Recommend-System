# Cho contracts.py đi theo $ref khi đọc enum/bounds từ OpenAPI

- Ngày: 2026-09-21
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Sau khi gỡ conflict marker trong `schemas/common.yaml` (7d2e6e5), endpoint
`POST /api/v1/assistant/itineraries/stream` vẫn 500 ở lỗi kế tiếp:
`KeyError: 'enum'` tại `enum_values("ProductSummary", "priceUnit")`
(`src/backend/app/agents/models.py:12`), làm `build_graph()` không import được `nodes`.

Nguyên nhân: trong `schemas/catalog.yaml:161`, `priceUnit` khai báo bằng
`$ref: ../openapi.yaml#/components/schemas/PriceUnit` kèm `description` anh em.
`bundle_openapi.walk()` chỉ inline ref tới file khác; ref đã trỏ nội bộ (`#/...`) thì
giữ nguyên dạng `$ref`. Vì vậy `_property()` trả về node `{$ref, description}` —
không bao giờ có `enum`. Lỗi này bị che từ trước bởi ScannerError YAML của common.yaml.

## File thay đổi

- `src/backend/app/application/itinerary/contracts.py` — sửa: thêm `_resolve()` đi theo
  `$ref` nội bộ (có unescape JSON Pointer `~1`/`~0`), và `_property()` resolve cả node
  trung gian lẫn node cuối trước khi trả về.

## Quyết định

- Sửa ở phía đọc (backend) chứ không inline ref trong contract: contract là nguồn sự thật
  (AGENTS.md §2) và cách viết `$ref` + `description` ở catalog.yaml là hợp lệ với OpenAPI.
  Đổi bundler hoặc nhân bản enum vào catalog.yaml đều làm contract kém đúng hơn.
- `_resolve` dùng vòng `while` để chịu được ref nhiều tầng; `document` dựng từ
  `node["components"]` mà `schema()` đã gắn sẵn, không gọi lại `bundle()`.

## Kiểm tra

- `enum_values`: PartyType/Pace/Taxonomy trả đúng như trước; `ProductSummary.priceUnit`
  giờ trả `('PER_NIGHT', 'PER_PERSON', 'PER_PACKAGE', 'UNKNOWN')`. `bounds` không đổi.
- `build_graph()`: dựng được đủ 9 node + `__start__`/`__end__`.
- `TestClient` POST `/api/v1/assistant/itineraries/stream`: **200**, stream phát
  `run.started` và `graph.topology` → lỗi 500 đã hết.
- `python -m pytest src/backend -q`: 106 passed, **2 failed** — cả hai có từ trước, không
  liên quan thay đổi này (trước đây file test không collect nổi vì chính `KeyError: 'enum'`).
- `validate_contract.py`: vẫn fail ở `KeyError: 'priceUnit'` (xem mục dưới).

## Còn lại / rủi ro

Ba lỗi còn lại đều cùng một gốc: `priceUnit` đã thành required của `ProductSummary`
(`schemas/catalog.yaml:118`, quyết định C1) nhưng dữ liệu và test chưa theo:

- `src/data_collection/sample/products-sample.jsonl` không có `priceUnit` trong khi mock
  `src/shared/mocks/itinerary-agent/products.json` có → `validate_contract.py` dòng 44 fail.
  Pipeline `src/data_collection` hiện không sinh field này. Cần chốt `priceUnit` dẫn xuất từ
  taxonomy thế nào trước khi sửa — chưa tự quyết (AGENTS.md §2).
- `src/backend/tests/unit/agents/test_itinerary_tools.py::HttpTests::test_minimal_projection_preserves_null_false_and_because`:
  product trong test thiếu `priceUnit` nên gateway trả `INVALID_TOOL_RESPONSE`, không có key `data`.
- `src/backend/tests/unit/agents/test_itinerary_tools.py::ContractTests::test_schemas_and_defaults`:
  test chưa biết default `includeVariants: false` mà `normalize_arguments` đang sinh.
  Cần xác nhận default này đúng ý đồ rồi mới cập nhật test.
