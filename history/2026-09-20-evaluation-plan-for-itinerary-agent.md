# Kế hoạch đánh giá Itinerary Agent chạy tay, xóa tài liệu runner không còn code

- Ngày: 2026-09-20
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, agent, evaluation

## Mục tiêu

Agent chạy được (9 node LangGraph, 97 unit test backend pass) nhưng chưa có cách lặp lại được để chứng minh nó chạy
đúng yêu cầu. Bằng chứng hiện nằm rải rác trong `history/`: mỗi entry một lần chạy tay, không có bộ case cố định,
không có biên bản, không so sánh được giữa hai lần chạy hay hai model. Các mục tiêu bắt buộc từ spec (grounding 100%,
p95 < 5 s, tiêu chí nghiệm thu §9) chưa ai đo có hệ thống.

Đồng thời ba tài liệu trong `docs/agent/` mô tả code không tồn tại, khiến người đọc sau tưởng vẫn chạy được.

Kết quả mong muốn: một tài liệu đánh giá chạy được bằng tay qua Streamlit, không cần viết code mới, gồm bộ case lõi
cố định, cách chấm từng lượt, mẫu biên bản, và ranh giới rõ ràng giữa "đã chứng minh" và "chưa chứng minh".

## File thay đổi

- `docs/agent/evaluation-plan.md` — thêm: tài liệu chính, 9 mục. Phạm vi chứng minh, bảng truy vết 9 tiêu chí về
  nguồn spec, chuẩn bị môi trường, bộ 12 case lõi, checklist chấm 8 bước, mẫu biên bản, giới hạn đã biết của fixture,
  ngưỡng kết luận, thời điểm chạy.
- `docs/agent/evaluation-suite.md` — xóa: mô tả runner 25 case, `evaluation_suite.json`, `suite_fixtures.py`,
  `assertions.py` và UI chạy case/batch. Không file nào trong số đó tồn tại.
- `docs/agent/fixture-generation.md` — xóa: mô tả `src.evaluation.agent.generate_fixtures`, không tồn tại.
- `docs/agent/rubric.md` — xóa: việc xóa đã treo sẵn trong working tree từ trước và chưa entry nào ghi nhận; entry
  này xác nhận. Phần còn giá trị đã gộp vào `evaluation-plan.md` §6 (bằng chứng cần lưu) và §8 (không đạt ngay nếu).
- `docs/agent/README.md` — sửa: mục lục bỏ ba dòng trên, thêm `evaluation-plan.md`; viết lại đoạn cuối về timeout
  (xem Quyết định).
- `history/2026-09-20-evaluation-plan-for-itinerary-agent.md` — thêm: entry này.

Không chạm code, không chạm contract, không chạm mock.

## Quyết định

- **Phạm vi chỉ Itinerary Agent.** Recall@20/NDCG@10 của recsys (handbook §12) để workstream Evaluation làm riêng.
- **Thuần thủ công, không viết runner.** Không dựng CI; `.github/workflows` để trống như hiện tại. Lý do: bộ runner
  cũ đã không còn, và một tài liệu chạy tay có giá trị ngay mà không phát sinh code phải bảo trì.
- **12 case thay vì 25.** Nguyên tắc chọn: mỗi case phải chạm ít nhất một gate cứng ở §8 **và** phải tái hiện được
  bằng đúng dữ liệu đang có trong `products.json`. Case không thỏa cả hai bị loại.
- **Xóa thay vì sửa ba tài liệu cũ.** `git log --all` cho thấy `evaluation_runner`, `generate_fixtures`,
  `evaluation_suite`, `suite_fixtures` **chưa từng có commit nào** trong repo này — hai tài liệu đó mô tả code chưa
  bao giờ được commit. Để lại tham chiếu treo nguy hiểm hơn là xóa.
- **Bốn chỗ kế hoạch ban đầu sai so với code, đã sửa khi viết tài liệu:**
  - Ghi `MODEL_NAME` chứ không phải `ITINERARY_LLM_MODEL`. `Settings` (`core/config.py`) đặt `extra="ignore"` và
    không khai báo `itinerary_llm_model`; model thực tế vào `get_llm()` là `settings.model_name`. Biến trong
    `.env.example` là biến chết. Đã ghi cảnh báo này ở §3 và ở `README.md`.
  - Case 12 (`đặt phòng và thanh toán giúp tôi`) kỳ vọng **HTTP 400 `VALIDATION_ERROR`**, không phải response 200.
    `classify` phân loại `side_effect` → `refusal=True` → `_non_compose`/`_conversational_update` gọi `_failure(...)`.
  - Case 10 (khách sạn không có trong catalog) kỳ vọng **`NEEDS_CLARIFICATION`**. `specific_hotel` làm
    `require_hotel=True`, retrieval loại hết hotel không khớp tên, `evaluate_node` chọn `constraint_clarification`.
    Nhánh `NO_RESULTS` không tới được, nên không ghi nó là kỳ vọng.
  - Case 04 (Hạ Long) kỳ vọng **`COMPLETED` có stay và 0 hoạt động**, kèm warning `PRODUCT_DROPPED_UNAVAILABLE` mang
    đúng `productId` của Vịnh Hạ Long — chứ không chỉ là "sản phẩm đó không xuất hiện". Hạ Long còn 4 hotel hợp lệ.
