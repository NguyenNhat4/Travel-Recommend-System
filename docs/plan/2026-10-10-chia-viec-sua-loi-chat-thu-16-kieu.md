# Plan: chia việc sửa lỗi từ chat thử 16 kiểu người dùng (10/10)

- Ngày: 2026-10-10
- Người yêu cầu: Nguyễn Minh Nhật
- Thay đổi: ban đầu chia hai luồng (agent local + Claude Code cloud); người dùng đổi thành một agent local làm hết (10/10).
- Nguồn: `src/evaluation/reports/eval-2026-10-10-chat-thu-16-kieu-nguoi-dung.md` (commit `4d0f139`), trang xem:
  https://claude.ai/artifact/1h5rRvBP1j6ob5dyHVtg2L
- Phục vụ: FR-AGT-01 (hội thoại đa lượt), FR-AGT-04 + NFR-REL-01 (grounding), FR-AGT-05, FR-AGT-06; FR-SRC (lọc theo ngày,
  nhánh Search)
- Nhánh gốc: `feat/agent` của `NguyenNhat4/Travel-Recommend-System`

## Cách làm

Một coding agent (chạy local trên laptop của người dùng) sửa **toàn bộ** lỗi dưới đây, tuần tự theo thứ tự ưu tiên, trên
nhánh `fix/chat-messy` tạo từ `feat/agent`. Mỗi việc một commit + một entry `history/`. Lỗi Search (mục cuối) cũng do agent
này làm sau cùng nếu còn thời gian; đụng engine Search nên đọc thêm phần Search trong `AGENTS.md` §1.2.

Thứ tự: L1 (M03) → C1 (vé: M05, M11, M15, M04, M06, M12) → L2 (M10, M13) → C2 (M02, M08, M09, M16) → S (Search lọc ngày).

## Việc 1–2 (trước đây "luồng L")

### L1. Không tự nói giờ, giá, quy định khi không có dữ liệu; nhận tên gọi khác của điểm nổi tiếng (M03, ưu tiên cao nhất)

- Lỗi: "văn miếu tối mở ko b" → "không mở cửa buổi tối" (sai, catalog: 08:00–17:00, 18:00–22:00). "lăng bác mấy giờ mở
  cửa", "hồ gươm có mất vé ko" → LLM tự nói. Cả ba đi `explore → extract → converse`, không có thẻ.
- Việc:
  1. Tìm vì sao "văn miếu tối mở ko b" không ra thẻ trong khi "Văn Miếu buổi tối có mở không?" ra (kiểm `place_destination`:
     kết quả Search của câu cụt, `rules.named_in`). Ghi nguyên nhân thật vào history trước khi sửa.
  2. `domain/itinerary/place_aliases.py` (mới): tên dân gian → tên catalog (Lăng Bác → Lăng Chủ tịch Hồ Chí Minh, Hồ Gươm →
     Hồ Hoàn Kiếm, Văn Miếu → Văn Miếu – Quốc Tử Giám, Chợ Bến Thành, Bà Nà…), dùng trong `place_destination` và
     `named_in` (so trên chuỗi đã `fold`).
  3. `CONVERSATION_PROMPT` + chốt chặn bằng code trong `conversation.py`: không có dữ liệu thì không nói giờ mở cửa, giá vé,
     ngày lễ, quy định; nói rõ không kiểm được và gợi ý câu hỏi có tên nơi.
- Kiểm: `chat_replay --only M03` cả 4 lượt ra thẻ đúng nơi hoặc nói rõ không kiểm được; không câu nào khẳng định giờ/giá
  không có trong catalog.

### L2. Câu trả lời ngắn không bị coi là rác, "không có ngân sách" là bỏ qua (M10, M13)

- Lỗi: "2 ng" → "Mình chưa hiểu ý bạn" (0,0 giây, bộ lọc tin rác). "ko có ngân sách, từ sg" → form vẫn đòi ngân sách.
  "hn" sau câu hỏi điểm đến → "còn thiếu điểm đến".
