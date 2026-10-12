# Response của agent: `status` và `error.code`

Phân biệt kết quả hội thoại (HTTP 200) với lỗi, và luồng tiếp tục hội thoại sau khi người dùng nhập giá trị không hợp lệ. Nguồn sự thật là [OpenAPI](../../src/shared/contracts/openapi.yaml).

Response cuối cùng của một lượt chỉ thuộc một trong hai nhóm, đừng nhầm:

| Nhóm | Dấu hiệu | Giá trị |
|---|---|---|
| Kết quả hội thoại | HTTP 200, có `status` và `conversationId` | `COMPLETED`, `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK` |
| Lỗi | HTTP khác 200, có `error.code` | `LLM_UNAVAILABLE`, `SEARCH_UNAVAILABLE`, `ITINERARY_VALIDATION_FAILED`, `INVALID_TOKEN`/`TOKEN_EXPIRED`, `CONVERSATION_NOT_FOUND`, `VALIDATION_ERROR` |

**Dòng tiêu đề.** `question`, `message` của `NO_RESULTS`/`FALLBACK` và `error.message` của lỗi từ chối (`VALIDATION_ERROR` 400) mở đầu bằng `**Tiêu đề**` tóm tắt cả câu (spec Itinerary §4.3). Chào hỏi, cảm ơn không có tiêu đề; lời cảm ơn, hẹn gặp lại khi người dùng không muốn đi nữa cũng vậy.

**Giá trị không hợp lệ không còn là lỗi** (đề xuất `docs/prd/update-archive/2026-09-30-bao-loi-dau-vao-khong-hop-le.md`). Ngày đi
đã qua, điểm đến ngoài catalog, số ngày ngoài 1–7, số người hoặc ngân sách ngoài giới hạn đều trả `NEEDS_CLARIFICATION`
(HTTP 200) với dòng đầu `**tiêu đề**` in đậm, lý do và gợi ý (spec Itinerary §4.3). Hai mã `UNSUPPORTED_DESTINATION` (422) và
`INVALID_TRIP_DURATION` (400) vẫn nằm trong enum của contract (không xoá ở v1) nhưng trợ lý không còn trả chúng.

Luồng tiếp tục sau khi nhập điểm đến ngoài catalog:

```text
Lượt 1: "tokyo 4 ngày từ ngày mai"
  → classify (destination=Tokyo, days=4, startDate) → tool (đối chiếu danh sách điểm đến, chưa gọi Search)
  → clarify → NEEDS_CLARIFICATION (missingFields=["destination"], suggestedValues.destination = danh sách hỗ trợ)
  → finalize lưu intent với destination=null, giữ days/startDate/party
Lượt 2: "ha noi" + conversationId lấy từ response.conversationId
  → intake nạp intent đã lưu → classify (destination=Hà Nội) → tool → evaluate → filter → compose → COMPLETED 4 ngày
```

- Mọi trường hợp không hợp lệ đều lưu phần intent còn lại (bỏ riêng trường sai) như mọi lượt hỏi lại, nên gửi lại `conversationId` cùng giá trị hợp lệ là tiếp tục chuyến đi. Lỗi thật (`LLM_UNAVAILABLE`...) không lưu nên client phải gửi lại đủ thông tin.
- Lượt 2 chỉ nói số ngày mà không có điểm đến thì agent hỏi lại điểm đến (`NEEDS_CLARIFICATION`, `missingFields=["destination"]`).
- Client phải lấy `conversationId` từ `error.details` khi response là lỗi (Streamlit dùng `conversation_id_of`); nếu không, lượt sau sẽ mở hội thoại mới và hỏi lại số ngày.
