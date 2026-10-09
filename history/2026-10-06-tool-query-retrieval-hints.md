# Query của node `tool`: bỏ thông tin dạng filter, thêm gợi ý truy xuất

- Ngày: 2026-10-06
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Phục vụ FR-AGT-02. Planner viết `query` cho `search_products` từ cả intent thô, nên chép ngân sách, ngày, số ngày và số
người vào text. Trace thật (LangSmith, gpt-4o-mini và gpt-6-luna, 05–06/10/2026) có các câu như:
- "Khách sạn … tại Đà Nẵng cho 2 người lớn, lưu trú ngày 15/10/2026";
- "… cho chuyến đi 2 ngày bắt đầu 2026-10-08";
- `priceMax` = ngân sách cả chuyến.

Text query của `/search` được dùng hai lần: embed/BM25, và query plan đọc thành filter.
`parse_numeric("khách sạn Nha Trang ngân sách 5 triệu")` trả `price_max = 5.000.000`, tức trần giá **từng sản phẩm**.
Document đem embed lại không có giá, ngày hay số người (`text_builder.py`).

Ngược lại, sở thích như `hotel_attributes`, trẻ em hay `interests` chỉ được hậu kiểm trên top-10, nên phải có trong
query thì mới kéo đúng sản phẩm vào top-10.

## File thay đổi

- `src/backend/app/domain/itinerary/search_hints.py` — thêm:
  - `retrieval_hints(intent, constraints)`: gợi ý theo taxonomy, dùng đúng nhãn của text embed;
  - `search_query_text(...)`: cắt giá/ngân sách, sao, số người, phủ định (tái dùng parser của `/search`), ngày,
    số ngày/đêm, số sót lại và tên điểm đến; thêm gợi ý còn thiếu; rỗng thì dùng danh từ loại; lũy đẳng.
- `src/backend/app/agents/steps/tool_planning.py` — sửa:
  - `_validated_args` làm sạch `query` của mọi `search_products` và log `query_sanitized` (chỉ log số đoạn cắt);
  - payload planner chỉ còn `intent` rút gọn (`destination`, `interests`, `partyType`, `hasChildren`), thêm `search_hints`.
- `src/backend/app/agents/steps/prompts.py` — sửa `TOOL_PLAN_PROMPT`: query là cụm mô tả theo đúng category cộng
  `search_hints`; cấm số, giá, ngân sách, ngày, số người, sao, tên điểm đến, phủ định; không tự đặt `priceMin/priceMax/starRatingMin`; có ví dụ.
- `src/backend/app/domain/search/constraints.py` — sửa bug ở `remove_spans`: chuỗi thay thế là byte `0x01` thay vì `\1`,
  nên dấu câu ngay sau đoạn cắt bị nuốt và chèn ký tự điều khiển vào text BM25 của `/search`.
- `src/backend/tests/unit/domain/test_search_hints.py` — thêm 24 test, gồm 5 câu query nguyên văn từ trace.
- `src/backend/tests/unit/domain/test_constraints.py` — thêm test hồi quy cho `remove_spans`.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — thêm `SearchQueryTests` (plan thật từ trace qua
  `validated_plan`; payload planner). Cập nhật 5 test: query dự phòng giờ là danh từ loại thay vì tên điểm đến, và payload có `search_hints`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — thêm đoạn "Nội dung `query`" ở §2; lưới an toàn §2.5 và lưới
  category không còn ghi `query=<điểm đến>`.
- `docs/spec/agent/langgraph-nodes.md` — hàng node `tool`: payload planner và bước làm sạch query.

## Quyết định

- **Hai lớp.** Prompt bảo planner viết đúng, và `_validated_args` cắt tất định. Skill `building-itinerary-agent`:
  quyết định kiểm được bằng luật thì làm bằng luật. Trên LLM thật, prompt đã đủ trong 11/12 lời gọi; lưới an toàn bắt
  lời gọi còn lại ("…văn hóa Hà Nội" thành "…văn hóa").
