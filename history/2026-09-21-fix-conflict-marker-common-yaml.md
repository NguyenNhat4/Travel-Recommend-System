# Gỡ conflict marker còn sót trong schemas/common.yaml

- Ngày: 2026-09-21
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: contract

## Mục tiêu

`POST /api/v1/assistant/itineraries/stream` trả 500. Traceback cho thấy `bundle_openapi.read()`
không parse được `src/shared/contracts/schemas/common.yaml`: file còn nguyên conflict marker
`<<<<<<< HEAD` / `=======` / `>>>>>>> 91449cb` đã bị commit vào nhánh, nên mọi request đi qua
`valid("ItineraryRequest", ...)` đều vỡ ở bước bundle contract.

## File thay đổi

- `src/shared/contracts/schemas/common.yaml` — sửa: gỡ khối conflict ở dòng 171–185, gộp nội dung
  `description` của `details` trong `Error`.

## Quyết định

- Gộp cả hai phía thay vì chọn một: phía HEAD có `MIN_STAY_NOT_MET {productId, minStay}` và
  `PRODUCT_NOT_INDEXED {productId, taxonomy}`; phía 91449cb bổ sung `conversationId` vào
  `UNSUPPORTED_DESTINATION`. Bỏ phía nào cũng làm mất mô tả của mã lỗi đang dùng thật.
- Giữ style block scalar `>-` của HEAD cho thống nhất với các description khác trong file.
- Chỉ sửa mô tả, không đổi field/semantics — không vi phạm quy tắc "không đổi v1" ở AGENTS.md §3.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: **fail**, nhưng
  ở một lỗi khác, không liên quan file này — `KeyError: 'priceUnit'` tại dòng 44, khi so fixture
  `src/shared/mocks/itinerary-agent/products.json` với nguồn
  `src/data_collection/sample/products-sample.jsonl`. Lỗi này trước đây bị che bởi ScannerError YAML.
- `valid("ItineraryRequest", {...})` → `True`: bundle contract load lại được, lỗi 500 của endpoint đã hết.

## Còn lại / rủi ro

- `priceUnit` là required của `ProductSummary` (`schemas/catalog.yaml:118`) nhưng pipeline
  `src/data_collection` không sinh field này, nên `products-sample.jsonl` thiếu nó trong khi mock
  fixture lại có. Chưa sửa: cần quyết định giá trị `priceUnit` theo taxonomy, thuộc phạm vi
  data_collection + contract, phải hỏi người dùng trước (AGENTS.md §2).
- Nên rà các file khác từng bị merge trong đợt 91449cb xem còn marker nào không:
  `grep -rn "^<<<<<<< " src/ docs/` hiện sạch.
