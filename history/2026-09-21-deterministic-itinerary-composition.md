# Bỏ LLM khỏi bước xếp lịch, chuyển sang quy tắc tất định

- Ngày: 2026-09-21
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, docs

## Mục tiêu

Nguồn bất ổn định lớn nhất của agent là node `answer`: LLM chọn sản phẩm nào vào ngày nào. Cùng một câu hỏi
cho ra lịch trình khác nhau mỗi lần chạy, và một lựa chọn sai từng làm hỏng cả lịch trình
(`history/2026-09-20-keep-valid-slots-when-composition-breaks-a-rule.md`). Yêu cầu: backend tự xếp lịch bằng
quy tắc, LLM không còn tham gia bước này.

Điểm khiến việc này rẻ hơn tưởng: LLM ở bước composition **không viết chữ nào**. Nó chỉ trả `stay_id`, danh sách
slot và một `note_kind` thuộc enum cố định; câu trả lời hiển thị cho người dùng vốn đã được `finalize_node` dựng
bằng template (`"Lịch trình tham khảo: " + tên sản phẩm`). Bỏ lời gọi này không mất một câu văn nào.

## File thay đổi

- `src/backend/app/domain/itinerary/planning.py` — thêm: hằng `MAX_ACTIVITIES_PER_DAY`; các hàm sắp thứ tự
  `_parent_key`, `_price_key`, `_stay_order`, `_activity_order`; hàm `compose_plan(candidates, intent)` dựng
  proposal tất định. Xóa: `render_best_effort` (chỉ tồn tại để chữa đề xuất hỏng của LLM, nay không còn đầu vào).
- `src/backend/app/agents/nodes.py` — sửa: `_composed(state)` bỏ tham số kết quả LLM, gọi `compose_plan` rồi
  `render_proposal`; thêm `_compose_or_fallback` và `_answer_message`; `answer_node`/`answer_node_async` bỏ lời gọi
  LLM ở nhánh lập lịch; bỏ `"llm_used": True` khỏi response `COMPLETED`; docstring module. Xóa: `COMPOSE_PROMPT`,
  `_composition_input`, warning `SLOT_DROPPED_UNSCHEDULABLE`.
- `src/backend/app/agents/models.py` — xóa: `Composition`, `ProposedSlot`, và hai alias `SlotTime`/`ActivityType`
  cùng `DAYS_MIN`/`DAYS_MAX` chỉ phục vụ hai model đó.
- `src/backend/tests/unit/test_itinerary_composition.py` — thêm: 11 test cho `compose_plan` (thứ tự chọn chỗ ở,
  cha/con, rải ngày, hoạt động nguyên ngày, trần mỗi ngày, tính tất định, đề xuất luôn qua được renderer/validator).
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: `ScriptedLlm` bỏ `composition`/`fail_composition`
  và **raise** nếu có ai gọi model bằng schema khác `Extraction`/`DestinationChoice`/`ConversationalAnswer`; viết lại
  6 test bám hành vi mới; thêm `test_the_itinerary_path_never_asks_the_model_to_pick_products`,
  `test_only_retrieved_products_can_reach_a_slot`, `test_nothing_schedulable_falls_back_to_the_real_products`.
- `src/backend/tests/unit/agents/test_contract_derived_models.py` — sửa: bỏ assertion về `ProposedSlot`,
  `SlotTime`, `ActivityType` đã xóa.
- `docs/agent/langgraph-nodes.md` — sửa: bảng node `answer`, ví dụ trace, ghi chú đọc trace; thêm mục
  "Quy tắc xếp lịch của `answer`" liệt kê 6 quy tắc.
- `docs/agent/evaluation-plan.md` — sửa: §1 nêu luồng `COMPLETED` còn 2 lời gọi LLM; §2 đổi tiêu chí ổn định
  từ "≥ 80% cùng status" thành "100% cùng status và cùng danh sách productId"; §4 case 04 thêm kỳ vọng chọn hotel
  rẻ nhất; mục lặp lại yêu cầu ghi cả productId; §5 thêm bước chấm quy tắc xếp lịch và mốc `answer` vài mili giây;
  §8 ghi rõ số 6–12 s là số cũ, cần đo lại.
- `history/2026-09-21-deterministic-itinerary-composition.md` — thêm: entry này.

Không chạm OpenAPI, không chạm mock.

## Quyết định

- **Thứ tự chọn chỗ ở: giá thấp nhất trước**, hòa thì sao cao hơn, hòa nữa thì `productId`. Giá `null` xếp cuối vì
  không so sánh được. Người dùng để tôi chọn; chọn rẻ nhất vì khi chưa biết ngân sách thì đẩy khách vào phòng đắt
  nhất là rủi ro một chiều. Tiêu chí nằm trong tài liệu để người chấm đối chiếu được, không phải hộp đen.
- **Không sinh slot `product=null`** (bữa ăn, nghỉ ngơi). Ngày không có sản phẩm thì `slots` rỗng và đã có warning
  `DAY_WITHOUT_PRODUCTS`. Streamlit vốn ẩn slot `product=null`
  (`history/2026-09-19-render-grounded-products-only.md`) nên không ai thấy khác biệt; schema không đặt `minItems`
  cho `slots` nên rỗng vẫn hợp lệ. Người dùng để tôi chọn.
