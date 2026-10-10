# Trợ lý trò chuyện và khám phá trước khi lập lịch (FR-AGT-06)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, frontend, evaluation, docs

## Mục tiêu

Agent hiện cứng: "Hà Nội có gì?" bị coi là yêu cầu lập lịch và lần nào cũng bắt điền form. Người dùng muốn một trợ lý thân
thiện, linh hoạt: trò chuyện và gợi ý trước, chỉ hỏi thông tin chuyến khi người dùng muốn lập lịch, rồi mới hỏi thêm sở thích
(hồ bơi, phù hợp trẻ nhỏ…); đổi khách sạn, chuyến bay mà chưa nói rõ thì hỏi lại kèm lựa chọn cụ thể; việc ngoài phạm vi thì nói
rõ nhưng không cứng. Kịch bản review: artifact "Kịch bản trợ lý V-OTA" bản 5; góp ý: artifact "Góp ý cho trợ lý V-OTA".

Người dùng chốt đề xuất `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` ngày 2026-10-10, giao agent tự quyết các điểm
còn mở ("miễn sao flexible") và cho **bỏ qua bước cập nhật PRD trước khi sửa source** (AGENTS.md §8). PRD vì vậy chưa cập
nhật; đề xuất ghi lại các quyết định ở mục "Quyết định khi áp dụng".

## File thay đổi

Contract và mock (1.24.0):
- `src/shared/contracts/openapi.yaml` — sửa: version 1.24.0.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: `ItineraryNeedsClarification.searchResults` (lượt khám phá),
  mô tả `suggestions`; `clarificationForm.fields` thêm `interests`, thêm `interestOptions`.
- `src/shared/mocks/assistant/createItinerary.200-needs-clarification-explore.json` — thêm: response khám phá mẫu.
- `src/shared/mocks/index.json` — sửa: đăng ký mock trên.

Backend agent:
- `src/backend/app/agents/steps/exploration.py` — thêm: node khám phá (Search theo điểm đến, chọn thẻ bằng luật, LLM viết lời
  dẫn với placeholder số, câu mời lập lịch, kiểm nút gợi ý `checked_suggestions`, xử lý Search lỗi).
- `src/backend/app/domain/itinerary/exploration.py` — thêm: chọn tối đa 4 thẻ, mỗi thẻ một lý do đúng trên toàn bộ kết quả
  (nhiều đánh giá nhất, điểm cao nhất, giá thấp nhất, vào cửa tự do); gộp vé/hạng phòng của cùng một nơi; khớp tiện ích dạng chuỗi.
- `src/backend/app/domain/itinerary/preferences.py` — thêm: 5 sở thích khách sạn, đọc "ưu tiên …", lọc mềm, cụm tìm kiếm.
- `src/backend/app/domain/itinerary/flights.py` — sửa: `nearest_dates` (ngày gần nhất có vé, giữ số ngày); `flight_choices`
  (chuyến khác cùng ngày của từng chặng); `choose_flights` nhận `chosen` (chuyến người dùng đã chọn khi đổi vé).
- `src/backend/app/agents/steps/changes.py` — thêm: luật "đổi khách sạn" trơn (hỏi kèm phương án sẵn có) và "đổi chuyến bay"
  (liệt kê chuyến khác, hoặc chọn luôn khi nói "muộn hơn/sớm hơn/rẻ hơn", bấm nút có số hiệu, "bạn chọn giúp").
- `src/backend/app/domain/itinerary/search_hints.py` — sửa: sở thích vào câu tìm khách sạn, không vào câu tìm điểm tham quan.
- `src/backend/app/agents/steps/classification.py` — sửa: luật đồng ý lập lịch (`plan_consented`, `planning_implied`), ba bậc
  "không biết", "cứ chọn đại" (`_DELEGATE`), nhớ nơi bị chê, `extract` chưa đồng ý thì sang `explore`/`converse`, giữ sở thích mềm.
- `src/backend/app/agents/steps/conversation.py` — sửa: ngoài phạm vi trả 200 kèm nút (guardrail chặn vẫn 400), nút gợi ý,
  payload mới cho LLM, ô sở thích trong form.