- Việc: `guardrails.py` không lọc câu ngắn có số hoặc từ chỉ người/ngày ("2 ng", "3n", "2 lớn 1 nhỏ"); `_extract_update` +
  `EXTRACT_PROMPT`: "không có/chưa có ngân sách" ghi là đã trả lời (không còn trong `missing_fields`); kiểm vì sao "hn" không
  thành Hà Nội ở lượt đó.
- Kiểm: `chat_replay --only M10,M13`.

## Việc 3–4 (trước đây "luồng C")

### C1. Câu hỏi về vé chịu lỗi gõ và cách nói khác (M04, M05, M06, M11, M12, M15)

- Lỗi: "vé sg ra hn bao nhiu" không được nhận là hỏi vé (5 lượt khám phá Sài Gòn); "tao ở sài gòn, đi đâu cũng đc miễn vé rẻ"
  hiểu Sài Gòn là nơi đến; sau câu hỏi loại vé, "khách sạn" mất Hà Nội; có lịch rồi hỏi "chuyến bay về mấy giờ", "có chuyến
  nào rẻ hơn ko" lập lại cả lịch; câu tiếng Anh về vé bị nói "không kiểm được giá vé".
- Việc: `fares.py` (nhận diện chịu lỗi gõ, "chuyến về/đi", "X ra/đi Y", nơi đi trong "tao ở X"), sau câu hỏi loại vé chọn
  khách sạn/vé tham quan thì khám phá đúng thành phố; câu hỏi về chuyến của lịch đang có trả lời từ `previous_flights`;
  câu nhiều ý (M12) thêm nút cho phần chưa trả lời.

### C2. Lỗi nhỏ của lượt khám phá và lịch tham khảo (M02, M08, M09, M16)

- "giá rẻ" trong câu → ưu tiên rẻ nhất (M08); dòng dự phòng của thẻ không còn câu cụt (M02); lịch tham khảo gom một ngày gợi
  ý có đủ vé + khách sạn + điểm (M09); hỏi chọn nơi có biển kèm nút (M16).

## Việc 5 — Search lọc theo ngày đi

- `application/itinerary/engine_tools.py` ghi "ngày của `travelContext` engine chưa nhận": Search trả khách sạn không còn
  bán cho ngày đi (Hà Nội 24/10: 368 khách sạn còn bán nhưng 46 kết quả đều thuộc nhóm chỉ bán 15–16/10). Cần lọc theo ngày
  ở engine Search; xem `history/2026-10-07-de-xuat-loc-theo-ngay-o-tim-kiem.md`.

## Quy tắc

- Đọc `AGENTS.md`, `docs/spec/agent/working-context.md`, skill `.agents/skills/building-itinerary-agent/SKILL.md`. Luật tất
  định trước LLM, LLM chỉ viết chữ, mọi sản phẩm/giá từ tool.
- Không đổi contract OpenAPI; bắt buộc đổi thì dừng và báo.
- Mỗi task một entry `history/2026-10-1x-<slug>.md`; commit message tiếng Việt `fix(agent): …`.
- Test trước khi sửa (fail trên code cũ). Trước khi push: `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain`.
- Kiểm bằng hội thoại thật, không chỉ golden: backend local chạy (`ITINERARY_DATA_MODE=inprocess`), rồi
  `.venv/bin/python -m src.evaluation.agent.chat_replay --api-base-url http://127.0.0.1:8000 --out <file> --only <id> --log <log backend>`,
  đọc file kết quả và ghi đánh giá Tốt/Tạm/Lỗi từng lượt vào history.

## Bàn giao

- Push nhánh `fix/chat-messy`, mở PR vào `feat/agent`.
- Chạy lại cả 16 hội thoại (`chat_replay` không `--only`), so với báo cáo 10/10, ghi báo cáo mới vào
  `src/evaluation/reports/eval-YYYY-MM-DD-chat-thu-16-kieu-lan-2.md` kèm bảng Tốt/Tạm/Lỗi trước và sau.
