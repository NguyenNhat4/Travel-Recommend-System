# Response của agent: `status` và `error.code`

Phân biệt kết quả hội thoại (HTTP 200) với lỗi, và luồng tiếp tục hội thoại sau `UNSUPPORTED_DESTINATION`. Nguồn sự thật là [OpenAPI](../../src/shared/contracts/openapi.yaml).

Response cuối cùng của một lượt chỉ thuộc một trong hai nhóm, đừng nhầm:

| Nhóm | Dấu hiệu | Giá trị |
|---|---|---|
| Kết quả hội thoại | HTTP 200, có `status` và `conversationId` | `COMPLETED`, `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK` |
| Lỗi | HTTP khác 200, có `error.code` | `INVALID_TRIP_DURATION`, `UNSUPPORTED_DESTINATION`, `LLM_UNAVAILABLE`, `SEARCH_UNAVAILABLE`, `ITINERARY_VALIDATION_FAILED`, `INVALID_TOKEN`/`TOKEN_EXPIRED`, `CONVERSATION_NOT_FOUND`, `VALIDATION_ERROR` |

`UNSUPPORTED_DESTINATION` là mã lỗi, không phải `status`. Node `tool` trả mã này (HTTP 422) khi tên điểm đến không khớp catalog và LLM cũng không chọn được tên nào trong danh sách, trước khi gọi Search. `error.message` viết cho người dùng: nêu điểm đến đã nhập và liệt kê các điểm đến đang hỗ trợ. `error.details` gồm `destination`, `supportedDestinations` và `conversationId`.

Luồng tiếp tục sau lỗi này:

```text
Lượt 1: "tokyo 4 ngày từ ngày mai"
  → classify (destination=Tokyo, days=4, startDate) → tool → UNSUPPORTED_DESTINATION (422)
  → finalize lưu intent với destination=null, giữ days/startDate/party
Lượt 2: "ha noi" + conversationId lấy từ error.details.conversationId
  → intake nạp intent đã lưu → classify (destination=Hà Nội) → tool → evaluate → answer → COMPLETED 4 ngày
```

- Chỉ `UNSUPPORTED_DESTINATION` được lưu intent khi lỗi; các lỗi khác (`INVALID_TRIP_DURATION`, `LLM_UNAVAILABLE`...) không lưu nên client phải gửi lại đủ thông tin.
- Lượt 2 chỉ nói số ngày mà không có điểm đến thì agent hỏi lại điểm đến (`NEEDS_CLARIFICATION`, `missingFields=["destination"]`).
- Client phải lấy `conversationId` từ `error.details` khi response là lỗi (Streamlit dùng `conversation_id_of`); nếu không, lượt sau sẽ mở hội thoại mới và hỏi lại số ngày.
