# Dataset test case của Itinerary Agent: cấu trúc và cách bổ sung case

Phục vụ `docs/prd/test-plan.md` §2.4 (Tool Calling Accuracy ≥ 95%, Grounding Rate 100%, Structured
Output Integrity 100%) và FR-AGT-01..05, NFR-REL-01, NFR-SEC-01 trong `docs/prd/requirements.md`.

Dành cho người thêm hoặc sửa case trong `agent_test_cases_nhat.yaml`. Luật chấm tổng quát và lý do chọn cách chấm nằm ở
[golden-run.md](golden-run.md) mục 4; cách chạy và đọc kết quả ở [golden-run.md](golden-run.md).

| Thành phần | Đường dẫn |
|---|---|
| Dataset | `src/evaluation/datasets/agent_test_cases_nhat.yaml` (nguồn: `src/evaluation/agent/agent-test-cases-nhat.md`) |
| Runner | `src/evaluation/agent/golden.py` |
| Test của dataset và bộ chấm | `src/evaluation/tests/test_golden.py` |
| Biên bản | `src/evaluation/reports/eval-YYYY-MM-DD-agent-test-cases.md` |

## 1. Nguyên tắc: chỉ ghi điều luôn đúng

Bộ test case chạy trên catalog Postgres thật. Sản phẩm, giá và tình trạng còn chỗ đổi mỗi lần seed lại
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
- id: TC-NN                     # duy nhất trong file
  category: multi_turn           # nhóm case (mục 5); cũng thành tag trong LangSmith
  fr: [FR-AGT-01, FR-AGT-05]     # mã FR/NFR case này kiểm, lấy từ docs/prd/requirements.md
  turns:                         # mỗi phần tử là một lượt chat, chạy theo thứ tự
    - message: Phú Quốc 4 ngày cho gia đình, khởi hành {today+3}   # nêu ngày đi để không bị hỏi ngày
      expect:
        httpStatus: 200
        status: [COMPLETED, FALLBACK]
    - message: đổi khách sạn khác đi
      expect:
        httpStatus: 200
        excludeProductsFromTurn: {turn: 1, role: stay}
