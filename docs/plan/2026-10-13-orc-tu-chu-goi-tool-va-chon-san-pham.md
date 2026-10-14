# Kế hoạch thực thi orc tự chủ gọi tool và chọn sản phẩm

- Ngày: 2026-10-13
- Nhánh: codex/orc-autonomous-tools
- Chốt bởi: Nguyễn Minh Nhật, 2026-10-13 (yêu cầu thực thi plan)
- FR/NFR: FR-AGT-01–07, FR-SRC-01/03/04, FR-REC-01/03, NFR-REL-01, NFR-SEC-01/04, NFR-MAINT-01/02, NFR-PERF-02
- PRD có hiệu lực: [đề xuất đã áp dụng](../prd/update-archive/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md) §2.

## Tiến độ và baseline

| Bước | Trạng thái | Bằng chứng |
|---|---|---|
| E00 | hoàn thành | PRD đã áp dụng; baseline 2 failed, 10 passed (cassetteMiss có sẵn) |
| E01 | hoàn thành contract | 36 schemas, 8 fixtures, 14 negative checks; types/typecheck đạt; bổ sung `Alternative.uiAction`, `Itinerary.party` (13/10) |
| E02–E10 | hoàn thành (viết lại gọn 13/10) | Schema strict 24 KB (bản cũ 193 KB, `uniqueItems` bị OpenAI từ chối); test v2 + Redis thật; history `2026-10-13-orc-tu-chu-rut-gon-va-chay-model-that.md` |
| E11 | dang dở | Widget hiển thị v2 qua hàm chuyển, bật bằng `NEXT_PUBLIC_ASSISTANT_API=v2`; vitest đạt; chưa có E2E trình duyệt cho v2, chưa xem trước lịch của phương án khác |
| E12 | dang dở | Ca §6 chạy model thật + catalog thật ×3 (`src/evaluation/agent/assistant_v2_cases.py`); báo cáo `src/evaluation/reports/eval-2026-10-13-assistant-v2-acceptance.md` |
| E13 | chưa làm | Chờ người dùng duyệt kết quả E12; cần ghi archive/đọc lịch sử v2 trước khi chuyển widget (FR-AGT-01) |

## Ma trận AC giữ/thay

| AC | Giữ | Thay ở v2 |
|---|---|---|
| 01 | Đồng ý, hỏi gộp, form, ngày/khách, dừng | Orc patch ngữ cảnh có bằng chứng, không extract riêng |
| 02 | Giá/khách, ngày/giờ, khoảng đệm 90/150 phút, vé đã chốt | Orc chọn vé; tool không tự bỏ/dời hoạt động |
| 03 | Vị trí chỉ trên trình duyệt | Không đổi |
| 04 | Giá/phòng ≤9, preview, nhãn có chứng cứ, km ước tính | Orc draft/selection; 0 đêm; >2 hoạt động; budget warning-only; refresh khi chọn |
| 05 | Hỏi giữ lịch; đổi giữ mốc đã chốt | Mọi câu trả lời qua orc; revision/plan effect |
| 06 | Grounding, consent, yêu cầu thêm và scope | Trần 10/taxonomy, không tổng 20/bù thẻ |
| 07 | Giọng điệu, grounded cards, tối đa 3 nút | Nút sai trả repair, không code tự tạo |
| 08 | Dữ kiện chuyến, thời gian, simulated, coverage | Tool trả facts, orc trả lời/chọn thẻ/nút |
| 09 | Số đếm an toàn, chỉ xem preview, không lưu tiến trình | Tiến trình theo call thực tế, không chuỗi định trước |

Baseline mới đo: snapshot + architecture → 2 failed, 10 passed, 7,81s (exit 1):
`test_each_turn_matches_the_recorded_behavior`, `test_every_llm_payload_is_in_the_cassette`, 178 lượt cassetteMiss.
Không đổi snapshot/cassette cho xanh. Lần chạy sandbox treo đã dừng (exit 130), rerun offline ngoài sandbox có giới hạn 120s hoàn tất.

Tồn đọng D1/D3/T1–T4 và hai snapshot cần ghi lại từ history 13/10 vẫn là ca hồi quy; chưa được đóng.
Đề xuất Catalog tự lấy (08/10) và debug Phần B vẫn chờ chốt riêng, không áp dụng.

## 3. Bộ công cụ dự kiến

Tên dưới đây là đề xuất nội bộ, không phải API công khai mới đã có. Không bọc toàn workflow cũ vào một tool.

| Tool | Nền hiện có | Tham số chính và trách nhiệm |
|---|---|---|
| `search_products` | Gateway + SearchRequest | Câu tìm, điểm đến/phạm vi, taxonomy, ngày/số khách phù hợp, bộ lọc giá, phân trang. Dùng để tìm theo nhu cầu; trả độ phủ và điều kiện thực sự áp dụng. |
| `get_recommendations` | Gateway; API hiện có `k`, `destination` | Dùng gợi ý theo hồ sơ hoặc phổ biến. Danh tính lấy từ phiên server, không do orc truyền. Không giả lập bộ lọc taxonomy/giá mà API chưa hỗ trợ. |
| `get_similar_products` | Gateway khi có Similar adapter | Mã sản phẩm gốc đã biết và giới hạn. Trả cùng taxonomy; orc kiểm sự phù hợp điểm đến/ràng buộc qua dữ kiện. |
| `get_product_detail` | Catalog helper | Mã sản phẩm đã có trong registry; đọc dữ kiện mới trong lượt. Phiên bản đầu một ref/call, cache trong lượt; batch chỉ bổ sung sau số đo như §9.3. |
| `list_destinations` | Catalog helper | Không tham số nghiệp vụ ở phiên bản đầu; trả các nơi hệ thống có dữ liệu. |
| `list_products` | Catalog helper | Điểm đến, taxonomy, parent, thứ tự giá, giới hạn/con trỏ. Dùng duyệt có cấu trúc khi cần; không giả vờ hiểu câu tìm ngữ nghĩa. |
| `lookup_flights` | Tách dữ kiện từ `fares.py` và `application/itinerary/flights.py` | Nơi đi/đến, ngày/khung giờ, một chiều/khứ hồi, tiêu chí so sánh, con trỏ. Trả ứng viên, thống kê, thiếu thông tin và phạm vi đã quét; không soạn câu trả lời cuối hay chọn vé thay orc. |
| `build_itinerary` | Tái sử dụng các hàm giá, lịch, khoảng cách; đổi quyền chọn của compose | Nhận lịch phác và refs do orc chọn; kiểm/tính/đổi thứ tự theo quyền được cấp. Không gọi Search/Rec ngầm, không tự thêm/thay sản phẩm. |

Một lần gọi tool có thể cần nhiều request hạ tầng (ví dụ tuyến → chuyến, lấy chi tiết theo lô), nhưng phạm vi,
giới hạn trang và lý do phải được khai báo; mọi request tính vào budget. Tool trả `partial` và con trỏ khi
chưa quét hết. Orc quyết định lấy tiếp. Retry vận chuyển cùng tham số được giới hạn; không tự đổi query.

## 4. Hợp đồng để orc biết cách truyền tham số

Mỗi tool phải có: mục đích, khi nên dùng, điều kiện trước khi gọi, kết quả trả về, giới hạn, ví dụ, lỗi có thể sửa.
Mọi field, kể cả field con và enum, phải có: kiểu, bắt buộc/default, ý nghĩa `null`/bỏ trống, đơn vị,
nguồn giá trị, quan hệ với field khác và ví dụ đúng/sai. Schema thực sự gửi tới model phải giữ các mô tả này.

