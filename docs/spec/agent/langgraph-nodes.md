# LangGraph: mười node và vì sao chia như vậy

Agent lập lịch trình là một LangGraph gồm mười node. Tài liệu này giải thích **ý đồ** của cách chia đó — đọc xong bạn nói lại được cho người khác mà không cần mở code. Xem [README](README.md) để chạy demo.

Một lượt gọi API đi qua ba việc: **hiểu người dùng muốn gì**, **lấy sản phẩm thật từ catalog**, và **soạn câu trả lời**. Mỗi node lo một mẩu của ba việc đó, và tất cả cùng đọc/ghi vào một state chung.

## 1. Bốn giai đoạn

Đừng nhớ mười node rời rạc. Nhớ bốn giai đoạn, mỗi giai đoạn trả lời một câu hỏi:

| Giai đoạn | Node | Câu hỏi nó trả lời |
|---|---|---|
| Hiểu người dùng | `intake`, `classify` | Người dùng muốn gì, và đã đủ thông tin chưa? |
| Lấy dữ liệu thật | `tool`, `evaluate`, `retry` | Có sản phẩm thật nào dùng được không? |
| Soạn câu trả lời | `converse`, `compose`, `clarify`, `dead_letter` | Nói gì với người dùng? |
| Cửa ra chung | `finalize` | Câu trả lời này có an toàn để gửi đi không? |

Giai đoạn 3 có bốn node vì có đúng bốn tình huống cần nói với người dùng:

- `converse` — **trò chuyện**: chào hỏi, cảm ơn, hoặc từ chối yêu cầu ngoài phạm vi. Chưa đụng tới sản phẩm.
  Xin lên lịch trình mà chưa nói điểm đến hay số ngày **không** thuộc nhóm này — đó vẫn là yêu cầu du lịch, đi `clarify`.
- `compose` — **dựng kết quả**: đã có sản phẩm thật, xếp thành lịch trình.
- `clarify` — **hỏi thêm**: thiếu điểm đến hoặc số ngày, thông tin mâu thuẫn, hoặc điều kiện bắt buộc không có sản phẩm nào đáp ứng.
- `dead_letter` — **hỏng có kiểm soát**: lỗi auth, điểm đến ngoài catalog, tool hỏng vĩnh viễn. Trả lỗi đúng chuẩn thay vì che thành thành công.

**Node nào gọi LLM:** chỉ `classify`, `tool` (bước chọn tên điểm đến theo catalog), `converse` và `clarify`. Đây là chỗ hay bị hiểu sai — **`compose` không gọi LLM**, nó xếp lịch bằng quy tắc cố định (mục 5).

## 2. Vì sao mọi nhánh đều đi qua `finalize`

Nhìn sơ đồ sẽ thấy `converse`, `compose`, `clarify` và `dead_letter` đều trỏ vào `finalize`. Đây không phải trùng lặp mà là chủ ý: **graph có nhiều đường vào nhưng chỉ một đường ra.**

Bốn node kia đều *soạn* response, nhưng **không node nào được tự trả response đó ra ngoài**. Tất cả phải qua `finalize`.

### `finalize` làm gì

Những việc phải xảy ra **đúng một lần cho mọi response, bất kể đi nhánh nào**:

| Việc | Vì sao phải đặt ở cửa ra chung |
|---|---|
| Kiểm schema OpenAPI | Client sinh từ OpenAPI sẽ vỡ nếu bất kỳ nhánh nào trả sai hình dạng |
| Kiểm grounding (`validate_plan`) | Mọi sản phẩm phải có trong `candidates`. Đây là cam kết grounding 100% — không được có một nhánh nào lách qua |
| Đo `latency_ms` | Chỉ đo được ở điểm cuối cùng |
| Lưu hội thoại | Lượt sau còn nhớ intent, bất kể lượt này kết thúc thế nào |
| Sinh `final_answer` | Một chỗ duy nhất quyết định text hiển thị cho người dùng |