- `src/backend/app/agents/steps/evaluation.py` — sửa: lọc mềm khách sạn theo sở thích.
- `src/backend/app/agents/steps/composition.py` — sửa (chỉ `_flight_warning`, thêm `_nearest_dates_sentence`, và trong
  `composed`: truyền `chosen_flights`, trả `flight_choices`): câu cảnh báo vé nêu ngày gần nhất có vé; lịch kèm chuyến khác. File này đã có thay đổi chưa commit của task `history/2026-10-09-chon-phuong-an-doan-nhieu-phong.md`;
  lần này không đụng phần đó.
- `src/backend/app/agents/steps/validation.py` — sửa: grounding của lượt khám phá (thẻ = sản phẩm Search, link chỉ tới thẻ).
- `src/backend/app/agents/steps/prompts.py` — sửa: nhãn `explore`, cờ `plan_request`, luật trò chuyện, từ chối mềm, sở thích;
  thêm `EXPLORE_PROMPT`.
- `src/backend/app/agents/steps/messages.py` — sửa: câu cố định cho khám phá, nút mẫu, ngày gần nhất có vé (vi, en).
- `src/backend/app/agents/models.py` — sửa: `TurnRoute` (nhãn `explore`, `plan_request`), `ConversationalAnswer.suggestions`,
  thêm `ExploreNarration`.
- `src/backend/app/agents/state.py` — sửa: `plan_consent`, `pending_offer`, `offered_destinations`, `dont_know_count`,
  `last_suggestions`, `rejected_destinations`, `explore_pick`, `offer_suggestions`.
- `src/backend/app/agents/nodes.py` — sửa: node `explore`, lưu/nạp giai đoạn hội thoại và `previous_flights`, `converse` nạp
  catalog cho nút gợi ý, `classify` chạy luật đổi trước LLM, `clarify` dựng câu hỏi đổi bằng code.
- `src/backend/app/agents/graph.py`, `src/backend/app/agents/routing.py` — sửa: 15 node, nhánh `explore`, `route_after_explore`,
  `classify → tool` khi đã chọn chuyến bay.
- `src/backend/app/main.py` — sửa: version app 1.24.0.

Frontend:
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts`, `widgetPlan.ts` — sửa: thẻ của lượt khám phá đặt xen câu dẫn.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: ô sở thích chọn nhiều, ghép "ưu tiên khách sạn có …".
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract.

Test:
- `src/backend/tests/unit/agents/test_changes.py` — thêm: 13 test (đổi khách sạn, đổi chuyến bay, vé khứ hồi, sản phẩm trùng
  chuyến, luật chọn vé, luồng ba lượt).
- `src/backend/tests/unit/agents/test_exploration.py` — thêm: 45 test (chọn thẻ, nút, đồng ý, nơi bị chê, sở thích, ngày có
  vé, luồng nhiều lượt qua graph, Search lỗi).
- `src/backend/tests/unit/agents/test_classify.py`, `test_guardrails.py`, `test_itinerary_runtime.py`, `test_lab_copy.py`,
  `test_reply_titles.py`, `test_routing.py` — sửa: theo hành vi mới (khám phá thay cho hỏi số ngày, từ chối mềm, 15 node).
- `src/backend/tests/contract/test_assistant_contract.py` — sửa: ngoài phạm vi là 200; thêm test câu trả lời có nút.
- `src/backend/tests/contract/test_search_contract.py`, `test_search_llm_contract.py` — sửa: version 1.24.0.
- `src/frontend/tests/unit/exploreCards.test.ts` — thêm; `src/frontend/tests/unit/tripDetailsForm.test.tsx` — sửa: ô sở thích.
- `src/evaluation/datasets/agent_test_cases_nhat.yaml` — sửa TC-02 (không form trước khi đồng ý), thêm TC-12 (khám phá → "ok"),
  TC-13 (nơi bị chê, ngoài phạm vi), TC-14 (đổi chuyến bay chưa nói rõ); `src/evaluation/tests/test_golden.py` — sửa danh
  sách case, thay hai test kiểm tra lỗi thời.
- `src/evaluation/agent/golden.py` — sửa: bỏ kiểm tra lỗi thời "khách sạn phải rẻ nhất" và "hoạt động đầu buổi sáng, thứ hai
  buổi chiều" (đã ghi lỗi thời ở `history/2026-10-08-node-filter-loc-trung-lap.md`), thay bằng kiểm thứ tự buổi trong ngày.
- `src/evaluation/reports/eval-2026-10-10-agent-test-cases.md` — thêm: biên bản golden cả bộ với LLM thật (bản `.json` cùng tên bị
  `.gitignore` bỏ qua, chỉ có trên máy).

Tài liệu:
- `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` — sửa: trạng thái đã chốt, mục "Quyết định khi áp dụng".
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` —
  sửa: node `explore`, bảng luật đồng ý, trường state mới, contract 1.24.0.