```

- `id`: dạng `TC-NN`, theo số thứ tự trong `agent-test-cases-nhat.md`. Không dùng lại id của case đã xoá, vì biên
  bản cũ và trace LangSmith còn tham chiếu tới nó.
- Mỗi lượt có thể thêm `language: en` (gửi `context.language`) và `conversationId` (ép id cho lượt đó,
  ví dụ id không tồn tại để kiểm `CONVERSATION_NOT_FOUND`).
- `turns`: một case có thể có nhiều lượt. Runner tự lấy `conversationId` từ response của lượt trước rồi
  gửi kèm lượt sau, giống frontend. Với lỗi có thể tiếp tục (nếu có), `conversationId` nằm trong
  `error.details` và runner cũng tự lấy; câu hỏi lại `NEEDS_CLARIFICATION` (kể cả giá trị không hợp lệ) có sẵn ở `conversationId`.
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
| `titleFirstLine` | `true`: dòng đầu câu trả lời (`question`/`message`/`error.message`) là `**Tiêu đề**` kèm phần chi tiết; `false`: không có (chào hỏi, cảm ơn). Không đặt cho case mà nhánh trả lời phụ thuộc LLM | `true` |
| `excludeProductsFromTurn` | `productId` của lượt `turn` (đếm từ 1) không xuất hiện lại ở lượt này; `role: stay` chỉ so chỗ ở, `role: any` so cả chỗ ở lẫn hoạt động | `{turn: 1, role: stay}` |
| `minActivities` | Tổng số slot có sản phẩm trong lịch ít nhất bằng số này. Chỉ dùng cho điểm đến catalog có nhiều điểm tham quan | `3` |
| `hasStay` | Lịch có hoặc không có chỗ ở | `false` |
| `warningsExclude` | Các `warnings[].code` này không được xuất hiện | `[PRODUCT_DROPPED_EXCLUDED]` |
| `toolsInclude` | Các tool này phải có trong `tool_plan` cuối của lượt (sau `validated_plan`; lời gọi bị server bỏ không tính) | `[get_similar_products]` |
| `judge` | Danh sách tiêu chí cho LLM giám khảo (golden-run.md mục 4); mỗi tiêu chí không đạt là một finding `[judge]`. Chỉ dùng cho điều khó viết thành luật (lời giải thích, câu thông báo); điều kiểm được bằng luật thì dùng khoá khác | `["Câu trả lời cho người dùng biết ngày đi đã đổi"]` |
| `formMatchesAnswer` | `true`: response có `clarificationForm`, và nếu câu trả lời nêu tên một điểm đến trong `suggestedValues.destination` thì form phải điền sẵn đúng điểm đến đó | `true` |

Giá trị hợp lệ:

- `status`: `COMPLETED`, `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK`.
- `errorCode`: một mã trong enum `ErrorCode` của `src/shared/contracts/schemas/common.yaml`.
- `missingFieldsInclude`: `destination`, `days`, `startDate`, `party`, `budget` (enum `missingFields` của
  `ItineraryNeedsClarification` trong contract).
- Tên node: `intake`, `classify`, `extract`, `tool`, `evaluate`, `retry`, `converse`, `compose`, `clarify`,
  `narrate`, `dead_letter`, `finalize`.
- Tên tool (`toolsInclude`): `search_products`, `get_recommendations`, `get_similar_products`.

Tab "📖 Hướng dẫn" của giao diện eval ([golden-run.md](golden-run.md) mục 2.1) liệt kê các giá trị này lấy thẳng từ
contract và graph, nên luôn khớp code. Hướng dẫn từng khoá nằm ở `FIELD_HELP` trong
`src/evaluation/agent/case_builder.py`; test buộc mọi khoá trong `EXPECT_KEYS` có hướng dẫn.
- `intent.destination` phải viết đúng tên catalog đã chuẩn hoá, ví dụ `TP. Hồ Chí Minh`, không viết
  `TPHCM`. Danh sách hiện hành lấy từ `GET /api/v1/destinations`.

Runner từ chối khoá lạ khi nạp dataset: gõ nhầm `missingField` thay vì `missingFieldsInclude` làm
`load_dataset` báo lỗi. Danh sách khoá hợp lệ nằm ở `TURN_KEYS` và `EXPECT_KEYS` trong `golden.py`.

## 5. Quy ước viết case

Mỗi case mô tả một lỗi người dùng tái hiện được; `category` là nhóm tự đặt (`snake_case`), cũng thành tag trong LangSmith.

**Lượt hỏi ngày đi.** Câu đầu chỉ có điểm đến và số ngày thì agent hỏi ngày đi, số người, ngân sách và chưa gọi tool.
Vì vậy hầu hết case bắt đầu bằng câu như vậy có hai lượt liền nhau: lượt hỏi (`status: [NEEDS_CLARIFICATION]`,
`missingFieldsInclude: [startDate]`, `toolCalled: false`) rồi lượt trả lời có **ngày đi và số người** (ví dụ
`đi từ {today+7}, 2 người lớn`); kỳ vọng kết quả nằm ở lượt trả lời. Từ đề xuất
`docs/prd/update-archive/2026-10-05-classify-route-clarify.md`, ngày đi và số người là trường bắt buộc: trả lời
`chưa chốt ngày đi` hay chỉ một phần thì agent hiện form, không lập lịch. Ngân sách không bắt buộc. Số lượt trong
`excludeProductsFromTurn` tính cả lượt hỏi. Case mới cần tới bước truy xuất thì làm theo cách này, hoặc nêu ngày đi và
số người ngay trong câu đầu (như nhóm `clear_request`).

**Lượt hỏi thiếu điểm đến/số ngày, không chốt được sau hai lượt.** Không giới hạn số lần hỏi lại từng làm hội thoại
kẹt vòng khi người dùng trả lời kiểu "bao nhiêu ngày cũng được" (LLM không trích được số). Từ đề xuất
`docs/prd/update-archive/2026-09-29-form-goi-y-thong-tin-chuyen-di.md` (đã áp dụng): lượt 1 hỏi bằng câu chữ như
bình thường; lượt 2 vẫn thiếu thì response có thêm `clarificationForm` thay vì hỏi lại y hệt. Runner chưa có khoá
`expect` kiểm trực tiếp `clarificationForm` — case kiểm gián tiếp bằng `missingFieldsInclude` giữ nguyên ở cả hai lượt
và `toolCalled: false` ở cả hai, để chứng minh agent không lặp vô hạn cũng không gọi tool khi thiếu thông tin
Lượt thứ ba mô
phỏng người dùng gửi câu hoàn chỉnh (frontend dựng từ form) như một câu chat bình thường.

**Ngày trong câu dùng placeholder.** Ngày cứng như "20/10" sẽ cũ đi theo thời gian và có thể rơi ra ngoài cửa sổ đặt chỗ 30 ngày
của catalog; cách nói tương đối như "tuần sau" thì LLM tự diễn giải nên không kiểm được ngày chính xác. Vì vậy dùng
placeholder, runner thay lúc chạy theo ngày ở Việt Nam (cùng nguồn với mốc `today` của agent, `vietnam_today`):

| Viết trong YAML | Ví dụ khi hôm nay là 25/09/2026 | Dùng ở đâu |
|---|---|---|
| `{today+7}` | `02/10/2026` | `message` — câu người dùng gõ |
| `{today+7:iso}` | `2026-10-02` | giá trị trong `expect`, ví dụ `intent: {startDate: "{today+7:iso}"}` |
| `{today}`, `{today-1}` | hôm nay, hôm qua | như trên; offset là tuỳ chọn và có thể âm |
| `{today+19:dm}` | `14/10` | `message` — ngày không năm, như người dùng thật gõ |
| `{today+19:vi}` | `14 tháng 10` | `message` — như trên, dạng chữ |

Giá trị có placeholder trong `expect` phải đặt trong dấu nháy kép (`"{today+7:iso}"`), vì `{` mở đầu là cú pháp map của YAML.
Chỉ dùng cho ngày trong vài tuần tới. Biên bản ghi câu đã thay, không ghi placeholder.

## 6. Chọn độ chặt của kỳ vọng

Kỳ vọng quá lỏng thì không bắt được lỗi; quá chặt thì fail vì những khác biệt vẫn hợp lệ.

- **Luồng có spec rõ thì khoá chặt.** Điểm đến ngoài catalog phải trả 422 theo
  [response-and-errors.md](response-and-errors.md), nên case loại này khoá `httpStatus: 422` và `errorCode`.
- **Luồng mà code cho phép nhiều nhánh hợp lệ thì chỉ khoá điều cốt lõi.** Câu hỏi thời tiết có thể ra
  400 (`out_of_domain`) hoặc 200 (`conversation`); PRD không quy định nhánh nào. Case loại này chỉ khoá
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

**Cách nhanh: tab "➕ Thêm case" của giao diện eval** (`make agent-eval`, [golden-run.md](golden-run.md) mục 2.1).

- Bắt đầu từ trống, hoặc chọn một case có sẵn rồi bấm "Nạp mẫu" để sửa từ đó.
- Id `TC-NN` được gợi ý sẵn. Điền nhóm, mã FR và lỗi gốc; lỗi gốc thành comment phía trên case.
- Mỗi lượt: câu người dùng gõ, kèm bản đã thay ngày theo hôm nay; tick khoá `expect` cần kiểm. Rê chuột vào ⓘ để xem
  khoá kiểm gì, khi nào dùng, ví dụ.
- Xem YAML sẽ ghi; có chế độ sửa YAML thô.
- **Kiểm tra** chạy đúng `load_dataset` của runner cộng các kiểm của `test_golden.py`: id trùng, mã FR, status,
  errorCode, placeholder ngày, khoá gõ sai tên. Kiểm tra cũng cảnh báo id từng bị xoá và điểm đến không có trong
  catalog.
- **Lưu vào dataset** chỉ nối khối mới vào cuối file; comment của các case cũ giữ nguyên.
- **Chạy thử** chạy riêng case đó.

Sửa hoặc xoá case cũ vẫn làm trực tiếp trong file YAML. Sau khi lưu, vẫn làm bước 2, 5, 6 dưới đây trước khi commit.

**Cách thủ công:**

1. Thêm khối YAML vào cuối file dataset, với `id` tiếp theo (không dùng lại id đã xoá), `category` và `fr`.
2. Chạy test của dataset:

   ```bash
   .venv/bin/python -m pytest src/evaluation/tests/test_golden.py -q
   ```

   Test kiểm id không trùng, mã `fr` đúng định dạng, `status` và `errorCode` thuộc enum của contract.
   Test **không** kiểm tên khoá `expect` (xem cảnh báo ở mục 4).
3. Chạy riêng case mới vài lần với LLM thật, kèm trace:

   ```bash
   .venv/bin/python -m src.evaluation.agent.golden --only TC-10 --trace-project claude-golden
   ```

   Cần Postgres đã seed và backend chạy với `ITINERARY_DATA_MODE=http`. Backend phải khởi động xong recsys
   (log `startup.recsys.index.load.ready`); nếu recsys tắt thì mọi case đều ra sai.
4. Nếu fail, xác định lỗi nằm ở đâu trước khi sửa (mục 8).
5. Chạy lại toàn bộ bộ test case trước khi commit, và commit biên bản `.md` cùng với dataset:

   ```bash
   .venv/bin/python -m src.evaluation.agent.golden --sweep --trace-project claude-golden
   ```

6. Tạo entry trong `history/` theo AGENTS.md §5.

## 8. Khi case mới fail

Biên bản `.md` liệt kê từng lượt fail kèm lý do. Trace trên LangSmith đặt tên `TC-01#1 <câu nhập>`,
gắn tag `golden`, id case và category; mở node `classify` để xem nhãn phân luồng, node `extract` để xem LLM trích ra gì, node `tool` để xem
tool plan.

Có ba khả năng:

- **Kỳ vọng sai:** code và PRD cho phép kết quả đó. Sửa dataset, ghi lý do bằng comment YAML ngay trên
  khoá .
- **Lỗi agent:** agent làm sai điều PRD yêu cầu. Giữ nguyên kỳ vọng, ghi lỗi vào `history/`; sửa code theo
  quy trình AGENTS.md.
- **Nhiễu của LLM:** cùng câu nhập, lúc pass lúc fail. Dùng `--repeat 5` để đo tỷ lệ. Không nới kỳ vọng
  chỉ vì fail ngẫu nhiên nếu luồng đó có spec; tỷ lệ fail là tín hiệu chất lượng thật.

Với case nhiều lượt fail ở lượt 2, kiểm lượt 1 trước: lượt 1 sai thì lượt 2 thường sai theo.

## 9. Giới hạn hiện tại của schema

- **Chưa khai báo được `intentOverride`** (chip người dùng sửa tay trên UI).
- **Chưa kiểm tham số chi tiết của tool plan.** Tool Calling Accuracy chỉ đo quyết định gọi hay không gọi
  tool; độ đúng của điểm đến được kiểm gián tiếp qua `intent.destination` và grounding.

Muốn thêm khoá mới vào `expect`: sửa `dataset_findings` trong `golden.py`, thêm test cho khoá đó trong
`test_golden.py`, thêm hướng dẫn vào `FIELD_HELP`/`EXPECT_GROUPS` và widget trong `eval_app.py`, rồi cập nhật bảng ở
mục 4 của tài liệu này.
