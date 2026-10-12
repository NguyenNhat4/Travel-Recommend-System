# Sửa plan và đề xuất orchestrator theo review: đường tắt vé, ranh giới trả lời từ `shown`, lấy tiếp kết quả

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Thay thế: `2026-10-12-chinh-thiet-ke-orchestrator.md` (một phần: "orchestrator trả lời từ `already_shown`" và "đường
  tắt: chỉ một việc `fare` thì trả như hiện tại"); `2026-10-12-nho-ket-qua-da-xem-b1-b3.md` (một phần: lý do của đơn vị
  giá trong dòng `facts`, "để câu 'giá tính theo người hay theo gói' trả lời được từ ngữ cảnh")
- Bị thay thế bởi: `2026-10-12-sua-plan-orchestrator-theo-review-2.md` (một phần: phép kiểm số, chèn khối vé, nút lập
  lịch tạo `pending_offer`)

## Mục tiêu

Người dùng gửi review 5 điểm cho plan `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` và đề xuất
`docs/prd/update/2026-10-12-orchestrator-va-kham-pha-llm.md`, ưu tiên điểm 1 và 2:

1. Đường tắt vé làm mất việc phụ thuộc phía sau ("đi đâu vé rẻ, chỗ đó có gì chơi" bắt đầu bằng đúng một việc `fare`).
2. Trả lời trực tiếp từ `shown` lệch quy tắc grounding (sản phẩm, giá phải từ tool của chính lượt).
3. Có `next_page` nhưng `Job` không có cách xin trang tiếp; phanh chống trùng chặn việc lặp lại; nhảy trang bỏ qua ứng
   viên đã tìm mà chưa hiện.
4. Chưa đủ cấu trúc để code kiểm câu hỏi (`ask` "Bạn đi mấy ngày?" vẫn qua) và giữ lời mời lập lịch (`pending_offer`).
5. Đề xuất chưa xử lý AC-AGT-07 (lý do chọn thẻ do code tính).

## File thay đổi

- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — sửa:
  - phần đầu: dòng trạng thái trỏ tới entry này;
  - mục 1: thêm số đo 12/10 về câu hỏi trên thẻ đã xem;
  - mục 3: sơ đồ (đường tắt, `pending`, `unlisted`/`source_more`, kiểm đồng ý) và bảng "ai làm gì";
  - 4.1: khối `already_shown` là để nhận ra thẻ, không phải nguồn trả lời; thêm việc chưa làm về ranh giới;
  - 4.2: schema thêm `Job.continue_from`, `Pending`, `Question`, `PlanOffer`, `OrchestratorTurn.pending`, `fare_only`,
    `refers_to`, `question`, `offer`, `plan_reason`, `declines_offer`; bỏ `plan_request`, `form_request`;
  - 4.3: `more` dùng hết ứng viên chưa hiện rồi mới tải trang kế; `continue_from`; trạng thái việc vé
    `answered|asked|unavailable`; `unlisted`/`source_more` thay `has_more`/`next_page`;
  - 4.4: luật 1 (ranh giới nhắc lại / tra lại), luật 6 (khối vé hỏi lại), luật 7 (câu hỏi, lời mời, bảng
    `pending_offer`, bảng `plan_reason`);
  - 4.5: đường tắt vé theo năm điều kiện, việc còn chờ, phanh theo con trỏ, graph;
  - 4.6, 4.8: lời mời qua `offer`; bảng hành vi mong đợi;
  - mục 5 (test B5–B8, luật kiểm và kịch bản B11), mục 6, 7, 8.
- `docs/prd/update/2026-10-12-orchestrator-va-kham-pha-llm.md` — sửa, vẫn `chờ chốt`:
  - lý do có số đo 12/10;
  - FR-AGT-06: hỏi về thẻ vừa xem thì tra lại ngay lượt đó; tin có việc phụ thuộc vẫn được trả lời đủ;
  - AC-AGT-06: nguyên tắc "thông tin sản phẩm chỉ từ dữ liệu tra trong chính lượt";
  - mục 3 mới **AC-AGT-07**: chỉ đổi câu "lý do chọn thẻ … do code tính"; liệt kê phần giữ nguyên;
  - mục 4 mới **AC-AGT-08**: giữ nguyên, ghi rõ tin chỉ hỏi vé và tin có vé cùng việc khác;
  - mục 5 (`architecture.md` §3): việc còn chờ, đường tắt vé, gác cổng kiểm đồng ý và một câu hỏi, ranh giới grounding;
  - thay đổi source thêm `agents/steps/consent.py`.
- `src/backend/app/agents/steps/shown.py` — sửa chú thích (docstring module, `_UNITS`, `facts`): dòng thông tin là để
  nhận ra sản phẩm, câu trả lời vẫn tra lại. Không đổi code hay payload LLM.
- `src/backend/app/agents/steps/history.py` — sửa docstring `llm_context` theo cùng ranh giới. Không đổi code.
- `history/2026-10-12-chinh-thiet-ke-orchestrator.md`, `history/2026-10-12-nho-ket-qua-da-xem-b1-b3.md` — sửa: chỉ thêm
  dòng `Bị thay thế bởi`.