- Lấy định nghĩa API từ OpenAPI; bổ sung mô tả điều phối trong schema nội bộ, không tạo bản sao API lệch nguồn.
- Giữ `description` ở cấp parameter khi dựng tool schema (`tool_contracts.py` hiện chỉ lấy schema ở một số tool).
- Phân biệt tham số backend hỗ trợ và tham số wrapper hậu kiểm; trả `applied`/`unsupported`/`unknown` rõ ràng.
- `limit` là số ứng viên lấy, `requested_count` là nhu cầu người dùng, danh sách refs là lựa chọn của orc,
  trần 10 là giới hạn hiển thị. Không đồng nhất bốn khái niệm này.
- Giá theo VND và cơ sở giá cụ thể; không truyền ngân sách cả chuyến vào giá mỗi đêm/phòng.
- `destination = null` ở yêu cầu thay phạm vi là không khóa điểm đến, không lấy thành phố của thẻ cuối để bù.
- Lịch sử chỉ giúp hiểu tham chiếu; các dữ kiện thay đổi được tra lại trong lượt. Dùng cache trong lượt để tránh đọc trùng.

Ví dụ thiết kế `build_itinerary` cần hoàn thiện thành schema sau chốt:

| Tham số | Ý nghĩa |
|---|---|
| `trip` | Điểm đến, ngày bắt đầu, số ngày, số người đã biết. Ngày giờ Việt Nam; không ngầm lấy giá trị cũ trái yêu cầu mới. |
| `draft.days[].activities[]` | Ref sản phẩm do orc đã chọn, ngày/buổi hoặc giờ đề xuất; duration có nguồn catalog hoặc đánh dấu giả định. |
| `draft.stays[]` | Ref khách sạn, ngày nhận/trả và số phòng nếu biết. `[]` nghĩa không lưu trú; không đổi thành một đêm mặc định. |
| `draft.flights[]` | Ref chuyến do orc chọn; `[]` nghĩa không thêm chuyến. Phải đúng tuyến/ngày và không trái lựa chọn người dùng. |
| `constraints` | Ngân sách cả chuyến, chỉ miễn phí theo phạm vi đã hiểu, loại không dùng, yêu cầu bắt buộc và ưu tiên mềm tách riêng. |
| `locked` | Sản phẩm và mốc thời gian đã chốt; tool không được thay. |
| `optimization` | `none`, `reorder_within_day` hoặc `reassign_unlocked_slots`; chỉ xê dịch đúng quyền, không thay tập sản phẩm. |
| `pace` | Nhịp đi theo người dùng/orc suy ra và nêu rõ; không biến thành trần hai hoạt động ẩn. |

Kết quả: `status`, lịch đã kiểm hoặc lịch còn lỗi, tổng/chi tiết chi phí, trạng thái giá chưa biết,
`violations`, `warnings`, giả định thời gian, `changes` do tối ưu, nguồn dữ kiện và phạm vi kiểm.
`infeasible` là dữ liệu để orc sửa, không phải lý do tự bỏ điểm. Thời lượng thăm dự kiến do orc đề xuất được
kiểm tính nhất quán nhưng vẫn ghi là ước tính; không bịa giờ mở cửa hay đổi khoảng cách đường thẳng thành thời gian đường bộ.

## 5. Kế hoạch triển khai sau chốt

### P0 — chốt PRD và tiêu chí chuyển đổi

- Áp dụng §2 vào PRD trước, rà AC-AGT-01–09 theo bảng giữ/thay, rồi lưu trữ đề xuất.
- Chuyển kế hoạch này sang `docs/plan/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md` sau khi PRD có hiệu lực.
- Chụp baseline hiện tại, ghi các lỗi tồn đọng; không coi snapshot cũ đang lệch là baseline xanh.
- Đọc đủ tài liệu backend/agent/frontend/contract theo AGENTS.md trước từng phần code; thông báo §1.3 trước sửa.
- Đầu ra: phạm vi được duyệt và ma trận AC cũ → kỳ vọng mới; không bỏ AC do gỡ node.

### P1 — schema công cụ, đầu ra và registry

- Thiết kế registry cho 8 tool trong §3; orc nhận đúng các tool có adapter hoạt động.
- Định nghĩa call/result/error/partial/continuation; mọi tham số có mô tả như §4.
- Registry giữ refs và dữ kiện đủ cho orc so chọn: giá/cơ sở giá, điểm đến, vị trí, tiện ích, thời lượng/giờ nếu có,
  nguồn và tình trạng thiếu dữ liệu. Không chỉ đưa vài tên rồi yêu cầu orc chọn trong mù mờ.
- Kết quả rút gọn có tổng, còn bao nhiêu ứng viên, còn trang không; orc chủ động đọc thêm. Không ép brief 8 mục
  hoặc 3.000 ký tự làm trần gợi ý trá hình. Chọn kích thước context bằng đo, giữ full data ở server.
- Đầu ra: schema có ví dụ và test chứng minh mô tả field tới được model; validation không tự sửa ý định.

### P2 — vòng orc gọi tool trực tiếp

- Graph tối giản theo §2.1; orc chọn tool bằng tên + args có schema và đọc tool result sau mỗi vòng.
- Loại bỏ tuyến `plan → extract → ... → narrate` khỏi đường thực thi mới; đưa hiểu yêu cầu/hỏi lại/diễn giải
  về orc. Giữ hàm thuần cần thiết cho tool, không sao chép cả graph con.
- Bỏ việc tự thêm Search/Recommendation, tự tiếp trang cho đủ chỉ tiêu, tự bù thẻ, chọn thẻ fallback và shortcut vé.
- Budget dùng chung cho mọi tool và thao tác sửa: deadline, số call vật lý, số vòng; chừa lần trả lời cuối.
  Dùng số hiện tại 3 vòng/10 call làm baseline đo, không khẳng định phù hợp cho mọi ca. Nếu không đủ, đưa số đo
  và đề xuất giới hạn cụ thể trước khi đổi; không bỏ phanh để đạt tự chủ.
- Chặn lặp lời gọi thành công không có tiến triển; lỗi tạm thời có quyền retry giới hạn, không bị signature cũ khóa vĩnh viễn.
- Đầu ra: trace chứng minh không có tool nghiệp vụ nào được code tự thêm ngoài quyết định orc.

### P3 — tool lập lịch và tra vé trả dữ kiện

- Tách `lookup_flights` khỏi phần dựng câu vé; giữ tính giá/thống kê và luật giờ bay có nguồn.
- Xây `build_itinerary` nhận refs + draft; tái dùng hàm giá/availability/khoảng cách và kiểm grounding.
- Gỡ việc compose tự chọn khách sạn, thay sản phẩm, lấp đủ buổi và ưu tiên vé có phí khi trùng.
- Kiểm được lịch không lưu trú, chỉ điểm miễn phí, lịch nhiều hơn hai hoạt động/ngày, lịch có mốc khóa.
- Đầu ra: tool không thay tập refs; lịch chưa khả thi trả vấn đề rõ; orc sửa và gọi lại.

### P4 — contract và giao diện của vòng mới

- Làm contract trước code API/UI: thẻ tối đa 10/taxonomy, lịch 0 đêm, nhiều hoạt động/buổi, tiến trình lặp,
  trạng thái unknown/partial và kiểm soát cập nhật lịch. Phân biệt gợi ý, preview và lịch đã chốt.
- Thay đổi này chạm semantics v1 (số đêm, cách trả lời và giới hạn). Thiết kế hợp đồng assistant v2 theo
  AGENTS.md §3; không sửa ngầm semantics v1 hoặc ép kết quả mới vào shape cũ rồi cắt thẻ.
  Giai đoạn P1 phải chốt cụ thể request/response và đường chuyển client trước khi triển khai P2–P3 vào API.
- UI dùng đầu ra orc đã kiểm để hiển thị thẻ, lịch, bản đồ; tiến trình lấy từ công việc thực tế.
- Bấm chọn phương án/nút vé gửi ý định có cấu trúc vào orc; không phải gõ lại bằng câu tự bịa.
- Đầu ra: người dùng thấy đúng số và thứ tự orc chọn, lịch chỉ đổi sau chốt hợp lệ; test cả HTTP và SSE.

