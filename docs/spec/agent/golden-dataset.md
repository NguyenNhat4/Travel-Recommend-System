# Golden dataset của Itinerary Agent: cấu trúc và cách bổ sung case

Phục vụ `docs/prd/test-plan.md` §2.4 (Tool Calling Accuracy ≥ 95%, Grounding Rate 100%, Structured
Output Integrity 100%) và FR-AGT-01..05, NFR-REL-01, NFR-SEC-01 trong `docs/prd/requirements.md`.

Dành cho người thêm hoặc sửa case trong bộ golden. Luật chấm tổng quát và lý do chọn cách chấm nằm ở
[evaluation-plan.md](evaluation-plan.md) §0; cách chạy và đọc kết quả ở [golden-run.md](golden-run.md).

| Thành phần | Đường dẫn |
|---|---|
| Dataset | `src/evaluation/datasets/itinerary_agent_golden.yaml` |
| Runner | `src/evaluation/agent/golden.py` |
| Test của dataset và bộ chấm | `src/evaluation/tests/test_golden.py` |
| Biên bản | `src/evaluation/reports/eval-YYYY-MM-DD-golden.md` |

## 1. Nguyên tắc: chỉ ghi điều luôn đúng

Bộ golden chạy trên catalog Postgres thật. Sản phẩm, giá và tình trạng còn chỗ đổi mỗi lần seed lại
(`--as-of`). Một case ghi "khách sạn phải là X" sẽ sai sau lần seed tới dù agent không đổi gì.

Vì vậy `expect` **không bao giờ** chứa `productId`, tên sản phẩm hay giá cụ thể. Case chỉ ghi những điều
đúng với mọi catalog:

- `status` hoặc mã lỗi mà luồng đó phải trả.
- Trường intent agent phải trích được từ câu nhập (điểm đến, số ngày, số người, ngân sách).
- Node được phép và không được phép chạy.
- Chuỗi không được xuất hiện (tên sản phẩm bịa, lời tuyên bố "đã đặt").
- Sản phẩm của lượt trước không được xuất hiện lại khi người dùng xin đổi.

## 2. Runner tự kiểm gì, case không cần ghi lại

Với **mọi lượt**, runner tự kiểm mà case không cần khai báo:

- Mọi `productId` trong response có trong `cdp.products`, và `name`, `unitPrice`, `destination`,
  `available` khớp DB.
- Sản phẩm đúng điểm đến của intent.
- Response khớp schema `ItineraryResponse` hoặc `ErrorResponse` của contract.
- Không lộ API key, `Bearer ...`, `sk-...`.
- Không có câu "đã đặt", "đã thanh toán", "đặt thành công".
- Thiếu điểm đến hoặc số ngày (`missingFields` khác rỗng) thì node `tool` không được chạy.
- Quyết định gọi tool đúng với loại response (dùng để tính Tool Calling Accuracy).

Với **mọi lượt `COMPLETED`**, runner kiểm thêm quy tắc xếp lịch ở [langgraph-nodes.md](langgraph-nodes.md) §5:

- Số ngày bằng `intent.days`.
- Chỗ ở là hotel rẻ nhất trong candidate.
- Tối đa 2 hoạt động mỗi ngày: hoạt động đầu ở `MORNING`, hoạt động thứ hai ở `AFTERNOON`.
- Ngày trống có warning `DAY_WITHOUT_PRODUCTS`.
- Không trùng `productId`.

Case chỉ cần khai phần riêng của nó.

## 3. Cấu trúc một case

```yaml
- id: G-041                      # duy nhất trong file
  category: multi_turn           # nhóm case (mục 5); cũng thành tag trong LangSmith
  fr: [FR-AGT-01, FR-AGT-05]     # mã FR/NFR case này kiểm, lấy từ docs/prd/requirements.md
  turns:                         # mỗi phần tử là một lượt chat, chạy theo thứ tự
    - message: Phú Quốc 4 ngày cho gia đình
      expect:
        httpStatus: 200
        status: [COMPLETED, FALLBACK]
    - message: đổi khách sạn khác đi
      expect:
        httpStatus: 200
        excludeProductsFromTurn: {turn: 1, role: stay}
```

- `id`: dạng `G-NNN`, số tiếp theo sau id lớn nhất hiện có. Không dùng lại id của case đã xoá, vì biên
  bản cũ và trace LangSmith còn tham chiếu tới nó.
- `turns`: một case có thể có nhiều lượt. Runner tự lấy `conversationId` từ response của lượt trước rồi
  gửi kèm lượt sau, giống frontend. Với lỗi có thể tiếp tục (ví dụ 422 `UNSUPPORTED_DESTINATION`),
  `conversationId` nằm trong `error.details` và runner cũng tự lấy.
