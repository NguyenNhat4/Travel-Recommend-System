# Giữ phần hợp lệ khi một slot vi phạm quy tắc xếp lịch

- Ngày: 2026-09-20
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, docs

## Mục tiêu

Câu demo chuẩn `đi Nha Trang 2 ngày từ ngày mai` trả `FALLBACK` 3/3 lần với model thật và fixture 50 sản phẩm. Nguyên nhân: `_composition_input` đưa cả `combo` vào danh sách candidate cho LLM chọn, LLM xếp combo Hòn Tằm vào slot ngày 1 NOON, `render_proposal` `raise ValueError("invalid product selection")` và `answer_node` bắt exception rồi vứt **toàn bộ** lịch trình — mất luôn khách sạn và hai hoạt động hoàn toàn hợp lệ.

Dữ liệu không thiếu: chạy `_drop_reason` và `render_proposal` trực tiếp trên fixture (không qua LLM) cho thấy Nha Trang 2 ngày dựng được lưu trú + 2 hoạt động. Khoảng cách giữa mức đó và `FALLBACK` là lỗi của code, không phải của mock data.

## File thay đổi

- `src/backend/app/domain/itinerary/planning.py` — thêm: hằng `STAY_TAXONOMY`, `SLOT_TAXONOMIES`, `SCHEDULABLE_TAXONOMIES` thay cho literal lặp trong `render_proposal`; hàm `render_best_effort` dựng lịch theo từng slot và chỉ bỏ slot bị quy tắc từ chối, trả về `(plan, dropped)`.
- `src/backend/app/agents/nodes.py` — sửa: `_composition_input` bỏ qua candidate ngoài `SCHEDULABLE_TAXONOMIES` trước khi dựng prompt; `_composed` dùng `render_best_effort` và thêm warning `SLOT_DROPPED_UNSCHEDULABLE` cho mỗi mục bị bỏ; `evaluate_node` dùng các hằng taxonomy thay literal.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: `ScriptedLlm` ghi lại prompt theo schema (`self.prompts`); tách `test_unknown_or_duplicate_ids_never_complete` thành `test_an_invented_id_never_completes` (giữ `FALLBACK`) và `test_a_duplicate_id_is_dropped_instead_of_discarding_the_itinerary`; thêm `test_an_unschedulable_taxonomy_is_dropped_and_never_reaches_the_model` tái hiện đúng case combo của Nha Trang.
- `docs/agent/langgraph-nodes.md` — sửa: dòng node `answer` trong bảng chín node ghi rõ candidate đưa cho LLM chỉ gồm ba taxonomy xếp lịch được, và slot vi phạm bị bỏ riêng kèm warning thay vì làm mất cả lịch trình.
- `history/2026-09-20-keep-valid-slots-when-composition-breaks-a-rule.md` — thêm: entry này.

## Quyết định

- **Không nới lỏng quy tắc nào.** `render_best_effort` thêm từng slot rồi gọi lại chính `render_proposal`; slot nào không qua thì bỏ. Kết quả tuân thủ đúng bộ luật cũ, chỉ khác ở chỗ một slot hỏng không kéo theo cả lịch trình. `validate_plan` ở `finalize` vẫn là tiếng nói cuối cùng về grounding và `require_hotel`.
- **ID model bịa ra vẫn `raise`.** Nếu có `product_id` không nằm trong `candidates` thì đó là lỗi grounding của cả đề xuất chứ không phải một slot xấu, nên không được "sửa" im lặng thành `COMPLETED`. Test `test_an_invented_id_never_completes` khoá hành vi này.
- **Lỗi cấp đề xuất không sửa được:** số ngày không hợp lệ và `stay_id` sai taxonomy vẫn `raise` như cũ (`render_proposal` với proposal rỗng được gọi trước vòng lặp để phân biệt).
- **Bịt lỗi từ đầu thay vì chỉ chữa hậu quả:** `flight` và `combo` chưa có mapping slot nào được chốt nên không bao giờ xếp lịch được; đưa chúng vào prompt rồi phạt LLM vì chọn là tự đặt bẫy. Chúng vẫn nằm trong `candidates` và vẫn hiện trong `searchResults` của `FALLBACK`.
- **Mã warning mới `SLOT_DROPPED_UNSCHEDULABLE`:** `ItineraryWarning.code` trong `schemas/itinerary-agent.yaml` là `type: string` tự do (mô tả nêu ví dụ, không phải enum), nên không cần đổi OpenAPI. Không sửa contract, không sửa mock.
- Không đụng tới `flight`/`combo` trong lịch trình: muốn xếp được chúng thì cần quyết định nghiệp vụ mới, không phải thay đổi kỹ thuật.

## Kiểm tra

- `LANGSMITH_TRACING=false pytest src/backend/tests`: **97 passed** (trước thay đổi là 95).
- `validate_contract.py`: **PASS** (63 schemas, 50 grounded products, 4 itinerary statuses, 50 fixtures; CDP clone 12 schemas). Chạy để xác nhận không có gì vỡ, dù thay đổi này không chạm contract.
- **Chạy thật với model và fixture 50 sản phẩm**, câu `đi Nha Trang 2 ngày từ ngày mai`, 3 lần: **COMPLETED 3/3**, `validation_issues=[]`, 11,6s / 6,2s / 6,6s. Kết quả mỗi lần: lưu trú Vinpearl Beachfront Nha Trang 1 đêm, ngày 1 MORNING VinWonders, ngày 2 MORNING voucher golf, các slot còn lại MEAL/FREE_TIME, `bookableCount=3`, `estimatedTotal=null` + `budgetStatus=UNKNOWN`.
- Trước thay đổi, cùng câu đó và cùng fixture cho `FALLBACK` 3/3 lần.
- Không có warning `SLOT_DROPPED_UNSCHEDULABLE` nào trong ba lần chạy thật: combo đã bị lọc khỏi prompt nên LLM không còn đề xuất nó, nhánh sửa chữa chỉ là lưới an toàn.

## Còn lại / rủi ro

- `estimatedTotal` vẫn luôn `null` với fixture này vì cả 50 sản phẩm đều có `priceUnit=UNKNOWN`. Đây là mục **chờ xác nhận** về đơn vị giá trong `docs/spec/contract-baseline-v1.1.md`, không phải lỗi của thay đổi này. Không tự điền `priceUnit` vào mock để demo ra tổng tiền.
- Latency 6–12 giây vẫn vượt mục tiêu p95 dưới 5 giây ở `hop-dong-tich-hop-itinerary-assistant.md` §7.2; ba lời gọi LLM tuần tự (classify 2s + tool plan 2s + compose 3s) đã vượt ngân sách ngay cả khi đúng hạn. Chưa xử lý trong thay đổi này.
- `render_best_effort` gọi lại `render_proposal` một lần cho mỗi slot (O(n²) với n ≤ khoảng 10 slot, hàm thuần, vài mili giây). Nếu số slot lớn lên nhiều thì cần dựng tăng dần có trạng thái thay vì render lại.
- Việc chọn sản phẩm nào và xếp vào ngày nào vẫn do LLM quyết; thay đổi này chỉ ngăn một lựa chọn sai phá hỏng cả lịch trình, chưa thay bằng thuật toán tất định.
- Mỗi điểm đến trong fixture chỉ có tối đa 2 sản phẩm xếp lịch được, nên chuyến từ 3 ngày trở lên chắc chắn có ngày trống. Muốn demo dài hơn thì phải bổ sung `attraction` vào fixture.
- `docs/agent/rubric.md` đang ở trạng thái đã xóa trong `git status` từ trước và chưa có entry nào ghi nhận; không thuộc thay đổi này.