Thứ tự phụ thuộc thực hiện: P0 → P1 (gồm contract v2) → P2 → P3 → P4; API/UI dùng contract đã định nghĩa ở P1.
P4 là hoàn thiện renderer/stream và chuyển client, không đợi tới đó mới thiết kế contract.

### P5 — nghiệm thu tự chủ và chất lượng

- Unit: schema/description, budget, cache trong lượt, partial và retry, refs, ràng buộc, số tiền, thời gian,
  không bù thẻ và không thay sản phẩm, lưu state chỉ sau finalize; coverage domain/application theo DoD.
- Contract: validate_contract.py, fixture âm/dương cho 10/11 mỗi taxonomy, hơn 20 tổng khi hợp lệ,
  0 đêm, nhiều hoạt động và câu trả lời không làm đổi lịch.
- Integration: adapters Search/Recommendation/Catalog, lựa chọn người dùng và danh tính phiên server,
  registry qua nhiều lượt, HTTP/SSE cùng kết quả nghiệp vụ.
- Model thật + catalog thật: các ca §6, mỗi ca trọng yếu chạy ba lần với biến thể câu chữ; ghi tool/args,
  refs được chọn, lỗi grounding/constraint, latency p50/p95 và token/cost khi có telemetry.
- Chấm tool calling theo công cụ/đối số phù hợp và mục tiêu đạt; không ép một chuỗi tool cố định làm đáp án duy nhất.
- Ghi lại cassette bằng model thật, review khác biệt và phát lại offline; không sửa đáp án snapshot cho xanh.
- Đầu ra: 100% grounding/schema ở ca kiểm; tool calling ≥95% theo test-plan; các ca trọng yếu đạt cả ba lần.
  NFR-PERF-02 vẫn là mục tiêu phải báo số đo; nếu không đạt thì ghi không đạt, không tự thay SLA.

### P6 — chuyển hoàn toàn và dọn workflow

- Sau nghiệm thu, chuyển widget sang contract mới; kiểm các client cũ trước khi ngừng v1 theo lộ trình riêng.
- Kiểm call site rồi gỡ node, prompt, field state, tests chỉ giữ workflow cũ; giữ các hàm nghiệp vụ đang được tool dùng.
- Không tạo lại cờ `ITINERARY_ORCHESTRATOR` hoặc classify/explore/converse LLM cũ.
- Cập nhật spec, sơ đồ, tài liệu chạy, history; rollback bằng bản phát hành trước nếu cần.
- Triển khai staging là bước riêng sau kiểm local; cấu hình VM đổi qua Secret Manager theo AGENTS.md,
  không ghi giá trị vào repo hoặc sửa tay env VM.

## 6. Ca nghiệm thu bắt buộc

| Ca | Kỳ vọng |
|---|---|
| Huế 24/10 một ngày, chỉ tham quan miễn phí, không ở khách sạn | Orc chọn đúng điều kiện, chỉ dùng điểm có căn cứ miễn phí; không tự search khách sạn/combo; 0 đêm; nêu phạm vi chi phí. |
| “Cho mình 10 khách sạn Huế có hồ bơi” | Đủ dữ liệu thì 10 hotel đúng điều kiện; thiếu thì nói đúng thiếu dữ liệu hay budget; không cắt còn 2/4, không bù bằng sản phẩm chưa được orc chọn. |
| Hỏi 10 khách sạn + 10 điểm + 10 combo | Mỗi taxonomy ≤10; không cắt ngầm toàn câu còn 20; có đủ dữ liệu/budget mới đủ 30. |
| “Gợi ý hợp với mình” khi đăng nhập/ẩn danh | Orc có thể chọn Recommendation; nhận rõ cá nhân hóa hay phổ biến; không truyền ID người khác. |
| Hỏi vị trí/tiện ích thẻ thứ hai | Tra đúng sản phẩm; không bắt đầu tìm toàn bộ loại hoặc lập lịch lại. |
| “Tìm thêm toàn catalog, không chỉ Huế” | Phạm vi mới do orc truyền; không kế thừa điểm đến của thẻ cuối; không lặp thẻ theo ý định more. |
| Chỉ hỏi vé sau khi đã có lịch | Tool trả dữ kiện cho orc; trả lời đúng câu hỏi và không đổi lịch đã lưu. |
| Lịch bốn hoạt động ngắn, thời gian đủ | Không bị trần hai; không trùng giờ; giả định thời gian được đánh dấu nếu nguồn thiếu. |
| Một hoạt động cả ngày + hoạt động trùng giờ | Tool trả xung đột; orc sửa, không âm thầm bỏ sản phẩm rồi báo thành công. |
| Khóa khách sạn A rồi tối ưu | Tool giữ A và tập refs; trả đúng thay đổi thứ tự được cho phép. |
| “Không tốn tiền” sau lượt ngân sách 2 triệu | Điều kiện mới không bị ngân sách cũ lấn át; chưa rõ phạm vi thì orc làm rõ, không đổi thành “giá rẻ”. |
| Product thiếu giá | Không kết luận miễn phí hoặc tính tổng hoàn chỉnh sai; hiện unknown/phạm vi chưa tính. |
| Tool trả dữ liệu có câu chèn lệnh | Chỉ coi là dữ liệu; không gọi tool ngoài quyền, không lộ secret. |
| Hỏng một tool / hết deadline / model lỗi | Kết quả thành công được giữ nội bộ, lỗi không thành empty; orc có thể chốt phần đã kiểm khi còn thời gian; không có final hợp lệ thì thông báo lỗi ngắn, không fallback chọn thẻ. |
| JSON và SSE, bấm nút và nhắn chữ | Cùng quyền quyết định orc; đúng lịch đang dùng, đúng shown; không double-finalize hoặc ghi nhận preview như đã gợi ý. |

## 7. Thay đổi source sau khi chốt

- `src/backend/app/agents/{graph.py,routing.py,nodes.py,state.py,models.py,runtime_dependencies.py}`:
  vòng điều phối, schema call/final, state và chuyển tiếp contract.
- `src/backend/app/agents/steps/{orchestration.py,jobs.py,tool_planning.py,prompts.py,fares.py,composition.py,shown.py,validation.py,progress.py}`:
  bỏ quyết định workflow ngầm, chuyển dữ kiện về orc, registry và tiến trình động.
- `src/backend/app/agents/tools/itinerary_gateway.py`, `src/backend/app/application/itinerary/tool_contracts.py`,
  `src/backend/app/application/ports/itinerary_tools.py`: danh sách tool có schema đầy đủ và dispatcher.
- Tool lập lịch mới đề xuất ở `src/backend/app/application/itinerary/build_itinerary.py` theo E06.
  `src/backend/app/domain/itinerary/{planning.py,gatekeeper.py}` và các hàm giá/lịch/routing liên quan:
  kiểm/tính/tối ưu theo đầu vào, bỏ quyền chọn sản phẩm ngầm.
- `src/shared/contracts/openapi.yaml`, `paths/itinerary-agent.yaml`, `schemas/itinerary-agent.yaml` và schema/path
  v2 được định nghĩa ở P1; mock/validator tương ứng. Tool schema nội bộ không bắt buộc thành HTTP endpoint.
- `src/backend/app/api/v1/routes/assistant.py`, use case/port planner và adapter API v2 dự kiến:
  wire phiên bản phù hợp, không đưa business logic vào route.
- `src/frontend/src/features/itinerary/widget/`, `services/assistantStream.ts`, `context/assistantState.ts`,
  `context/AssistantProvider.tsx`, types sinh từ contract: nhiều thẻ, lịch linh hoạt, tiến trình và xác nhận lựa chọn.