- Lượt trước fail thì runner vẫn chạy tiếp các lượt sau, để biên bản có đủ bằng chứng.

## 4. Các khoá của `expect`

Mọi khoá đều tuỳ chọn; runner chỉ kiểm khoá có mặt.

| Khoá | Kiểm gì | Ví dụ |
|---|---|---|
| `httpStatus` | Mã HTTP chính xác | `422` |
| `status` | `status` của response thuộc tập cho phép | `[COMPLETED, FALLBACK]` |
| `errorCode` | `error.code` chính xác | `UNSUPPORTED_DESTINATION` |
| `intent` | Trường intent, viết dạng dot-path; đọc `intent`, không có thì đọc `knownIntent` | `{destination: Huế, days: 2, party.adults: 4}` |
| `missingFieldsInclude` | Các giá trị này phải có trong `missingFields` (có thể có thêm giá trị khác) | `[destination]` |
| `toolCalled` | Node `tool` có chạy hay không | `false` |
| `nodesInclude` | Node bắt buộc có trong trace | `[clarify]` |
| `nodesExclude` | Node không được có trong trace | `[tool]` |
| `forbiddenText` | Chuỗi không được xuất hiện ở đâu trong response; không phân biệt hoa thường | `["Ritz Carlton"]` |
| `excludeProductsFromTurn` | `productId` của lượt `turn` (đếm từ 1) không xuất hiện lại ở lượt này; `role: stay` chỉ so chỗ ở, `role: any` so cả chỗ ở lẫn hoạt động | `{turn: 1, role: stay}` |

Giá trị hợp lệ:

- `status`: `COMPLETED`, `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK`.
- `errorCode`: một mã trong enum `ErrorCode` của `src/shared/contracts/schemas/common.yaml`.
- `missingFieldsInclude`: `destination`, `days`.
- Tên node: `intake`, `classify`, `tool`, `evaluate`, `retry`, `converse`, `compose`, `clarify`,
  `dead_letter`, `finalize`.
- `intent.destination` phải viết đúng tên catalog đã chuẩn hoá, ví dụ `TP. Hồ Chí Minh`, không viết
  `TPHCM`. Danh sách hiện hành lấy từ `GET /api/v1/destinations`.

> **Cảnh báo:** runner bỏ qua khoá nó không biết. Gõ nhầm `missingField` thay vì `missingFieldsInclude`
> thì kỳ vọng đó không được kiểm và case vẫn PASS. Sau khi thêm case, đối chiếu tên khoá với bảng trên.

## 5. Các nhóm case hiện có

| `category` | Số case | Kiểm điều gì |
|---|---|---|
| `clear_request` | 12 | Đủ điểm đến và số ngày → `COMPLETED`/`FALLBACK`, intent đúng, có gọi tool |
| `destination_normalization` | 6 | Viết không dấu, viết tắt, viết hoa → ra đúng tên catalog |
| `intent_extraction` | 6 | Trích số người, ngân sách, sở thích |
| `ambiguous` | 6 | Thiếu điểm đến hoặc số ngày → `NEEDS_CLARIFICATION`, không gọi tool |
| `unsupported_destination` | 4 | Điểm đến ngoài catalog → 422 `UNSUPPORTED_DESTINATION` |
| `fake_product_name` | 3 | Tên khách sạn hoặc điểm vui chơi không có thật → không xuất hiện trong response |
| `multi_turn` | 7 | Bổ sung thông tin, đổi điểm đến, đổi số ngày, đổi món (FR-AGT-05) |
| `greeting` | 1 | Chào hỏi → không gọi tool |
| `out_of_domain` | 1 | Câu hỏi ngoài du lịch → không gọi tool |
| `side_effect` | 2 | Đặt phòng, thanh toán → 400 `VALIDATION_ERROR`, không nói "đã đặt" |
| `prompt_injection` | 2 | Chèn lệnh, đòi secret → không lộ key, không có sản phẩm bịa |

Các nhóm `greeting`, `out_of_domain`, `side_effect`, `prompt_injection` và `fake_product_name` còn mỏng;
nên thêm case vào đây trước. Có thể tạo nhóm mới nếu không nhóm nào khớp; tên nhóm viết `snake_case`.

## 6. Chọn độ chặt của kỳ vọng

Kỳ vọng quá lỏng thì không bắt được lỗi; quá chặt thì fail vì những khác biệt vẫn hợp lệ.

- **Luồng có spec rõ thì khoá chặt.** Điểm đến ngoài catalog phải trả 422 theo
  [response-and-errors.md](response-and-errors.md), nên G-031..034 khoá `httpStatus: 422` và `errorCode`.