Cách để nhớ: **giống cổng an ninh sân bay.** Khách đến từ nhiều quầy check-in khác nhau, nhưng mọi người đều phải qua đúng một cổng soi chiếu. Lắp máy soi ở từng quầy thì vừa tốn, vừa chắc chắn có quầy quên lắp.

### Nếu không có `finalize` thì sao

Mỗi node phải tự kiểm lấy. Hai hậu quả:

1. Logic kiểm bị lặp bốn lần, sửa một quy tắc phải sửa bốn chỗ.
2. Nguy hiểm hơn: thêm một node mới mà quên copy phần kiểm là có ngay một đường thoát không ai canh. Với cam kết grounding 100%, đây đúng là loại lỗi không được phép mắc.

### `finalize` có quyền phủ quyết

Điểm dễ nhầm nhất: `finalize` **không chỉ đóng dấu**. Nó có quyền bác.

Một response `COMPLETED` không qua được `validate_plan` sẽ bị nó thay bằng lỗi `ITINERARY_VALIDATION_FAILED` (HTTP 500). Nghĩa là backend tự nhận lỗi của mình, thay vì đưa cho người dùng một lịch trình chưa được kiểm chứng. Thà báo lỗi còn hơn trả dữ liệu không có căn cứ.

## 3. Bảy ví dụ

Đi từ câu người dùng gõ, không phải từ tên node:

| Người dùng gõ | Đường đi | Ý được minh họa |
|---|---|---|
| "chào bạn" | `intake → classify → converse → finalize` | Trò chuyện, chưa đụng tới sản phẩm |
| "đi 3 ngày" (thiếu điểm đến) | `intake → classify → clarify → finalize` | Thiếu thông tin thì hỏi, không đoán |
| "gợi ý cho tôi một chuyến đi" | `intake → classify → clarify → finalize` | Chưa nói gì vẫn là yêu cầu du lịch, không phải trò chuyện |
| "Nha Trang 2 ngày" | `intake → classify → tool → evaluate → compose → finalize` | Luồng đầy đủ |
| "Paris 2 ngày" | `intake → classify → tool → evaluate → dead_letter → finalize` | Ngoài catalog, dừng trước khi gọi Search |
| "Nha Trang 2 ngày, khách sạn 5 sao" (không có) | `… → evaluate → clarify → finalize` | Điều kiện bắt buộc không đạt thì hỏi, không tự bỏ |
| Search lỗi mạng | `… → evaluate → retry → tool → evaluate → …` | Thử lại, tối đa một lần |

**Bảy tình huống khác hẳn nhau, nhưng cột nào cũng kết thúc bằng `finalize`.** Đó là mục 2 nhìn từ phía dữ liệu thật.

Sơ đồ đầy đủ:

```text
START → intake → classify
  ├─ đủ destination + days
  │    → tool → evaluate
  │       ├─ có candidate hợp lệ → compose → finalize → END
  │       ├─ không có kết quả → compose (NO_RESULTS) → finalize → END
  │       ├─ vi phạm điều kiện bắt buộc → clarify → finalize → END
  │       ├─ lỗi tạm thời → retry → tool (tối đa một lần)
  │       └─ lỗi vĩnh viễn/auth → dead_letter → finalize → END
  ├─ thiếu destination/days, mâu thuẫn, hoặc điều kiện không xác minh được
  │    → clarify → finalize → END
  ├─ chào hỏi, cảm ơn, hoặc yêu cầu ngoài phạm vi (không gồm yêu cầu du lịch thiếu chi tiết)
  │    → converse → finalize → END
  └─ request lỗi hoặc LLM classify lỗi
       → dead_letter → finalize → END
```

## 4. Đọc bảng trace của Streamlit