- `src/backend/tests/{unit,contract,integration,architecture}/`, test widget/stream/E2E và bộ snapshot.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/` và spec frontend/product:
  đồng bộ sau PRD; không sửa trước phê duyệt.

## 8. Liên quan, tồn đọng và giới hạn bằng chứng

- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`: lấy các lỗi T1–T4, D1/D3 và ý AC còn thiếu làm ca
  hồi quy; không coi việc đổi kiến trúc là đã sửa xong. Plan này không thay lịch sử kết quả của plan cũ.
- `history/2026-10-13-sua-ke-thua-pham-vi-kham-pha.md`: chưa kiểm model thật sau sửa, hai snapshot cần ghi lại.
- `history/2026-10-13-d3-baseline-va-tai-lieu-orchestrator.md`: baseline và các lỗi D3 cần tiếp tục đối chiếu.
- `history/2026-10-13-hoan-thien-ui-tien-trinh-agent.md` và `2026-10-13-tien-trinh-bam-luot-chat-hien-tai.md`:
  giữ số đếm có nguồn, phạm vi của lượt hiện tại; chưa có bằng chứng staging/LLM thật từ kiểm fixture UI.
- Đề xuất `2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md` đang chờ, đề nghị code tự lấy Catalog;
  hướng đó xung đột quyền tự chọn tool ở đây. Không tự áp dụng; sau chốt cần hợp nhất hoặc đóng riêng phần trùng.
- Đề xuất tiến trình Phần B, thẻ khách sạn một chạm, bố cục bản đồ màn hẹp và đồng bộ nút form vẫn có trạng thái
  riêng. Không suy việc chốt hướng orc thành chốt các đề xuất đó.
- Lần lập đề xuất này chỉ đọc tài liệu/source và kiểm file tài liệu; không chạy model, không tái hiện ca Huế,
  không chạy benchmark, không xác nhận runtime mới.

Điều cần duyệt khi chốt toàn bộ: các đoạn PRD thay ở §2, contract assistant v2, ngoại lệ lỗi/guardrail,
phân biệt miễn phí với chưa biết giá, và thiết kế thực thi §9–14. Các lựa chọn người dùng đã trả lời ở §1 không hỏi lại.

## 9. Hợp đồng thực thi nội bộ — thiết kế cụ thể đề xuất

Phần này giảm các quyết định mà coding agent phải tự đoán. Tên module/schema mới dưới đây là **đề xuất**,
chỉ tạo sau khi chốt; khi chuyển thành spec không coi mô tả này là code đã tồn tại.

### 9.1. Một cơ chế điều khiển, hai dạng quyết định

Dùng structured output đã có trong adapter LLM cho `OrcDecision` phân biệt bởi `action`; không đổi provider/SDK
hoặc đồng thời triển khai thêm một cơ chế native tool calling trong cùng task. Orc vẫn chọn trực tiếp tên tool
và args từ schema; dispatcher không đổi lựa chọn đó. Schema dùng union theo tên tool, không dùng `args: dict`
tự do để model phải đoán. Về sau có thể đổi transport gọi tool mà giữ các hợp đồng này.

| Dạng | Field và luật |
|---|---|
| `action=execute` | `context_patch`, `calls` (1–3), `calls[].call_id`, `calls[].name`, `calls[].arguments`. Một batch chỉ chứa việc độc lập; tool dùng kết quả của một call chưa chạy trong cùng batch bị từ chối. |
| `action=respond` | `context_patch`, `answer`, `suggested_refs` theo taxonomy, `plan_result_id` nullable, `plan_effect=keep|replace`, `suggestions` (0–3), `disclosures`, `outstanding_requests`. Không có calls. |

`answer` là các đoạn văn và tham chiếu dữ kiện có kiểu, tái dùng cách điền placeholder hiện có nếu phù hợp.
Orc không truyền giá/URL/ảnh tự do vào thẻ; renderer lấy theo ref. So sánh dùng `fact_ref` do tool trả và phạm vi
được tính; không cho kết luận “rẻ nhất” toàn catalog khi tool chỉ trả một trang. Các câu miêu tả không có căn cứ
vẫn cần eval model thật; schema không chứng minh được mọi câu văn đều đúng.

`context_patch` chỉ sửa trường hội thoại được cho phép: nhu cầu chuyến, ràng buộc, yêu cầu đang chờ, đồng ý/dừng,
và lựa chọn người dùng. Mỗi thay đổi điều kiện bắt buộc có `source=user_message|ui_action`, trích đoạn bằng chứng
hoặc ID UI action. Không cho tool result viết đè chúng. Kiểm đoạn trích thực sự có trong đầu vào; không coi
kiểm đoạn trích là đã chứng minh hiểu đúng ngữ nghĩa. Ca ngôn ngữ phủ định/mơ hồ cần kiểm model thật.

`plan_effect=replace` chỉ hợp lệ nếu có `plan_result_id` do `build_itinerary` của lượt này trả về, status không
`infeasible`, và đầu vào người dùng đã cho phép lập/sửa lịch. `keep` không ghi đè lịch cũ dù tool vừa thử lịch mới.
Chỉ hỏi giá vé, xem chi tiết hoặc gợi ý sản phẩm mặc định không có hiệu ứng sửa lịch.

### 9.2. Kết quả công cụ và sổ dữ kiện

`ToolResult` dùng cùng envelope cho cả tám công cụ:

| Field | Luật |
|---|---|
| `call_id`, `tool` | Copy từ lời gọi đã kiểm, không lấy từ nội dung catalog. |
| `status` | `ok|empty|partial|needs_input|invalid_arguments|unavailable|failed`. Empty chỉ khi tra thành công và không có kết quả phù hợp. |
| `items` | Mỗi mục có ref do server cấp, taxonomy, tên và facts có nguồn. Giữ thứ tự nguồn; orc quyết định thứ tự hiển thị. |
| `facts` | Giá/currency/basis, ngày/giờ, tiện ích, tọa độ, thời lượng nếu có; mỗi fact gắn nguồn/call và tình trạng known/unknown. |
| `coverage` | Phạm vi query/filter, số đã kiểm, total nếu nguồn cung cấp, `complete`, `next_cursor`. Total tìm thấy không đồng nghĩa số phù hợp sau lọc. |
| `applied`, `unsupported`, `warnings` | Nêu bộ lọc thực thi thật, khả năng thiếu và cảnh báo; không nhận tham số mà lặng lẽ bỏ qua. |
| `errors` | `code`, `field`, `retryable`, `safe_message`; không chứa raw exception/secret. |
| `data` | Dữ liệu riêng có schema cho từng tool: thống kê vé, lịch kiểm, tổng tiền… |

Registry theo lượt gồm `ref → productId + source_call_ids + facts + freshness + presented_to_orc`.
Mã từ lịch sử vẫn nhận diện được sản phẩm, nhưng muốn đưa lại thẻ hoặc facts thì phải tra trong lượt này.
Chỉ ref đã cung cấp cho orc mới được chọn vào final; code không tự chọn sản phẩm từ kho kết quả chưa trình cho orc.
Cache chi tiết chỉ trong lượt; tra lại giữa hai lượt. Cùng một sản phẩm từ hai nguồn dùng một ref, giữ cả provenance.

Con trỏ opaque do server cấp, gắn owner/conversation/run/query fingerprint. Orc chỉ copy nguyên con trỏ;
đổi filter thì mở truy vấn mới. Offset hạ tầng do adapter tính. Nguồn không hỗ trợ pagination (Recommendation,
Similar hiện tại) phải báo `next_cursor=null`; không giả lập phân trang bằng gọi lại cùng kết quả.

### 9.3. Bảng tham số tối thiểu cho tám tool

Quy ước chung: field tùy chọn bỏ trống là không áp filter mới, không tự kế thừa ngầm. Orc phải truyền lại các
điều kiện muốn giữ. Field nullable có `null` cũng nghĩa không lọc, trừ nơi ghi khác. Currency bước đầu chỉ VND.
Không nhận `userId`, JWT, connection string, URL tùy ý hay tên hàm nội bộ từ model.

