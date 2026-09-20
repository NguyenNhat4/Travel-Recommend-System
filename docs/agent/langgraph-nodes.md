# LangGraph: trace, node và luồng thực thi

Cách đọc bảng trace của Streamlit, trách nhiệm từng node và các nhánh của graph. Xem [README](README.md) để chạy demo.

## Đọc bảng LangGraph execution

Bảng bên phải là trace của **một lượt gọi API qua SSE**, theo đúng thứ tự event backend phát ra. Mỗi dòng cho biết một node đã kết thúc; bảng không hiển thị raw state, prompt, token, JWT hay payload nội bộ.

| Cột | Cách đọc |
|---|---|
| `sequence` | Thứ tự event trong lượt chạy, bắt đầu từ 1. Đây không phải số thứ tự cố định của node trong mọi luồng. |
| `nodeId` | Tên node LangGraph vừa hoàn tất. Node không đi qua trong lượt hiện tại sẽ không có dòng. |
| `outcome` | Trạng thái thực thi của node. `completed` chỉ có nghĩa node đã chạy xong; kết quả nghiệp vụ cuối cùng vẫn phải xem response và validation. |
| `message` | Tóm tắt quyết định hoặc công việc node vừa làm; `tool` ghi `retrieval completed (normalized destination)` khi điểm đến người dùng nhập được đổi thành tên catalog. Ví dụ `compose` ở node `evaluate` nghĩa là dữ liệu đủ điều kiện đi tiếp tới bước soạn lịch trình; việc soạn thực sự nằm ở `answer`. |
| `durationMs` | Thời gian quan sát từ event node trước đến event hiện tại tại biên SSE, gồm thời gian chạy node và overhead cập nhật/phát state. Đây không phải CPU profile chính xác bên trong node. Giá trị tối thiểu là 1 ms. |

Ví dụ trace `intake → classify → tool → evaluate → answer → finalize` là luồng lập lịch đầy đủ:

1. Request được chuẩn hóa trong `intake`.
2. `classify` mất nhiều thời gian để gọi LLM trích xuất intent.
3. `tool` lập kế hoạch tool rồi truy xuất sản phẩm thật.
4. `evaluate` kiểm tra kết quả retrieval và quyết định `compose`.
5. `answer` gọi LLM sắp xếp các candidate đã được grounding thành lịch trình.
6. `finalize` kiểm tra schema và grounding lần cuối trước khi trả response.

Tổng các dòng trong ví dụ là `10.867 ms`, tức xấp xỉ `10,9 giây`. Con số này giải thích thời gian quan sát theo node của trace đó, nhưng không thay thế latency đầu-cuối của HTTP request và không chứng minh SLA production.

## Chín node làm gì

Mỗi node chỉ đọc và ghi vào state chung của graph. Bảng dưới cho biết node nhận gì, trả gì và đi tiếp đâu.

| Node | Nhận vào | Trả ra | Đi tiếp |
|---|---|---|---|
| `intake` | Message của người dùng, `conversationId` (nếu có). | State khởi tạo: message đã chuẩn hóa, `conversationId`, intent đã lưu của hội thoại. | `classify` |
| `classify` | Message và intent đã lưu. Gọi LLM. | Intent/constraints (`destination`, `days`...), các trường còn thiếu, cờ hội thoại chung hoặc yêu cầu bị từ chối. | `tool` nếu đủ `destination` + `days`; `answer` nếu cần hỏi lại hoặc trò chuyện; `dead_letter` nếu lỗi. |
| `tool` | Intent/constraints. Có thể gọi LLM. | Tên điểm đến đã chuẩn hóa theo catalog, kết quả Search/Recommendation/ProductDetail (hoặc lỗi) trong `tool_results`. Điểm đến ngoài catalog trả `UNSUPPORTED_DESTINATION` (422) kèm danh sách điểm đến hỗ trợ. | `evaluate` |
| `evaluate` | `tool_results` và intent. | Danh sách candidate hợp lệ có nguồn grounding, hoặc phân loại: `compose`, `no_results`, `fallback`, `constraint_clarification`, lỗi tạm thời/vĩnh viễn. | `answer`, `retry` hoặc `dead_letter` |
| `answer` | Candidate đã evaluate (chỉ `hotel`, `attraction`, `golf`; `flight`/`combo` không xếp lịch được nên không đưa cho LLM), hoặc message hội thoại/làm rõ. Có thể gọi LLM. | Lịch trình (`COMPLETED`), hoặc `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK`, câu trả lời hội thoại, từ chối. Chỉ dùng ID/tên/giá của candidate có sẵn; slot vi phạm quy tắc xếp lịch bị bỏ riêng kèm warning `SLOT_DROPPED_UNSCHEDULABLE`, không làm mất cả lịch trình. | `finalize` |
| `clarify` | Danh sách trường còn thiếu. | Response `NEEDS_CLARIFICATION` theo rule cố định. Hiện routing đưa trường hợp này qua `answer`, nên trace thường không có node này. | `finalize` |
| `retry` | Lỗi tool tạm thời và số lần đã thử. | Quyết định thử lại (tối đa một lần), dùng fallback hoặc báo lỗi. | `tool`, `answer` hoặc `dead_letter` |
| `dead_letter` | Lỗi auth, tool plan/argument hoặc upstream. | `ErrorResponse` chuẩn, không che lỗi thành thành công. | `finalize` |
| `finalize` | Response từ `answer` hoặc `dead_letter`. | Response cuối đã validate schema và grounding, kèm latency; lưu conversation nếu thành công. Validation lỗi thành `ITINERARY_VALIDATION_FAILED`. | `END` |

## Các luồng thực thi

```text
START → intake → classify
  ├─ đủ destination + days
  │    → tool → evaluate
  │       ├─ candidate hợp lệ → answer (compose) → finalize → END
  │       ├─ không có kết quả/vi phạm điều kiện → answer (no-results hoặc hỏi lại) → finalize → END
  │       ├─ lỗi tạm thời → retry → tool (tối đa một lần)
  │       └─ lỗi vĩnh viễn/auth → dead_letter → finalize → END
  ├─ chào hỏi, cảm ơn hoặc thiếu destination/days
  │    → answer (hội thoại/làm rõ, không gọi product tool) → finalize → END
  └─ request lỗi, LLM classify lỗi hoặc yêu cầu bị từ chối
       → dead_letter hoặc answer (refusal) → finalize → END
```

Các điểm cần nhớ khi đọc trace:

- Không thấy `tool` nghĩa là agent chưa truy xuất sản phẩm; thường do thiếu `destination`/`days`, hội thoại chung hoặc request bị từ chối.
- Có `retry` nghĩa là retrieval gặp lỗi tạm thời; graph chỉ cho phép retry một lần để tránh vòng lặp vô hạn.
- `answer` không đồng nghĩa luôn có `COMPLETED`: node này còn tạo `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK` hoặc response từ chối.
- Chỉ `run.completed.response` và kết quả ở `finalize` mới cho biết trạng thái API cuối cùng. Trace `completed` ở từng node không phải kết luận PASS của evaluation.
- Trace dùng fixture chỉ chứng minh luồng local và grounding vào fixture; không chứng minh availability, giá hiện tại, chất lượng Search hay latency production.