## Quyết định

- **Đường tắt vé do orchestrator khai, code kiểm.** Thêm `fare_only` (câu vé đã trả lời đủ tin nhắn) và `pending` (việc
  còn chờ kết quả vòng này). Code chỉ đi đường tắt khi đủ năm điều kiện: vòng 1, đúng một việc `fare`, `fare_only`,
  `pending` rỗng, việc vé có câu do code viết. Không suy từ số việc của vòng. "Đi đâu vé rẻ, chỗ đó có gì chơi" khai
  `pending`, nên có vòng 2 khám phá nơi rẻ nhất (`pending_fare.best`). Chạm phanh khi còn việc chờ thì câu trả lời nói rõ
  phần chưa làm, kèm nút hỏi tiếp.
- **Ranh giới trả lời từ `shown`** (theo PRD hiện hành: sản phẩm của câu trả lời khám phá chỉ từ Search của chính lượt;
  giá và còn chỗ luôn tải lại):
  - không tra lại thì chỉ được nhắc lại đã gợi ý gì, bằng tên viết thường, không link, không thẻ, không số;
  - mọi dữ kiện (giá, đơn vị giá, giờ, tiện ích, còn chỗ, điểm…) và việc hiện lại thẻ phải qua `about_shown` tra lại;
  - code bắt được link, thẻ, placeholder ngoài lượt và số (giờ, tiền, điểm) trong lượt không tra gì. Có `refers_to` thì
    code tự chạy `about_shown`, không có thì câu cố định. Dữ kiện không có số ("có hồ bơi") chỉ kiểm bằng prompt và B11.
- **`ABOUT` của khối `already_shown` giữ nguyên** để cờ `off` không đổi payload và snapshot; ranh giới vào
  `ORCHESTRATOR_PROMPT` ở B7. Số đo bên dưới cho thấy đường hiện tại không lấy dữ kiện từ khối để trả lời.
- **Lấy tiếp kết quả:** LLM không ghi số trang. `continue_from` trỏ tới việc đã chạy; code giữ con trỏ, lấy hết mục đã
  tìm mà chưa liệt kê (`unlisted`) rồi mới tải trang kế của nguồn (`source_more`, theo `offset`/`total` của Search). `more`
  ở lượt sau chạy lại `via` và loại thẻ đã xem.
- **Câu hỏi và lời mời có cấu trúc:** `question.about` không có loại "thông tin chuyến", vì chỉ nhánh lập lịch hỏi các
  câu đó. Lời mời là `offer {destination, text}`, code quyết có chèn. `plan_reason` thay `plan_request`/`form_request` và
  được kiểm trước `extract` (ví dụ `accepts_offer` cần có `pending_offer`). Câu chữ lệch loại đã khai thì đo ở B11.
- **AC-AGT-07:** chỉ đổi câu về lý do chọn thẻ; nút, vị trí và câu dẫn của thẻ, giọng điệu và các nhóm người dùng giữ
  nguyên. AC-AGT-08 giữ nguyên, ghi rõ thêm trường hợp tin có vé và việc khác.

## Kiểm tra

- Số đo trên code hiện tại (B1–B3, LLM thật, `repro.py` trong scratchpad, Postgres + Weaviate local), mỗi đoạn chat chạy
  một lần:
  - `["hà nội","khách sạn thứ hai giá bao nhiêu"]`: `classify` → `explore`. Kết quả là 4 khách sạn khác với 2 thẻ lượt 1,
    câu báo giá Classyc Hotel Hang Buom (4.688.250 ₫), không phải thẻ thứ hai (Proverb Hotel Hanoi).
  - `["hà nội","mấy chỗ lúc nãy cái nào có hồ bơi"]`: `classify` → `explore`. Kết quả là 4 khách sạn mới có hồ bơi, không
    xét Proverb Hotel Hanoi đã hiện (có hồ bơi ngoài trời).
  - `["đà nẵng có gì chơi","giá tính theo người hay theo gói vậy"]`: `classify` → `explore`. Tìm lại đúng 4 thẻ cũ, trả
    lời theo thẻ vừa tra.
  - Cả ba đều tra lại, không lấy giá từ khối `already_shown`. Lỗi là sai phạm vi.
- `HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_shown.py
  src/backend/tests/unit/agents/test_turn_context.py src/backend/tests/unit/agents/test_behavior_snapshot.py` → 43 passed
  (sau khi sửa chú thích).

## Còn lại / rủi ro

- **Dừng chờ người dùng duyệt plan và chốt đề xuất**, kèm 4 điểm (số thẻ, phạm vi "đã xem", số việc mỗi vòng, số vòng).
  Chưa chốt thì không làm B5–B10.
- Sau khi chốt: sửa `docs/prd/requirements.md` (FR-AGT-06, AC-AGT-06, AC-AGT-07, AC-AGT-08), `architecture.md` §3,
  `deployment-plan.md` §2 trước, rồi mới sửa source.
- Số đo chỉ một lần mỗi đoạn chat; chưa đo lặp.