| Tool | Arguments phải định nghĩa và mô tả |
|---|---|
| Search | `query` bắt buộc 1–500 ký tự; `destination`, `taxonomy`, `priceMin/Max` theo giá đơn vị API, `travelContext`, `availableOnly` theo SearchRequest; `limit` 1–50 mặc định 20; `cursor` tùy chọn; wrapper `cost_mode=any|free_only` mặc định any, `exclude_refs=[]`. Ràng buộc wrapper phải hậu kiểm có căn cứ; schema sinh từ API chỉ giới thiệu các field đã thực sự hỗ trợ ở adapter đang dùng. |
| Recommendation | `k` 1–20 mặc định 5; `destination` tùy chọn. Không thêm query, taxonomy hay budget khi API chưa hỗ trợ. Trả `strategy/because`; muốn lọc thêm, orc dùng facts hoặc gọi Search. |
| Similar | `product_ref` bắt buộc là ref đã biết, adapter ánh xạ productId; `limit` theo đúng bounds/default của `/products/{productId}/similar`, không chép số riêng. Không buộc Search sau Similar. |
| Detail | `product_ref` bắt buộc. Phiên bản đầu giữ đọc một sản phẩm mỗi call để không mở rộng schema không cần thiết; tận dụng cache trong lượt. Nếu batch là cần thiết theo số đo, bổ sung schema riêng trước khi code batch. |
| Destinations | `{}`. Không dựa trên tên tỉnh do model tự tạo; trả nơi đang có catalog và thông tin tuyến nếu nguồn có. |
| Catalog list | `destination`, `taxonomy`, `parent_ref` tùy chọn; `availableOnly`, `sort`, `limit` lấy enum/default/bounds từ catalog contract, `cursor` tùy chọn. `parent_ref` ánh xạ ID trước khi gọi port. `cost_mode`, `exclude_refs` hậu kiểm như Search; không tự thêm query semantic. |
| Flights | `origin`, `destination` nullable để trả needs_input; `departure_date`, `return_date` ISO nullable; `trip_type=one_way|round_trip|any` mặc định any; `time_of_day=early|morning|afternoon|evening` nullable; `sort=price_asc|price_desc|departure_asc` mặc định price_asc; `limit` 1–20 mặc định 10; `cursor` tùy chọn; `exclude_refs=[]`. Không có điểm đến và người dùng muốn đi đâu cũng được: orc lấy destinations rồi chọn tuyến để tra; không quét toàn bộ tuyến ngầm. |
| Itinerary | `trip`, `draft`, `constraints`, `locked`, `optimization`, `pace` theo §4 và §9.4. Tool chỉ nhận ref, không nhận bản sao sản phẩm/giá do orc tự viết. |

Search free_only: không chỉ truyền từ “miễn phí” trong query. Adapter hậu kiểm ticketed/price có căn cứ,
trả unknown-price count riêng. `priceMax=0` một mình không chứng minh miễn phí khi API xử lý null/giá tầng cha khác nhau.
Flights khung giờ theo AC-AGT-08; trả cả `date_range_scanned` và mức complete. Không đủ phạm vi thì không gọi là
rẻ nhất toàn đợt. Nhu cầu về hành lý/điều kiện vé mà catalog không có phải trả unknown.

### 9.4. Tool lập lịch: cấu trúc draft, tính tiền và tối ưu

- `trip`: destination, start_date ISO, days theo giới hạn chuyến của contract, adults/children; ngày/bên đi đã biết
  phải khớp context. Không có nơi đi vẫn được lập lịch không vé. Không đủ trường bắt buộc trả needs_input.
- `draft.days`: mỗi ngày có day_index từ 1..days, `activities` thứ tự orc chọn. Activity gồm `product_ref`,
  `start_minute/end_minute` 0..1440, `timing_source=catalog|estimate`, `assumption` khi estimate.
  End phải lớn hơn start; buổi hiển thị suy từ giờ, không dùng enum buổi để ép một hoạt động mỗi buổi.
- `draft.stays`: ref + check_in/check_out; nights lấy chênh ngày thật. Rỗng là không lưu trú. Có stay thì
  check_out phải sau check_in; không tạo stay zero-night. Trẻ em/số phòng theo luật giá hiện tại đã kiểm.
- `draft.flights`: ref + vai trò outbound/return/round_trip; xác minh ngày/giờ theo dữ kiện, không lấy giờ model khai.
- `constraints.trip_budget_vnd`: nullable, **warning-only**. Budget 0 là giá trị hợp lệ khác null. Các điều kiện
  `free_only`, exclude taxonomy/ref, địa điểm/ngày/sản phẩm khóa kiểm riêng, không gom mọi thứ thành budget error.
- `locked`: refs và các vị trí/thời gian khóa. `optimization=none` giữ nguyên toàn bộ draft; reorder chỉ trong
  ngày; reassign chỉ đổi các mục không khóa. Không có quyền thay tập sản phẩm ở bất cứ chế độ nào.
- `pace`: relaxed/balanced/busy để orc giải thích nhịp; phiên bản đầu không gán số hoạt động hay phút ngầm theo enum.
  Thời gian nghỉ/di chuyển phải hiện rõ trong draft dưới dạng estimate nếu chưa có nguồn. Không gọi OSRM từ
  domain hoặc quy đường chim bay thành phút bằng tốc độ tự đặt.
- Với dữ kiện giờ/thời lượng đủ: kiểm overlap, cửa sổ ngày, giờ mở có nguồn, khoảng đệm chuyến bay và thời gian nghỉ.
  Với dữ kiện thiếu: vẫn kiểm tính nhất quán của draft nhưng `feasibility=provisional`, cảnh báo chưa xác minh.
- Tối ưu chỉ dùng tọa độ đủ tin cậy; thiếu thì giữ thứ tự, trả `OPTIMIZATION_UNAVAILABLE`. Không bắt buộc đổi cho có.
  Kết quả phải giữ multiset refs và locked positions; test assert hai invariant này trước kiểm khoảng cách.

`build_itinerary.data` trả `plan_result_id`, `draft_revision`, `plan`, `feasibility=verified|provisional|infeasible`,
`costs`, `changes`, `violations`, `warnings`. Verified chỉ trong phạm vi dữ kiện catalog, không phải bảo đảm
tồn kho thực tế hay đã đặt chỗ. `plan_result_id` server sinh, bất biến và chỉ thuộc lượt/owner hiện tại.

`costs`: `known_subtotal_vnd`, `estimated_total_vnd` (null khi còn khoản sản phẩm chưa biết), `unpriced_refs`,
`trip_budget_vnd`, `over_by_vnd` (null khi không đủ tổng hoặc không có budget), `budget_status=not_set|within|over|unknown`,
`coverage_notes`. Không cộng các thẻ phương án khác hoặc toàn bộ gợi ý vào tiền lịch.

Ví dụ kiểm bắt buộc: tổng 2.300.000, budget 2.000.000 → over_by=300.000, status over, **không infeasible**.
Biết 1.000.000 và còn một giá null → total=null, status unknown, không báo còn dư 1.000.000.
Biết 2.300.000 và còn giá null → chỉ được nói “phần đã biết đã vượt ít nhất 300.000”; total/over_by vẫn null,
lower bound có fact riêng nếu trình bày. Không coi tổng phần đã biết là tổng hoàn chỉnh.

## 10. Guardrail: vị trí kiểm và cách xử lý

### 10.1. Kết quả guardrail có cấu trúc

Mỗi kiểm tra trả `GuardrailIssue{code,severity,call_id?,field?,refs[],safe_message,required_disclosure?}`.
Severity gồm `fatal` (chặn truy cập/thực thi nguy hiểm), `repair` (orc sửa hành động/đầu ra), `warning`
(vẫn được hoàn thành nếu trình bày đúng). Không dùng một boolean blocked cho cả ba mức.