- **Bỏ cả tên điểm đến khỏi query.** `destination` đã là tham số. Mọi ứng viên cùng điểm đến nên tên không phân biệt
  được gì. Riêng search không lọc taxonomy vẫn dùng tên điểm đến, vì không có danh từ loại nào đúng cho kết quả hỗn hợp.
- **Gợi ý được thêm tất định**, không chỉ đưa cho LLM: tiện ích bắt buộc (`hotel_attributes = true`) bị hậu kiểm trên
  top-10, nên phải luôn có trong query. Giá trị `false` không thêm, vì vector không hiểu phủ định.
- **`pace` và `COUPLE`/`FRIENDS` không thành gợi ý.** `pace` chỉ ảnh hưởng mật độ lịch. Còn `audience` của catalog chỉ
  phủ khoảng 3% và chưa có từ vựng chuẩn cho cặp đôi hay nhóm bạn.
- **Hàm lũy đẳng**, để plan đã lưu chạy lại vẫn ra đúng plan cũ (invariant ở spec Itinerary §2.5). Gợi ý cũng được làm sạch như query.
- **Phạm vi phủ định do parser của `/search` quyết định.** "không có hồ bơi, gần biển" bị cắt cả hai vế. Không sửa parser
  vì câu này thật sự mơ hồ, và parser thuộc workstream Search.
- **Sửa bug `remove_spans`** dù file thuộc Search: một byte, đúng ý docstring, có test. Nó ảnh hưởng text BM25 của `/search`
  mỗi khi cờ filter-từ-câu bật.
- **Không lệch PRD.** Architecture §3 vẫn đúng: planner nhận ngữ cảnh chung `llm_context`. Thay đổi chỉ là chất lượng tham số tool.
- **Prompt hub chưa cập nhật.** Bản `vota-itinerary-tool-plan` trên LangSmith hub (`history/2026-10-01-langsmith-prompt-hub.md`)
  giờ cũ hơn `prompts.py`. Backend chưa đọc hub nên không ảnh hưởng chatbot.

## Kiểm tra

- `pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain` → 1033 passed trước khi thêm test mới. Sau khi
  thêm, `test_search_hints.py` 24 passed và `SearchQueryTests` 2 passed.
- `pytest -q -p no:cacheprovider src/backend/tests` → 1723 passed, 32 skipped (gồm `tests/architecture`).
- `pytest -q src/evaluation/tests` → 14 failed, 96 passed. Đúng 14 fail này cũng có trên code chưa sửa (đã chạy lại sau
  `git stash`): do `UnitIndex(E=…)`, `LocalCdpClient.all_events` và mock psycopg, không liên quan thay đổi này.
- Golden với LLM thật, tầng "model/provider thật":
  - lệnh: `python -m src.evaluation.agent.golden --only TC-01,TC-03` (backend `inprocess`, 3.183 sản phẩm, model `gpt-6-luna`);
  - kết quả: PASS 7/7, Grounding 1.0, Structured Output 1.0, Tool Calling 1.0;
  - 12/12 query gửi `/search` (đọc từ log backend) không còn số, ngân sách, ngày, số người hay tên điểm đến, ví dụ
    "khách sạn nghỉ dưỡng yên tĩnh phù hợp cặp đôi", "tham quan di tích lịch sử và danh lam thắng cảnh";
  - biên bản để ở scratchpad, không commit.
- Chưa đo chất lượng xếp hạng (Recall/NDCG) trước và sau. Bằng chứng mới dừng ở mức hình dạng query.

## Còn lại / rủi ro

- Chưa có bench retrieval cho query của agent. Muốn khẳng định xếp hạng tốt hơn thì cần một bộ cố định đo
  Recall@10 / tỉ lệ còn ứng viên sau hậu kiểm (working-context §5B).
- Cập nhật prompt hub `vota-itinerary-tool-plan` nếu đề xuất prompt hub được chốt.
- Vé máy bay chưa làm: chờ chốt đề xuất `docs/prd/update/2026-10-06-ve-may-bay-trong-lich-trinh-va-vi-tri.md`
  (entry `history/2026-10-06-de-xuat-ve-may-bay-trong-lich-trinh.md`).