Không phải của task này (commit riêng: `63a997db` sửa đoàn nhiều phòng, `0b5760ac` báo cáo tuần): `src/backend/app/agents/steps/option_swap.py`,
`src/backend/tests/unit/agents/test_option_swap.py`, `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md`, phần
`composition.py` ngoài `_flight_warning`, `docs/spec/agent/slide/`, các entry `history/2026-10-09-*` chưa commit.

## Quyết định

- **Linh hoạt nhưng giữ grounding:** không chuyển sang kiểu LLM tự gọi tool. LLM chọn nhãn và viết chữ; code tìm, chọn thẻ, điền
  số, kiểm nút. Luồng lập lịch sau khi đồng ý giữ nguyên (AC-AGT-01..04).
- **Đồng ý lập lịch:** câu xin lập lịch, nút, sửa form, "ok" sau lời mời, hoặc câu có số ngày/ngày đi/số người/ngân sách. Đổi
  nơi ngay sau lời mời ("Thôi, Hà Nội thì sao?") không phải đồng ý (lỗi thấy khi chạy LLM thật). Vừa "ok" thì hỏi gộp một câu,
  chưa form.
- **Ngoài phạm vi trả 200 kèm nút**, nói rõ không làm được và việc gần nhất làm được ("Đặt ngay", "Lịch sử đặt chỗ"). Chèn lệnh,
  đòi secret, chỉ có tục tĩu vẫn 400 không gọi LLM (NFR-SEC-04).
- **Thẻ:** tối đa 4 mỗi lượt; lý do tính trên toàn bộ kết quả; khách sạn và hạng phòng của nó là một thẻ.
- **Sở thích là ưu tiên**, nằm ở `intent.interests`, không ở `hotel_attributes` (bộ lọc bắt buộc; catalog chỉ có tiện ích dạng
  chuỗi nên cờ bắt buộc loại gần hết khách sạn). Lọc mềm chỉ khi còn ≥ 3 khách sạn hợp.
- **"Cứ chọn đại"** và **chê một nơi** nhận bằng luật, vì LLM thật xếp nhãn sai ở cả hai.
- **Đổi khách sạn, chuyến bay khi chưa nói rõ** (góp ý của người dùng 09/10, kịch bản bản 5): luật tất định trong
  `classify`, không gọi LLM để hỏi. Khách sạn: hỏi kèm phương án đã tính, nút đổi ngay qua `apply_option`; câu có hướng thì
  vẫn tự đổi như cũ. Chuyến bay: liệt kê chuyến khác cùng ngày; nói rõ mong muốn hoặc bấm nút thì chọn luôn và lập lại lịch.
  Vé khứ hồi chưa đổi riêng từng chiều.
- **Bớt một lượt LLM ở lượt khám phá:** câu hỏi về một nơi, không có chữ số, chưa đồng ý lập lịch thì `explore` chạy thẳng,
  tự tra tên nơi trong catalog và `DESTINATION_ALIASES` rồi ghi làm điểm đến; không tra được thì quay lại `extract` một lần
  (`route_after_explore`), nên "Bangkok có gì?" vẫn được báo "chưa có dịch vụ" như cũ. Câu có chữ số luôn qua `extract`.