- **Sửa thêm đoạn timeout trong `docs/agent/README.md`** ngoài mục lục. Đoạn cũ nói "Runner từng case/batch ... chờ
  30 giây ... API giữ giới hạn classify/planner 2 giây và composition 3 giây". Cả hai vế đều sai: runner không tồn
  tại, và `assistant.py:40` truyền `settings.itinerary_llm_timeout_seconds` vào `build_graph`, nên API dùng đúng giá
  trị `.env` (30 giây) cho cả `classify`, chọn điểm đến và `answer`. Con số 2/3 giây là ngân sách spec §7.2, không
  phải cấu hình đang chạy. Để nguyên thì biên bản đánh giá sẽ ghi sai điều kiện chạy.
- **Không tự quyết mục chờ xác nhận.** `priceUnit`/availability vẫn là mục *chờ xác nhận* ở `contract-baseline-v1.1.md`,
  nên tài liệu ghi ngân sách là "không kiểm được" và cấm điền `priceUnit` vào mock để demo ra tổng tiền.
- **Độ ổn định ≥ 80% được đánh dấu rõ là đề xuất**, không có trong spec, và xếp vào nhóm theo dõi chứ không phải gate.

## Kiểm tra

- `git status --short` khớp danh sách trên: 1 sửa (`README.md`), 3 xóa, 2 thêm.
- `grep -rn "evaluation-suite.md\|fixture-generation.md\|rubric.md" docs/ src/ AGENTS.md CLAUDE.md`: rỗng, không còn
  tham chiếu treo (`history/` giữ nguyên theo quy tắc không sửa entry cũ).
- `grep -rn "evaluation_runner\|generate_fixtures\|suite_fixtures\|evaluation_suite" docs/ src/`: rỗng.
- Mọi link `.md` nội bộ trong `docs/agent/` trỏ tới file tồn tại: 4/4 OK.
- Đối chiếu lại từng con số §7 với `products.json` bằng script đếm: 50/50 sản phẩm `priceUnit=UNKNOWN`; đúng 1 sản
  phẩm `available=false` và 1 sản phẩm `unitPrice=null`, cùng là `Vịnh Hạ Long`; 9 điểm đến; sản phẩm xếp lịch được
  Nha Trang 8, Phú Quốc 8, Hạ Long 5 (4 sau khi loại unavailable), Hà Tĩnh 4, Hội An 4, Hà Nội 1, TP.HCM 1,
  Đà Nẵng 1, Hải Phòng 0; hoạt động (`attraction`+`golf`) available tối đa 2 mỗi điểm đến.
- Đối chiếu kỳ vọng từng case với code: `nodes.py` (`_non_compose`, `evaluate_node`, `_composed`, `classify` refusal),
  `application/itinerary/retrieval.py` (`_drop_reason`), `domain/itinerary/planning.py` (`totals`, `_known_cost`),
  `api/v1/routes/assistant.py` (log `itinerary.completed ... latencyMs=`, `agent_status`),
  `paths/itinerary-agent.yaml` (200/400/401/404/422/500/503).
- **Không chạy** `validate_contract.py`: thay đổi chỉ nằm trong `docs/`, không chạm `src/shared/contracts/` hay
  `src/shared/mocks/`, nên AGENTS.md §4 không yêu cầu.
- Không chạy test tự động: thay đổi là tài liệu, không có code mới.

## Còn lại / rủi ro

- **Chưa nghiệm thu thật.** Cần chạy thử case 01, 06 và 08 theo đúng tài liệu. Nếu một bước nào không làm được chỉ
  bằng UI thì tài liệu sai và phải sửa. Chưa làm trong thay đổi này vì cần backend + model thật đang chạy.
- Chưa có biên bản nào trong `src/evaluation/reports/`; thư mục mới chỉ có `.gitkeep`.
- Latency 6–12 s vẫn vượt mục tiêu 5 s (ba lời gọi LLM tuần tự). Tài liệu ghi nhận, chưa xử lý.
- Bảy nhánh ghi ở §7 (`context.language=en`, `INVALID_TRIP_DURATION`, `CONVERSATION_NOT_FOUND`, sửa intent giữa
  chừng, mâu thuẫn ngày/số ngày, `LLM_UNAVAILABLE`, `retry`) chỉ có unit test backend bảo vệ, không có case thủ công.
- `.env.example` vẫn còn biến chết `ITINERARY_LLM_MODEL` và `ITINERARY_USE_LLM` mà `Settings` không đọc. Tài liệu đã
  cảnh báo nhưng chưa dọn file, vì dọn `.env.example` là thay đổi cấu hình nằm ngoài phạm vi task này.
- Số case sẽ phải xem lại nếu fixture được bổ sung sản phẩm: nhiều kỳ vọng ở §4 bám trực tiếp vào số lượng sản phẩm
  hiện tại của từng điểm đến.