| Vị trí | Ví dụ | Xử lý |
|---|---|---|
| Trước orc | Auth/owner sai, đầu vào NFR-SEC-04, rate limit | Giữ lớp hiện có và response lỗi an toàn; không gọi model để vượt chặn. |
| Trước tool | TOOL_NOT_ALLOWED, INVALID_ARGUMENTS, UNKNOWN_REF, CURSOR_SCOPE_MISMATCH | Không thực thi call đó; trả lỗi cho orc. Các call độc lập hợp lệ vẫn chạy. Không thay args/call khác. |
| Trước tool | CROSS_OWNER_ACCESS, SECRET_EXPOSURE | Fatal; dừng phần vi phạm, không đưa dữ liệu bị cấm vào context/log. |
| Sau tool | Schema nguồn sai, timeout, HTTP failure | unavailable/failed; giữ phần thành công, không biến thành empty. |
| Kiểm lịch | LOCKED_ITEM_CHANGED, TIME_OVERLAP, EXCLUDED_TAXONOMY | Repair; orc quyết định sửa draft, không tự bỏ/thay sản phẩm. |
| Kiểm tiền | OVER_TRIP_BUDGET | Warning; vẫn nhận lịch và cho final nếu có disclosure đúng. Không ép retry tool. |
| Kiểm dữ kiện | PRICE_UNKNOWN, OPENING_HOURS_UNKNOWN, PARTIAL_COVERAGE | Warning; cho final với phạm vi/độ chưa chắc chắn rõ; không cho khẳng định giá/giờ đã biết. |
| Trước final | UNGROUNDED_REF, UNSUPPORTED_FACT, FALSE_BOOKING_CLAIM | Repair; sửa lời đáp, không bù thẻ. Không sửa được trong ngân sách thì thông báo hệ thống ngắn. |
| Trước final | MISSING_BUDGET_DISCLOSURE | Repair **câu trả lời**, không chặn vì lịch vượt tiền và không buộc tìm lại. |
| Trước final | TAXONOMY_CARD_LIMIT (11 thẻ một loại) | Repair để orc chọn lại tối đa 10; không slice lấy 10 thẻ đầu. |
| Runtime | TIME_LIMIT, ROUND_LIMIT, TOOL_LIMIT, MODEL_TIMEOUT | Dừng gọi thêm theo loại giới hạn; cho orc chốt nếu còn deadline/quota model được dành; không còn thì error ngắn. |

`disclosures` trong OrcDecision tham chiếu warning_id/fact_ref từ tool. Renderer chỉ điền số và câu báo chuẩn
cho disclosure orc đã chọn. Không được bỏ cảnh báo over/unknown của plan được final tham chiếu. Điều kiện pass
final: mọi cảnh báo bắt buộc của plan đã được công bố, không phải lịch nằm trong budget.

Điểm có phí trước yêu cầu “chỉ miễn phí” không được gắn nhãn matching. Orc có thể trình bày riêng trong
`alternatives` với `violates=[free_only]` và disclosure rõ chưa đáp ứng, không tự đưa vào lịch miễn phí đã chốt.
Alternative vẫn tính vào trần 10 của taxonomy. Phương án thay thế không được dùng để lách lỗi nguồn/owner/ngày
không hợp lệ. Nhận miễn phí/unknown theo §2.5, không đổi user budget về 0 một cách suy diễn.

### 10.2. Không để lớp kiểm biến lại thành workflow

- Validator không được tự gọi Search, Rec, Flights hoặc build_itinerary. Khi thiếu dữ kiện, trả danh sách field
  thiếu; orc tự chọn cách lấy.
- Không phát sinh call/selection từ regex ý định. Luật bảo mật/kiểu dữ liệu vẫn tất định.
- Không dùng LLM guardrail thứ hai bắt buộc cho mọi lượt trong đợt đầu; kiểm dữ liệu bằng code và eval các
  lỗi ngôn ngữ. Mô tả catalog luôn là dữ liệu không tin cậy, không ghép vào system instruction.
- Model không được tắt guardrail, tăng giới hạn hay viết các field server-owned. Schema exclude các quyền đó.
- Test phải kiểm cả false-positive: lịch vượt budget vẫn đi hết finalize; câu hợp lệ ngắn không bị junk filter.

## 11. State, vòng lặp và cập nhật hội thoại

### 11.1. Phân quyền field

| Field | Ai ghi | Khi lưu lâu hơn lượt |
|---|---|---|
| context/constraints/pending | Orc đề xuất patch, server kiểm rồi áp | Sau final hợp lệ; lỗi terminal không ghi patch mới. |
| registry/tool_results/cursors/cache | Dispatcher | Không lưu facts giá/availability để tái dùng ở lượt sau. |
| execution_budget/rounds/deadline | Runtime | Chỉ trong lượt; orc được đọc mức còn lại, không sửa. |
| candidate_plan_results | Tool build_itinerary | Chỉ trong lượt, chưa thay committed plan. |
| committed_plan/revision | Finalize | Chỉ khi plan_effect=replace hợp lệ; hỏi vé giữ nguyên revision. |
| shown | Finalize | Chỉ refs trong câu trả lời hiển thị cuối; một lần/run, không theo search/preview. |

Giữ lịch sử đọc được của hội thoại cũ. Khi restore thiếu schema_version, coi là legacy, lấy intent/refs/lịch
đang dùng và đánh dấu facts cần refresh; không tái chạy workflow cũ chỉ vì hội thoại cũ. Mọi chuyển đổi có test fixture.

### 11.2. Thuật toán vòng lặp dùng để viết test

```text
1. Load state theo owner; chụp committed revision; input guardrail.
2. Gọi orc với context, tools được phép, kết quả hiện có và giới hạn còn lại.
3. Nếu execute:
   a. Kiểm schema/refs/quyền/điều kiện từng call; trả lỗi an toàn cho call sai.
   b. Dành quota trước await; chạy các call hợp lệ độc lập.
   c. Ghi mọi kết quả kể cả partial/error, cấp refs; quay bước 2.
4. Nếu respond:
   a. Kiểm refs, facts, card limits, disclosure và quyền đổi plan.
   b. Repair được và còn quota sửa → trả issue về orc, quay bước 2.
   c. Hợp lệ → hydrate/render thuần từ lựa chọn đó; kiểm response contract.
   d. Lưu final, shown và plan effect đúng một lần; kết thúc.
5. Fatal/model lỗi/hết deadline không có final hợp lệ → báo ngắn, giữ committed plan.
```

Baseline kỹ thuật để triển khai và đo: tối đa 3 batch execute, 3 calls/batch, 10 request nguồn vật lý,
1 lượt sửa final và 1 lượt final sau batch cuối; model calls tổng tối đa 5 (4 quyết định thông thường + 1 repair).
Call build_itinerary tính trong batch/call logic dù không dùng network. Cache hit không tốn request nguồn nhưng
vẫn tính call logic; request nguồn retry tính thêm một request, retry transient tối đa một lần cùng args.
Tất cả retry/repair/terminal model calls nằm trong deadline hiện có, không tự kéo dài timeout.
Dành thời gian final theo timeout model cấu hình; nếu không đủ thì không bắt đầu batch mới. Giá trị tối ưu
cho rollout phải có số đo P5; baseline không phải tuyên bố 3 vòng luôn đủ cho 30 gợi ý.

Batch kết quả giữ thứ tự call_id ban đầu, không dựa vào thứ tự task async hoàn tất. Lời gọi thành công trùng
fingerprint được trả cached result; lời gọi thất bại retryable không bị ghi cờ “đã xong”. Cùng call vô hiệu lặp
lại tính vào giới hạn model, không tạo vòng sửa vô tận. Khi nguồn trả partial vẫn giữ items/facts đã hợp lệ.

## 12. Các gói việc giao cho coding agent