- **Rải hoạt động thay vì dồn ngày đầu:** mỗi hoạt động vào ngày đang ít việc nhất, ngày sớm hơn thắng khi hòa.
  Hoạt động nguyên ngày (`durationMinutes >= 360`) xếp trước và chiếm trọn một ngày, nên không còn cảnh một slot
  chồng giờ bị bỏ.
- **`pace` chưa phải đầu vào.** Trần 2 hoạt động/ngày áp dụng cho mọi `pace` — đúng bằng trần mà `COMPOSE_PROMPT`
  cũ đã yêu cầu. Không tự đặt quy tắc mới cho `RELAXED`/`PACKED` khi spec không nói.
- **Xóa `render_best_effort` thay vì giữ làm lưới an toàn.** Nó tồn tại để vá đề xuất hỏng của model; khi backend tự
  sinh đề xuất, một slot bị renderer từ chối là **lỗi backend**, và vá im lặng sẽ giấu lỗi đó. Nay `_composed` gọi
  thẳng `render_proposal`; hỏng thì `answer` trả `FALLBACK` và ghi log `itinerary.composition_failed`.
- **`render_proposal` và `validate_plan` giữ nguyên, không nới lỏng một quy tắc nào.** `compose_plan` chỉ có nghĩa
  vụ không đề xuất thứ mà renderer sẽ từ chối; test `test_the_proposal_always_survives_the_renderer_and_the_validator`
  khóa điều đó.
- **Harness test chủ động chặn hồi quy:** `ScriptedLlm` raise `AssertionError` nếu luồng lập lịch gọi model bằng
  bất kỳ schema nào ngoài ba schema còn lại. Ai đưa LLM trở lại bước xếp lịch sẽ thấy test đỏ ngay.
- **Mâu thuẫn tài liệu, đã xử lý theo AGENTS.md §2:** handbook `recsys-internship-handbook-v3-vi.md` §9 viết
  "LLM sắp xếp các kết quả thật thành một kế hoạch theo từng ngày", nay không còn đúng. `src/ARCHITECTURE.md` §8
  ("LLM chỉ trích xuất intent và trình bày kết quả; backend tự tính tổng tiền") và spec §5.9 (cho phép lịch trình
  dựng bằng rule) có thứ tự ưu tiên cao hơn handbook, và thay đổi này đi **về phía** ARCHITECTURE §8. Không tự sửa
  handbook vì đó là tài liệu spec của chủ dự án; đã báo người dùng.

## Kiểm tra

- `LANGSMITH_TRACING=false pytest src/backend/tests`: **108 passed** (trước thay đổi 97; +11 test composer,
  các test cũ được viết lại chứ không bỏ).
- `validate_contract.py`: **PASS** (63 schemas, 50 grounded products, 4 itinerary statuses, 50 fixtures;
  CDP clone 12 schemas). Chạy để xác nhận, dù thay đổi không chạm contract/mock.
- `git diff --check`: pass.
- **Chạy `compose_plan` trực tiếp trên fixture 50 sản phẩm** cho 6 điểm đến, khớp đúng kỳ vọng đã ghi trong
  `evaluation-plan.md` §4:
  - Nha Trang 2 ngày → stay Vinpearl Beachfront (1.602.232, rẻ nhất trong 6 hotel), ngày 1 VinWonders,
    ngày 2 voucher golf.
  - Phú Quốc 3 ngày → stay VinHolidays Fiesta (1.844.192), 2 hoạt động ở ngày 1–2, ngày 3 trống.
  - TP. Hồ Chí Minh 2 ngày → không stay (catalog 0 hotel), 1 golf ngày 1.
  - Hạ Long 2 ngày → stay Vinpearl Resort & Spa (2.579.685), 0 hoạt động; Vịnh Hạ Long `available=false` bị loại.
  - Hà Nội 4 ngày → không stay, 1 attraction ngày 1, ba ngày trống.
  - Hải Phòng 2 ngày → không stay, không hoạt động (chỉ có 1 combo) → `evaluate` chuyển sang `FALLBACK`.
- **Chưa chạy thật với model và Streamlit trên trình duyệt.** Latency mới chưa đo.

## Còn lại / rủi ro

- **Chưa đo lại latency với model thật.** Kỳ vọng giảm vì bỏ một lời gọi LLM khỏi luồng `COMPLETED`, nhưng
  "kỳ vọng" không phải số đo. Phải chạy `evaluation-plan.md` và ghi số thật trước khi tuyên bố đạt/không đạt 5 s.
- Chất lượng lựa chọn nay do một quy tắc cố định quyết, không còn suy luận theo ngữ cảnh: `interests`, `party` và
  `pace` **không** ảnh hưởng tới việc chọn sản phẩm nào. Với fixture hiện tại mỗi điểm đến chỉ có tối đa 2 hoạt
  động nên không thấy khác biệt; catalog lớn hơn thì đây là hạn chế thật và cần một bước ranking riêng.
- `render_proposal` vẫn nhận `activity_type`/`note_kind` cho slot `product=null`, nhưng không còn ai sinh chúng.
  Nhánh code đó nay chỉ có test domain đi qua.
- Handbook §9 vẫn mô tả thiết kế cũ; cần chủ dự án quyết có cập nhật hay không.
- Chưa kiểm hành vi khi một điểm đến có nhiều hoạt động hơn sức chứa của chuyến trên dữ liệu thật — fixture không
  tạo được tình huống đó (tối đa 2 hoạt động mỗi điểm đến).