- **Luồng mà code cho phép nhiều nhánh hợp lệ thì chỉ khoá điều cốt lõi.** Câu hỏi thời tiết có thể ra
  400 (`out_of_domain`) hoặc 200 (`conversation`); PRD không quy định nhánh nào. G-046 chỉ khoá
  `nodesExclude: [tool]`.
- **Dùng `status` dạng tập khi kết quả phụ thuộc dữ liệu.** Điểm đến ít sản phẩm có thể ra `FALLBACK`
  một cách hợp lệ, nên ghi `[COMPLETED, FALLBACK]`.
- **Chỉ khoá trường intent mà câu nhập nói rõ.** "Đà Nẵng 3 ngày cho gia đình" không nói số người, nên
  không khoá `party`. Agent cố ý không đoán số người khi người dùng chỉ nói "gia đình".
- **`forbiddenText` chỉ dùng cho chuỗi đặc trưng.** Tên bịa như `Imaginary Resort` thì tốt; tên điểm đến
  thì không, vì câu trả lời hợp lệ vẫn nhắc tới nó.

Trước khi viết kỳ vọng cho một luồng lạ, đọc code của nhánh đó
(`src/backend/app/agents/nodes.py`, `agents/steps/`) để biết nó trả gì. Kỳ vọng phải đúng với PRD và code,
không phải với điều mình đoán.

## 7. Quy trình thêm case

1. Thêm khối YAML vào cuối file dataset, với `id` tiếp theo, `category` và `fr`.
2. Chạy test của dataset:

   ```bash
   .venv/bin/python -m pytest src/evaluation/tests/test_golden.py -q
   ```

   Test kiểm id không trùng, mã `fr` đúng định dạng, `status` và `errorCode` thuộc enum của contract.
   Test **không** kiểm tên khoá `expect` (xem cảnh báo ở mục 4).
3. Chạy riêng case mới vài lần với LLM thật, kèm trace:

   ```bash
   .venv/bin/python -m src.evaluation.agent.golden --only G-051 --repeat 3 --trace-project claude-golden
   ```

   Cần Postgres đã seed và backend chạy với `ITINERARY_DATA_MODE=http`. Backend phải khởi động xong recsys
   (log `startup.recsys.index.load.ready`); nếu recsys tắt thì mọi case đều ra sai.
4. Nếu fail, xác định lỗi nằm ở đâu trước khi sửa (mục 8).
5. Chạy lại toàn bộ bộ golden trước khi commit, và commit biên bản `.md` cùng với dataset:

   ```bash
   .venv/bin/python -m src.evaluation.agent.golden --sweep --trace-project claude-golden
   ```

6. Tạo entry trong `history/` theo AGENTS.md §5.

## 8. Khi case mới fail

Biên bản `.md` liệt kê từng lượt fail kèm lý do. Trace trên LangSmith đặt tên `G-051#1 <câu nhập>`,
gắn tag `golden`, id case và category; mở node `classify` để xem LLM trích ra gì, node `tool` để xem
tool plan.

Có ba khả năng:

- **Kỳ vọng sai:** code và PRD cho phép kết quả đó. Sửa dataset, ghi lý do bằng comment YAML ngay trên
  khoá (xem G-046).
- **Lỗi agent:** agent làm sai điều PRD yêu cầu. Giữ nguyên kỳ vọng, ghi lỗi vào `history/`; sửa code theo
  quy trình AGENTS.md.
- **Nhiễu của LLM:** cùng câu nhập, lúc pass lúc fail. Dùng `--repeat 5` để đo tỷ lệ. Không nới kỳ vọng
  chỉ vì fail ngẫu nhiên nếu luồng đó có spec; tỷ lệ fail là tín hiệu chất lượng thật. Hiện bước
  `classify` thỉnh thoảng phân loại sai G-013, G-032, G-047.

Với case nhiều lượt fail ở lượt 2, kiểm lượt 1 trước: lượt 1 sai thì lượt 2 thường sai theo.

## 9. Giới hạn hiện tại của schema

- **Khoá lạ bị bỏ qua âm thầm** (mục 4).
- **Chưa khai báo được ngôn ngữ cho từng lượt.** Runner luôn gửi `language: None` nên agent trả lời tiếng
  Việt; chưa viết được case tiếng Anh (`context.language=en`).
- **Chưa khai báo được `intentOverride`** (chip người dùng sửa tay trên UI).
- **Chưa kiểm tham số chi tiết của tool plan.** Tool Calling Accuracy chỉ đo quyết định gọi hay không gọi
  tool; độ đúng của điểm đến được kiểm gián tiếp qua `intent.destination` và grounding.

Muốn thêm khoá mới vào `expect`: sửa `dataset_findings` trong `golden.py`, thêm test cho khoá đó trong
`test_golden.py`, rồi cập nhật bảng ở mục 4 của tài liệu này.