Đây là các bước nhỏ bên trong P0–P6. Hoàn thành cổng kiểm của bước trước mới làm bước sau. Mỗi bước ghi
history và danh sách file thực tế. Chỉ đọc/sửa các phần liên quan; không đổi thuật toán Search/Rec, không đổi DB.

| Bước | Phụ thuộc | File/symbol chính | Công việc và đầu ra | Cổng kiểm |
|---|---|---|---|---|
| E00 | Chốt đề xuất | PRD và plan | Áp §2, lập bảng AC giữ/thay; chuyển plan sau PRD; đọc đủ AGENTS §1 | Không còn mâu thuẫn đã biết giữa PRD mới và plan; ghi baseline fail hiện có |
| E01 | E00 | contracts assistant v2, mocks, validator | Định nghĩa request/final/event theo §13, tách version; fixture budget over/unknown/30 thẻ/0 đêm | Validate contract pass trước implementation |
| E02 | E01 | `agents/models.py`; **mới** `application/itinerary/orc_contracts.py` | OrcDecision union + ToolResult + GuardrailIssue; mô tả field đệ quy; schemas lỗi/final | Test schema reject tên tool/args lạ, field thiếu mô tả; không đổi graph đang phục vụ |
| E03 | E02 | **mới** `application/itinerary/product_registry.py`; `steps/shown.py` | Ref/provenance/current-turn freshness; con trỏ có scope; cache trong lượt | Test stale/cross-owner/unpresented refs, cùng product hai nguồn một ref |
| E04 | E03 | gateway/tool_contracts/ports | Expose sáu tool hiện có với args §9.3, adapter mapping rõ, giữ description | Test actual definitions gửi model và fake ports ghi đúng args, không gọi tool ngoài yêu cầu |
| E05 | E04 | **mới** `application/itinerary/flight_lookup.py`; flights/fares helpers | Trả dữ kiện vé/coverage/needs_input; tách khỏi formatter | Test ngày/giờ/phạm vi/partial; kết quả không chứa câu trả lời cuối hoặc chọn vé mặc định |
| E06 | E03 | **mới** `domain/itinerary/draft_validation.py`; **mới** `application/itinerary/build_itinerary.py` | Kiểm draft, tính tiền, tối ưu có quyền; reuse hàm thuần đã audit, không gọi compose_plan để chọn lại | 0 đêm/4 hoạt động/locked/unknown/over pass đúng semantics; multiset refs giữ nguyên |
| E07 | E04–06 | **mới** `domain/itinerary/orc_guardrails.py`; existing guardrails.py | Các mã/severity §10, không import agents vào domain/application | Unit cả allow/repair/fatal/warning; architecture test pass |
| E08 | E07 | graph/routing/orchestration/runtime_dependencies | Vòng §11; decisions/dispatch/repair/finalize; không edges nghiệp vụ cũ trên graph v2 | Scripted model trace: tool và selection đúng hoàn toàn; budget concurrency/partial/retry |
| E09 | E08 | finalize/store/archive/phase helpers | Chỉ commit final hợp lệ; restore legacy; revision và run idempotency | Lượt hỏi vé/lỗi/preview không đổi plan; run lặp không ghi hai final; owner isolation |
| E10 | E09 | API v2/use case port/composition root | HTTP/SSE mới, giữ v1 trong giai đoạn tương thích; BFF proxy đúng version | Integration parity, auth/error/cancel, không ghi vào conversation người khác |
| E11 | E10 | assistantStream/state/provider/widget | Render taxonomy10, nhiều slots, cảnh báo tiền, tiến trình động; giữ giá trị null/0 khác nhau | Vitest/typecheck/build và E2E thẻ, plan, chọn phương án, lỗi, stream |
| E12 | E11 | tests + snapshot/runner hiện có | Chạy §6 và §14 với model/công cụ thật; ghi trace và số đo; review cassette diff | Không gọi scripted model là bằng chứng tự chủ LLM; các tiêu chí P5 đạt hoặc báo fail cụ thể |
| E13 | E12 | docs + source obsolete | Chuyển client; dọn theo call-site và trạng thái v1 | Không xóa helper v1 đang dùng; regressions/contract/full suites; đóng các AC tồn đọng có bằng chứng |

Tên mới trong bảng là nơi sở hữu đề xuất: domain là hàm thuần; application gọi ports; agents điều phối model;
infrastructure hiện thực truy cập. Khi file đã có lúc bắt đầu implement, đọc và mở rộng đúng trách nhiệm,
không ghi đè. E05 và E06 có thể làm độc lập nhưng bảng không yêu cầu spawn agent.

Quy tắc tái sử dụng:

- `planning.py::{cost_breakdown,totals,price_plan,day_windows}` là ứng viên tái dùng sau audit: các hàm này có thể
  mang assumption 1 đêm hoặc free khi thiếu giá; không gọi nguyên trạng rồi giả định đúng với v2.
- `compose_plan`, `keep_rank`, `_activity_order`, `_stay_order`, `_layout` không được dùng để chọn thay orc.
  Chỉ tách phép tính thuần cần thiết; `validate_plan` cũ phải kiểm lại luật cap/ngày/khách sạn trước tái dùng.
- `gatekeeper.render` hiện có thể bổ sung nội dung: v2 renderer phải thuần theo refs/disclosures đã chọn.
- `tool_planning.validated_plan`, `_count_continuations`, `fare_button_turn`, `apply_option` là các vị trí cần
  kiểm để không đi đường tắt vào final v2. Không xóa chúng nếu v1 còn dùng.

## 13. Đường chuyển API và UI cần triển khai

Thiết kế đường dẫn đề xuất: `POST /api/v2/assistant/itineraries` và `/api/v2/assistant/itineraries/stream`.
Đặt router/use case adapter theo cùng quy tắc dependency như v1. OpenAPI v2 dùng entrypoint riêng
`src/shared/contracts/assistant-v2.openapi.yaml` với schemas/paths v2 riêng để không trùng server prefix v1;
validate_contract phải kiểm cả hai entrypoint. Frontend sinh `assistant-v2.gen.ts` riêng, không sửa tay types.
Đây là bổ sung cấu trúc contract phải ghi PRD architecture §6 ở E00 trước khi tạo file.

Request v2: các field ngữ cảnh có sẵn được map rõ; thêm `clientTurnId`, `basePlanRevision` và
`uiAction` có schema cho chọn phương án/nút vé (camelCase ở API; snake_case chỉ nội bộ).
Không cho request truyền dữ kiện giá hay tool permissions.
Server kiểm revision trước khi thay lịch; xung đột trả controlled conflict, không âm thầm ghi đè.

Response v2 tối thiểu gồm `conversationId`, `runId`, `turnKind`, `message`, `recommendations` theo taxonomy,
`alternatives` có disclosure, `itinerary` nullable, `planEffect`, `planRevision`, `warnings`, `suggestions`.
`turnKind=answer|clarification|itinerary|partial`; lỗi dùng Error Envelope của dự án. Không dùng
NEEDS_CLARIFICATION để đánh dấu mọi câu trả lời thông thường. Trường của ProductSummary tái dùng contract nguồn.
`planEffect=keep` không xóa lịch đang hiển thị khi response.itinerary=null. Limits gợi ý kiểm hợp recommendations
và alternatives; duplicates không được dùng để đủ số. E01 phải khai đầy đủ required/nullable/discriminator,
không dùng additionalProperties tự do cho phần nghiệp vụ.

SSE v2 dùng start/activity/tool-completed/preview/final/error theo schema định nghĩa E01; mỗi event có runId
và sequence tăng. Final chỉ một; preview không có hành động đặt/chọn và không commit state. Frontend bỏ event
trùng hoặc sai run, thay nhóm theo groupId chứ không cộng số lũy kế. Mất kết nối không tự gửi lại một lượt mới:
dùng clientTurnId: gửi lại cùng endpoint, cùng nội dung thì trả final đã có, đang chạy thì trả 409
`TURN_IN_PROGRESS` kèm Retry-After; cùng ID khác nội dung trả 409 `IDEMPOTENCY_CONFLICT`.
Claim owner/conversation/clientTurnId phải nguyên tử ở store dùng chung, không khóa trong memory một worker.
Lưu claim/kết quả theo TTL working memory hiện có; chưa bảo đảm qua sự cố store thì báo phạm vi này rõ.
Không tự thêm bảng DB. Nếu port/store chưa làm được, hoàn thiện adapter và test concurrency trước khi E10 đạt.
Không stream lời đáp sản phẩm chưa qua kiểm guardrail; tiến trình không được tính là first text token trong báo SLA.

