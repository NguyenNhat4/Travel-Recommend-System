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

| Node | Trách nhiệm | Có gọi LLM/tool? | Kết quả/rẽ nhánh chính |
|---|---|---|---|
| `intake` | Chuẩn hóa message, tạo/đọc `conversationId`, khởi tạo state và nạp intent đã lưu của hội thoại. | Không gọi LLM; có thể đọc conversation store. | Luôn sang `classify`; hội thoại không tồn tại được đánh dấu lỗi để xử lý có kiểm soát. |
| `classify` | Dùng structured output để tách intent/constraints, nhận diện hội thoại chung, yêu cầu ngoài phạm vi/side effect, xung đột và các trường còn thiếu. | Có, một lời gọi LLM. | `tool` khi đủ `destination` + `days`; `answer` khi cần hội thoại/làm rõ; `dead_letter` khi request hoặc LLM lỗi. |
| `tool` | Đưa `destination` về đúng tên trong danh sách catalog (`list_destinations`) rồi để LLM lập tối đa 5 lời gọi read-only, validate arguments, gọi Search/Recommendation và hydrate ProductDetail khi cần. Tên khớp không phân biệt dấu/hoa thường thì dùng luôn; nếu không (`tphcm`, `sài gòn`, `pq`...) thì một lời gọi LLM chọn trong chính danh sách catalog, code kiểm tra lại kết quả có trong danh sách. Không có bảng alias viết tay. Cũng dọn `interests`, `exclude_taxonomies`, `specific_hotel/activity` và bỏ số người model đoán khi `FAMILY_WITH_KIDS` mà `children=0`. | Có thể gọi LLM để chọn điểm đến và lập tool plan; gọi các tool read-only song song. | Luôn sang `evaluate`; lỗi được giữ trong `tool_results` để node sau quyết định retry hay dừng. Điểm đến ngoài catalog trả `UNSUPPORTED_DESTINATION` (422) trước khi gọi Search, message nêu điểm đến người dùng nhập và liệt kê các điểm đến catalog đang hỗ trợ (cũng có trong `details.supportedDestinations`); `details.conversationId` trỏ tới hội thoại đã lưu intent còn lại (bỏ điểm đến) để lượt sau chỉ cần nói điểm đến hợp lệ; LLM chọn điểm đến lỗi trả `LLM_UNAVAILABLE`. |
| `evaluate` | Gom và lọc candidate theo intent/constraints, giữ nguồn grounding, loại sản phẩm không đủ căn cứ và phân loại lỗi tool. | Không. | Sang `answer`, `retry` hoặc `dead_letter`. Message có thể là `compose`, `no_results`, `fallback` hoặc `constraint_clarification`. |
| `answer` | Tạo câu hỏi/câu trả lời hội thoại, hoặc dùng LLM chọn các candidate thật để dựng lịch trình; khi không thể compose thì trả fallback/no-results có kiểm soát. | Có LLM cho hội thoại và composition; một số nhánh lỗi/no-results không cần gọi LLM. | Sang `finalize`. Không được tạo ID, tên hay giá ngoài candidate đã retrieval. |
| `clarify` | Dựng response `NEEDS_CLARIFICATION` theo rule cố định. | Không. | Sang `finalize`. Node vẫn nằm trong topology, nhưng routing hiện hành đưa trường hợp thiếu thông tin qua `answer` để LLM viết câu hỏi; vì vậy trace bình thường có thể không đi qua node này. |
| `retry` | Quyết định thử lại lỗi tool tạm thời, tối đa một lần; nếu hết lượt thì chọn fallback hoặc lỗi. | Không. | Quay lại `tool`, sang `answer` để fallback, hoặc sang `dead_letter`. |
| `dead_letter` | Chuyển lỗi auth, tool plan/argument hoặc upstream thành `ErrorResponse` chuẩn, không che lỗi thành thành công. | Không. | Sang `finalize`. |
| `finalize` | Validate `ItineraryResponse`/`ErrorResponse`, kiểm tra lại grounding và plan, tính latency, lưu conversation thành công rồi kết thúc graph. | Không gọi LLM; có thể ghi conversation store. | `END`; validation thất bại bị đổi thành `ITINERARY_VALIDATION_FAILED`. |

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