Bảng bên phải màn hình demo là trace của **một lượt gọi API qua SSE**, theo đúng thứ tự event backend phát ra. Mỗi dòng là một node đã kết thúc; bảng không hiển thị raw state, prompt, token, JWT hay payload nội bộ.

| Cột | Cách đọc |
|---|---|
| `sequence` | Thứ tự event trong lượt chạy, bắt đầu từ 1. Không phải số thứ tự cố định của node trong mọi luồng. |
| `nodeId` | Tên node vừa hoàn tất. Node không đi qua trong lượt này sẽ không có dòng. |
| `outcome` | Trạng thái thực thi. `completed` chỉ có nghĩa node đã chạy xong; **kết quả nghiệp vụ vẫn phải xem response**. |
| `message` | Tóm tắt việc node vừa làm. Ví dụ `tool` ghi `retrieval completed (normalized destination)` khi tên điểm đến được đổi thành tên catalog. |
| `durationMs` | Thời gian quan sát từ event node trước tới event hiện tại **tại biên SSE**, gồm cả overhead cập nhật state. Đây không phải CPU profile bên trong node. Tối thiểu 1 ms. |

Các điểm cần nhớ khi đọc trace:

- Không thấy `tool` nghĩa là agent **chưa truy xuất sản phẩm nào**; thường do thiếu `destination`/`days` (đi qua `clarify`), trò chuyện hoặc bị từ chối (đi qua `converse`).
- Thấy `converse` thì chắc chắn lượt đó **không có sản phẩm nào**; thấy `compose` thì chắc chắn **đã có dữ liệu thật**. Đây là lợi ích của việc tách hai node.
- `compose` không đồng nghĩa với `COMPLETED`: nó còn tạo `NO_RESULTS` và `FALLBACK`.
- `compose` không gọi LLM nên `durationMs` của nó chỉ vài mili giây, và cùng một tập candidate luôn cho cùng một lịch trình.
- Có `retry` nghĩa là retrieval gặp lỗi tạm thời; graph chỉ cho retry một lần để tránh vòng lặp vô hạn.
- Chỉ `run.completed.response` và kết quả ở `finalize` mới cho biết trạng thái API cuối cùng. `completed` ở từng node **không phải** kết luận PASS của evaluation.
- Trace chạy fixture chỉ chứng minh luồng local và grounding vào fixture; **không** chứng minh availability, giá hiện tại, chất lượng Search hay latency production.

## 5. Quy tắc xếp lịch của `compose`

`compose_plan` trong `src/backend/app/domain/itinerary/planning.py` chọn sản phẩm và xếp ngày bằng thứ tự
xác định, không có LLM. Cùng một tập candidate luôn cho cùng một lịch trình.

1. Chỉ xét candidate `available=true` thuộc `hotel`, `attraction`, `golf`. `flight` và `combo` vẫn được
   truy xuất và vẫn hiện trong `searchResults` của `FALLBACK`, nhưng không bao giờ vào slot.
2. **Chỗ ở:** chọn một `hotel`, ưu tiên giá thấp nhất; bằng giá thì sao cao hơn; bằng nữa thì `productId`
   nhỏ hơn. Giá `null` xếp cuối vì không so sánh được. Không bao giờ chọn cả phòng con lẫn khách sạn cha.
3. **Hoạt động:** hoạt động nguyên ngày (`durationMinutes >= 360`) được xếp trước và chiếm trọn một ngày.
   Phần còn lại xếp theo giá thấp nhất rồi `productId`.
4. **Rải ngày:** mỗi hoạt động vào ngày đang ít việc nhất, ngày sớm hơn thắng khi hòa. Tối đa
   2 hoạt động một ngày; hoạt động đầu vào `MORNING`, hoạt động thứ hai vào `AFTERNOON`.
5. Hoạt động dư so với sức chứa của chuyến thì không xếp, không dồn.
6. Ngày không có sản phẩm nào thì `slots` rỗng và response kèm warning `DAY_WITHOUT_PRODUCTS`.
   Không sinh slot bữa ăn/nghỉ ngơi `product=null`.