- Lỗi thấy khi chạy LLM thật đều đã có test hồi quy: "chọn đại" bị trả lời "nhắn tên đi"; lọc hồ bơi ra rỗng vì catalog không có
  cờ `pool`; đổi nơi bị coi là đồng ý; nút "Lên lịch" lệch câu dẫn "Tiếp tục lập lịch"; Search lỗi bị báo "không có chỗ nào";
  khách sạn và hạng phòng thành hai thẻ.

## Kiểm tra

Tầng tất định (fixture, LLM giả), chạy trên code cuối cùng:
- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain`: 1882 passed (trước thay đổi:
  1817 passed).
- Cả bộ backend: `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false .venv/bin/python -m pytest -q -p no:cacheprovider
  src/backend/tests`: **2675 passed, 36 skipped, 0 failed** (24 giây). 36 test bỏ qua là test tích hợp phải bật bằng
  `RUN_POSTGRES_INTEGRATION=1`, `RUN_REDIS_INTEGRATION=1`, `RUN_PGBOUNCER_INTEGRATION=1`, `E5_SMOKE=1` — không chạy. Hai biến môi
  trường chỉ để app trong test contract không nối Weaviate và không nạp RecSys (mỗi `TestClient(app)` mất khoảng 50 giây cho
  bước đó; test contract tự tiêm client giả nên không cần). Chạy thường thì quá chậm (30 phút mới xong 7 test contract).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (120 schemas, 95 fixtures).
- `.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py`: 67 passed.
- `.venv/bin/python -m pytest -q src/evaluation/tests`: 13 failed, 100 passed — đúng 13 test RecSys `test_temporal.py`… fail y hệt
  trên HEAD (so bằng worktree tạm), không liên quan.
- Frontend: `vitest run` 820 passed (79 file); `tsc --noEmit` sạch; eslint file đã sửa: 0 lỗi (1 cảnh báo có sẵn từ d8791cd1).

LLM thật (`ITINERARY_LLM_MODEL=gpt-6-luna` trong `.env`), backend local:
- **Golden, cả bộ, `inprocess` (catalog thật, 4.147 sản phẩm):** report `src/evaluation/reports/eval-2026-10-10-agent-test-cases.md`
  (`.json`): 20/23 lượt PASS; Grounding 100%, Structured Output 100%, Tool Calling 100% (18 lượt); latency p50 5,4 giây, p95
  25,1 giây. Ba lượt fail:
  - TC-01 lượt 1 (mong `COMPLETED`, nhận câu hỏi chi tiết chuyến): chạy lại trên HEAD bằng worktree tạm cũng fail y hệt, không
    do thay đổi này (có từ khi nơi đi thành chi tiết được hỏi, 07/10).
  - TC-04 lượt 3 ("không đổi nữa"): lỗi đã biết từ 05/10.
  - TC-02 lượt 1: LLM quên câu "chưa biết cũng không sao"; đã siết `CONVERSATION_PROMPT`, chạy lại `--only TC-02 --repeat 2`:
    4/4 PASS.
  Report này chạy trước khi sửa TC-02; các chỗ khác của code giống bản cuối.
- Trong lúc chạy golden đã sửa thêm bốn lỗi, có test hồi quy: câu từ chối cố định không nói rõ không làm thay (TC-13); vé khứ hồi
  không đổi được (TC-14); hai sản phẩm cùng một chuyến bị coi là "chuyến khác" (TC-14); "hòn Thơm" và "Cáp Treo Hòn Thơm" thành
  hai thẻ. Kiểm tra lỗi thời của runner ("khách sạn phải rẻ nhất", "hoạt động đầu phải buổi sáng") đã thay bằng kiểm thứ tự buổi.
- Kịch bản 6 lượt trên catalog thật (code cuối): chào hỏi → "cứ chọn đại" (tự chọn Nha Trang, có thẻ) → "chán, chỗ khác đi" (đổi
  sang Phú Quốc) → "hn có gì chơi" (Hà Nội, 7,1 giây) → "khách sạn nào có hồ bơi?" (4 khách sạn có hồ bơi, có Little Charm) →
  "ok lên lịch luôn" (hỏi số ngày, không form).
- Đối chiếu từng cảnh của artifact "Kịch bản trợ lý V-OTA" bản 5 trên catalog thật (code cuối): luồng chính cảnh 1–5, 7–9 đúng
  ý; người dùng khó ("?", "vắng vắng", "asdfgh", chê nơi, không dấu "k bit dat phong sao", "đi đâu cũng đc vl") đúng ý; ngoài
  phạm vi (đặt vé, huỷ đơn, MoMo, xe đưa đón, thời tiết, Bangkok, chèn lệnh) đúng ý. Lần đối chiếu này bắt thêm ba lỗi, đã sửa
  và có test: "Văn Miếu buổi tối có mở không?" trả thẻ chung chung và nói không kiểm được giờ (giờ có trong catalog) → nay tìm
  thêm bằng nguyên câu hỏi, nơi được nêu tên đứng đầu, LLM nhận giờ mở cửa để trả lời; MoMo trả lời lửng → prompt nêu rõ chỉ
  nhận thẻ; "đi đâu cũng đc" (viết tắt) không vào bậc trợ lý tự chọn. Thêm nút chọn nhanh ngày đi dưới form (cảnh 8).
  Chưa làm theo kịch bản: cảnh 6 (giá vé khi chưa có ngày, kịch bản ghi "Ngoài đề xuất") và trả lời tiếng Anh ("Ngoài PRD") —
  chờ người dùng quyết.
- `fixture`: "hn có gì chơi" đi `classify → explore → finalize`, **3,7 giây**; "Bangkok có gì vui?" đi `explore → extract →
  clarify`, báo chưa có trong danh sách.

Sự cố môi trường trong phiên (đã tìm ra nguyên nhân): từ 09:11 Search treo tới timeout. Lúc đó mình **kết luận sai** là do key
Cohere hết lượt (Cohere trả 429), nhưng embedding đã chuyển sang model local `intfloat/multilingual-e5-small`, không dùng Cohere
nữa (người dùng nhắc). Nguyên nhân thật, đo bằng Python: tên miền ra ngoài trả địa chỉ IPv6 trước mà máy **không đi được IPv6**
(mỗi lần nối IPv6 chờ hết timeout, IPv4 0,1 giây). Lần tìm đầu, thư viện HuggingFace kiểm phiên bản model qua mạng nên kẹt; lúc
khởi động, client Weaviate gọi PyPI cũng kẹt (`_check_package_version`, `weaviate/connect/v4.py`). Chạy backend với
`HF_HUB_OFFLINE=1` (model đã có trong cache) thì Search lại 3,1 giây lần đầu, sau đó khoảng 30 ms.

## Còn lại / rủi ro

- **Máy local không đi được IPv6** (không phải lỗi code): nên đặt `HF_HUB_OFFLINE=1` khi chạy backend local (model e5 đã có trong
  cache), hoặc cho máy ưu tiên IPv4. Khởi động backend vẫn mất khoảng 107 giây vì client Weaviate kiểm phiên bản trên PyPI qua
  IPv6; muốn bỏ bước này cần `skip_init_checks` ở `infrastructure/vectors/weaviate_store.py` (phần của người khác, chưa sửa).
- Cập nhật PRD theo đề xuất (người dùng cho bỏ qua ở đợt này); đề xuất còn ở `docs/prd/update/`, chưa chuyển sang archive.
- Chưa làm: cảnh 6 của kịch bản (giá vé khi chưa có ngày) và trả lời tiếng Anh — chờ người dùng quyết; ẩn lựa chọn sở thích
  theo dữ liệu từng điểm đến; cẩm nang điểm đến (cần DDL);
  golden case cho đổi khách sạn (phụ thuộc lịch có phương án khác); TC-01 lượt 1 và TC-04 lượt 3 (lỗi có sẵn).
- Thời gian: lượt khám phá với LLM thật 3,7 giây (`fixture`) đến 7,1 giây (`inprocess`), p50 cả bộ golden 5,4 giây; lượt lập lịch
  vẫn 10–25 giây. Hướng giảm tiếp: cẩm nang điểm đến, rút ngắn `narrate`.