Giai đoạn tương thích: v1 tiếp tục hành vi cũ cho client cũ, v2 dùng graph mới. Đây là version adapter,
không phục hồi cờ orchestrator hay classifier đã xóa. Widget chuyển v2 sau E12. Chỉ xóa code v1 khi đã kiểm
inventory client (web, Streamlit, golden runner, scripts) và có quyết định ngừng v1; trước đó E13 chỉ xóa ký hiệu
không còn call site. Không ép client v1 nhận semantics v2 và không xóa workflow đang phục vụ v1 cho “sạch”.

## 14. Test bàn giao, lệnh kiểm và điều kiện dừng

### 14.1. Ca guardrail/budget bổ sung cho §6

| ID | Given / When | Then bắt buộc |
|---|---|---|
| G01 | Budget 2 triệu, tool tính 2,3 triệu, orc công bố chênh 300 nghìn | Final thành công, lịch hiển thị/lưu được, warning OVER_TRIP_BUDGET, không tự tìm lại hoặc đổi refs |
| G02 | Như G01 nhưng orc không công bố cảnh báo | Một repair về orc yêu cầu disclosure; không gọi Search; sửa xong final thành công |
| G03 | Một sản phẩm thiếu giá | total/over_by null, budget_status unknown, không nói miễn phí hay “trong ngân sách” |
| G04 | Budget 0, sản phẩm có phí | Over warning, không bị nhầm null hoặc chặn lịch chỉ vì tiền; nếu free_only thì kiểm nhãn/phạm vi riêng |
| G05 | Miễn phí nhưng muốn nêu phương án có phí | Alternative có disclosure; không lẫn vào lịch được gọi là miễn phí; count chung ≤10/taxonomy |
| G06 | 10 hotel + 10 attraction + 10 combo | Không bị trần tổng 20; 11 hotel trả repair, không tự cắt còn 10 |
| G07 | Ref không có nguồn hoặc chỉ có ở lượt trước | Không render thẻ; orc nhận lỗi để tra lại; không bù sản phẩm khác |
| G08 | Tool timeout sau một trang thành công | partial giữ dữ kiện trang đầu; không nói toàn catalog rỗng/đã quét hết |
| G09 | Hai call song song khi còn một request vật lý | Chỉ một được cấp quota; call kia nhận TOOL_LIMIT, không vượt 10 do race |
| G10 | Orc lặp quyết định sai/repair quá giới hạn | Kết thúc trong 5 model calls và deadline, báo lỗi ngắn, không tự chọn thẻ |
| G11 | Orc thay sản phẩm/mốc khóa trong tool tối ưu | Repair; committed plan/revision không đổi |
| G12 | UI action hoặc final gửi lặp, hoặc hai tab cùng sửa revision | Không ghi hai final, không silently overwrite revision; lỗi an toàn/return kết quả cũ theo idempotency |

Test mới dự kiến: `test_orc_contracts.py`, `test_orc_registry.py`, `test_orc_tool_dispatch.py`,
`test_orc_loop.py` dưới `src/backend/tests/unit/agents/` khi kiểm agent; test application/domain đặt đúng
thư mục tương ứng (`test_build_itinerary.py`, `test_orc_guardrails.py`). Không import agents vào application test
để lách layering. API v2 có `test_assistant_v2_contract.py`; frontend có test service/progress/renderer v2.

### 14.2. Lệnh kiểm (sau implement, chưa chạy trong lần sửa tài liệu)

Chạy từ repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false SEARCH_PREWARM=false WEAVIATE_URL=http://127.0.0.1:1 .venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/unit/application src/backend/tests/architecture
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false SEARCH_PREWARM=false WEAVIATE_URL=http://127.0.0.1:1 .venv/bin/python -m pytest -q src/backend/tests/contract
npm --prefix src/frontend run typecheck
npm --prefix src/frontend run test:unit
npm --prefix src/frontend run build:web
git diff --check
```

Ở E01/E11 thêm script sinh types v2 theo entrypoint mới trước khi gọi; script hiện tại chỉ sinh v1.
E2E dùng script `test:e2e` của frontend và các ca widget v2 tạo ở E11; giữ cổng test riêng theo config repo.
E12 chạy full backend/frontend phù hợp và snapshot offline sau khi ghi/review mới; không ignore test đỏ để báo all-pass.
Nếu môi trường thiếu tool/dependency hoặc integration phải dùng DB thật, báo đúng phần chưa chạy và dùng hướng dẫn
repo; không cài mới/migrate/reset DB hoặc sửa cấu hình VM chỉ để thực hiện plan này.

### 14.3. Mẫu bàn giao cho mỗi bước

Ghi: bước E nào; FR/AC liên quan; file đã sửa; test mới và tình huống chứng minh; lệnh/mã thoát/kết quả;
ref PRD đã chốt; rủi ro/tồn đọng; bước kế tiếp và điều kiện vào bước đó. Đối chiếu git status, tạo history
mới; không sửa entry cũ. Đọc plan không được coi là đã đọc source hoặc đã chạy test.

Dừng phần phụ thuộc và hỏi khi: thay đổi chưa được PRD cho phép; cần nguồn dữ kiện/API mà contract không có;
cần tăng budget/SLA hoặc thay mục tiêu người dùng; cần ngừng v1 mà chưa duyệt client migration. Khi gặp dữ kiện
thời gian/giá thiếu, dùng unknown như thiết kế chứ không hỏi người dùng để cho phép bịa. Lỗi kỹ thuật sửa được
trong phạm vi thì tự sửa và kiểm lại, không xin chốt từng dòng code.

Đánh giá mức sẵn sàng: đủ chi tiết để giao từng bước sau phê duyệt, với cổng schema/fixture trước runtime.
Không giao toàn bộ P0–P6 như một lệnh sửa một lần; E00/E01 phải được kiểm xong trước khi chuyển cho agent thực thi E02.

### 14.4. Ví dụ kiểm xuyên suốt: vượt tiền không chặn

Dữ liệu dưới đây chỉ là fixture minh họa cho test, không phải giá sản phẩm thật và không dùng cho demo:

```json
{
  "costs": {
    "known_subtotal_vnd": 2300000,
    "estimated_total_vnd": 2300000,
    "unpriced_refs": [],
    "trip_budget_vnd": 2000000,
    "over_by_vnd": 300000,
    "budget_status": "over",
    "coverage_notes": ["Chỉ gồm sản phẩm trong lịch; chưa gồm ăn uống và di chuyển tự túc"]
  },
  "violations": [],
  "warnings": [{"id": "w1", "code": "OVER_TRIP_BUDGET", "severity": "warning"}]
}
```

Chạy test lần lượt: (1) build_itinerary trả như trên và không infeasible; (2) orc nhận warning w1, chọn công bố
tổng/budget/chênh qua fact refs và giữ plan_result_id; (3) guardrail cho qua; (4) renderer hiện 2,3 triệu, vượt
300 nghìn và phạm vi chi phí; (5) finalize lưu đúng refs orc đã chọn, không phát sinh tool call phụ.
Biến thể bỏ disclosure w1: guardrail trả MISSING_BUDGET_DISCLOSURE, orc chỉ sửa final, tool count không tăng.
Biến thể đổi số chênh thành 200 nghìn: không cho qua phép tính sai dù đã có dòng cảnh báo.