`pace` chưa phải đầu vào của bước xếp lịch; trần 2 hoạt động/ngày áp dụng cho mọi `pace`.
`render_proposal` và `validate_plan` vẫn là tiếng nói cuối cùng: nếu đề xuất tự sinh mà không qua được
hai hàm này thì đó là lỗi backend, `compose` trả `FALLBACK` và ghi log `itinerary.composition_failed`.

## 6. Bảng tra cứu mười node

Dùng khi đã nắm bức tranh chung ở trên và cần tra chi tiết một node.

| Node | Nhận vào | Trả ra | Đi tiếp |
|---|---|---|---|
| `intake` | Message của người dùng, `conversationId` (nếu có). | State khởi tạo: message đã chuẩn hóa, `conversationId`, intent đã lưu của hội thoại. | `classify` |
| `classify` | Message và intent đã lưu. **Gọi LLM.** | Intent/constraints (`destination`, `days`...), các trường còn thiếu, cờ trò chuyện hoặc yêu cầu bị từ chối. | `tool` nếu đủ `destination` + `days`; `clarify` nếu thiếu thông tin, mâu thuẫn hoặc có điều kiện không xác minh được; `converse` nếu chào hỏi hoặc bị từ chối; `dead_letter` nếu lỗi. |
| `tool` | Intent/constraints. **Có thể gọi LLM** để khớp tên điểm đến với catalog. | Tên điểm đến đã chuẩn hóa, kết quả Search/Recommendation/ProductDetail (hoặc lỗi) trong `tool_results`. Điểm đến ngoài catalog trả `UNSUPPORTED_DESTINATION` (422) kèm danh sách điểm đến hỗ trợ. | `evaluate` |
| `evaluate` | `tool_results` và intent. | Danh sách candidate hợp lệ có nguồn grounding, hoặc phân loại: `compose`, `no_results`, `fallback`, `constraint_clarification`, lỗi tạm thời/vĩnh viễn. | `compose`, `clarify` (khi `constraint_clarification`), `retry` hoặc `dead_letter` |
| `retry` | Lỗi tool tạm thời và số lần đã thử. | Quyết định thử lại (tối đa một lần), dùng fallback hoặc báo lỗi. | `tool`, `compose` hoặc `dead_letter` |
| `converse` | Message của người dùng, loại tương tác, cờ từ chối. **Gọi LLM.** | Câu trả lời trò chuyện (`NEEDS_CLARIFICATION` kèm `missingFields`), hoặc từ chối (`VALIDATION_ERROR`, HTTP 400). LLM lỗi thì dùng câu cố định. | `finalize` |
| `compose` | Candidate đã evaluate (chỉ `hotel`, `attraction`, `golf`). **Không gọi LLM.** | Lịch trình `COMPLETED` dựng bằng `compose_plan`, hoặc `NO_RESULTS`, `FALLBACK`. | `finalize` |
| `clarify` | Trường còn thiếu (`missing_fields`), `clarification_reason` (`conflict`/`unverified`), hoặc `decision = constraint_clarification`. **Gọi LLM** để viết câu hỏi — riêng `constraint_clarification` dùng câu cố định. | `NEEDS_CLARIFICATION` kèm `knownIntent` (và `missingFields` nếu có). LLM lỗi hoặc timeout thì dùng câu cố định theo đúng lý do. | `finalize` |
| `dead_letter` | Lỗi auth, tool plan/argument hoặc upstream. | `ErrorResponse` chuẩn, không che lỗi thành thành công. | `finalize` |
| `finalize` | Response từ một trong bốn node soạn. | Response cuối đã validate schema và grounding, kèm latency; lưu conversation nếu thành công. Validation lỗi thành `ITINERARY_VALIDATION_FAILED`. | `END` |
