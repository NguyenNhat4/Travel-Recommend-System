# Plan: sửa các lỗi từ đợt chat thử trợ lý V-OTA (10/10)

- Ngày: 2026-10-10
- Người yêu cầu: Nguyễn Minh Nhật
- Nhánh gốc: `feat/agent` (đối chiếu code ở `ab4e375`)
- Phục vụ: FR-AGT-01 (hội thoại đa lượt), FR-AGT-04 + NFR-REL-01 (grounding 100%), FR-AGT-05 (hỏi đáp sau khi có lịch),
  NFR-PERF-02; FR-AGT-06 / AC-AGT-06, AC-AGT-07 (mã mới trong đề xuất `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md`)
- Nguồn: ghi chú chat thử của người dùng và plan của phiên trước (không có trong repo); bản này viết lại, đã đối chiếu code.

## 1. Lỗi người dùng gặp

Câu trong ngoặc kép là câu người dùng gõ nguyên văn; dùng đúng các câu này khi chạy live và khi viết case golden.

| # | Người dùng gõ | Trợ lý đang làm | Trợ lý phải làm |
|---|---|---|---|
| A | "không thích đi Nha Trang" → thẻ khám phá điểm khác | Mô tả thẻ ngắn, khô; lặp cụm "được khen nhiều"; không có không khí, không có câu chuyện | Mỗi thẻ 2–3 câu kể chuyện, lôi cuốn, đủ để người dùng hiểu nơi đó; không lặp cụm khen |
| B | "Văn Miếu có mở cửa buổi tối không?" | Trả cả danh sách khách sạn và điểm khác | Trả lời đúng câu hỏi về Văn Miếu như cảnh 9 của artifact kịch bản; chỉ thẻ Văn Miếu (tối đa thêm 1 điểm liên quan) |
| C | "giờ tao đi hà nội thì vé nào rẻ" | Ra danh sách "vé rẻ ở Hà Nội" hoặc lập luôn lịch trình | Hỏi lại "vé máy bay, khách sạn hay vé tham quan?" kèm 3 nút |
| D | Lượt sau: "tao hỏi vé máy bay mà" | Lại ra danh sách/lịch như trên | Vào nhánh giá vé máy bay |
| E | "giá máy báy đó rẻ nhất chưa" → "đắt nhất thì soa" | Lượt 1 trả rất nhanh (người dùng nghi cache) và chỉ nói giá ngày đã chọn; lượt 2 lập lại cả lịch | Lượt 1 so với các ngày khác trong cửa sổ bán; lượt 2 trả lời chuyến đắt nhất cùng tuyến, hoặc hỏi lại / nói chưa có dữ liệu — không lập lịch mới |
| F | Đang hỏi vé: "đi đâu cũng được, miễn đắt nhất" | Chuyển sang khám phá Nha Trang | Vẫn trong ngữ cảnh vé: so các tuyến từ nơi đi (hoặc hỏi nơi đi) |
| G | "có khách sạn nào có hồ bơi gần phố cổ không?" → trợ lý hỏi phố cổ ở đâu → "hà nội cha ơi" | Ra "Hà Nội có gì" chung chung | Nhớ câu hỏi gốc, ra danh sách khách sạn có hồ bơi gần phố cổ Hà Nội như kịch bản |
| H | "khởi hành 12/11, ngân sách 15 triệu, từ Đà Nẵng" | "Chưa có sản phẩm mở bán cho ngày này" | Không bao giờ chỉ nói "không có sản phẩm": "Mình chưa tìm thấy vé mở bán cho ngày 12/11, nhưng có những nơi sau…" rồi dẫn chuyện, dựng lịch tham khảo từ các điểm nổi tiếng |
| I | — | Bộ golden không có các cảnh của artifact kịch bản bản 5 và các lỗi trên | Có dataset kịch bản để đo lại sau mỗi lần sửa |

## 2. Nguyên nhân (đã đối chiếu code ở `ab4e375`)

- **A.** `EXPLORE_PROMPT` (`agents/steps/prompts.py:286`) ép mỗi thẻ "in one or two clauses"; `about()` cắt ở
  `ABOUT_CHARS = 360` (`agents/steps/exploration.py:41`); `_card_input` đưa `reasons` cho mỗi thẻ nên LLM nhắc lại lý do
  (`reason_*` → "được khen nhiều") ở từng dòng.
- **B.** `pick()` (`exploration.py:168`) luôn ghép thẻ `asked` với 2 điểm + 2 khách sạn chung; không phân biệt câu hỏi
  về một nơi cụ thể với câu khám phá.
- **C, D.** `fares._FLIGHT` (`agents/steps/fares.py:23`) chỉ khớp "vé máy bay/vé bay/vé ra|vào|từ…", không khớp "vé nào";
  `asked()` cần cả `_FLIGHT` và `_PRICE`, nên "tao hỏi vé máy bay mà" (không có từ hỏi giá) không vào nhánh giá vé.
  Không có nhánh hỏi lại cho câu "vé" không rõ loại.
- **E.** Lượt 1 đi luật `fares` không gọi LLM nên nhanh (trace phiên trước: 0,17 s) — không phải cache. `answer_text`
  chỉ nêu ngày đã chọn, không so với ngày rẻ nhất cả cửa sổ. Sau khi trả lời, `fares.answer` đặt `pending_fare = None`
  (`fares.py:249`) nên ngữ cảnh giá vé mất; "đắt nhất thì sao" không khớp luật nào và rơi về LLM → `travel`.
  Điều kiện chặn `state.get("previous_plan")` trong `fares.detected` (`fares.py:50`): code hiện lưu (`nodes.py:709`) và
  nạp lại (`nodes.py:140`) `previous_plan`, nên giả thuyết "lượt đó không có khoá" của phiên trước **chưa được xác nhận** —
  phải tái hiện hội thoại trước khi sửa.
- **F.** `fares.asked()` chỉ nhận câu trả lời ≤ `MAX_REPLY_WORDS = 5` từ khi đang hỏi vé; câu dài hơn rơi xuống
  `classification._DELEGATE` ("đâu cũng được") → khám phá.
- **G.** Khi `converse` hỏi lại "phố cổ ở đâu", câu hỏi gốc không được ghi vào state; `CONVERSATION_PHASE`
  (`nodes.py:51`) không có khoá cho câu hỏi đang dở, nên lượt sau chỉ còn "hà nội cha ơi".
- **H.** `retrieval._drop_reason` (`application/itinerary/retrieval.py:55`) loại mọi sản phẩm có ngày đi ngoài
  `availableFrom/To` (`PRODUCT_DROPPED_DATE`), kể cả điểm công cộng không bán vé (`is_bookable = false`, vd. Hồ Hoàn Kiếm,
  Khu Phố Cổ). Catalog chỉ mở bán 30 ngày từ `as_of` (AGENTS.md §6.2), nên 12/11 ngoài cửa sổ → `NO_RESULTS` với câu
  `composition._no_results_message`.

## 3. Điểm cần người dùng chốt trước khi làm

1. **Đơn vị 3, phần "đã có lịch rồi hỏi giá vé"** thuộc đề xuất `docs/prd/update/2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md`,
   đang `chờ chốt`. Phần hỏi giá vé *trước* khi lập lịch đã chốt (đề xuất `2026-10-09-goi-y-truoc-khi-lap-lich.md`, điểm
   "Hỏi giá vé trước khi lập lịch").
2. **Đơn vị 5** đổi hành vi `NO_RESULTS` (dựng lịch tham khảo gồm sản phẩm chưa mở bán cho ngày đó). Cần xác nhận nó nằm
   trong phạm vi đã giao cho đợt khám phá; nếu không thì tạo đề xuất riêng trong `docs/prd/update/`.
3. Câu "vé" mơ hồ khi đã biết điểm đến ("vé nào rẻ ở Hà Nội") nên hỏi lại hay mặc định vé máy bay? Plan chọn **hỏi lại**
   theo ghi chú của người dùng.

## 4. Đơn vị việc (6 đơn vị, chạy song song)

Tránh xung đột khi merge: mỗi đơn vị viết test vào **một file test mới riêng**, chỉ sửa đúng hàm được giao trong file
dùng chung, ghi `history/2026-10-10-<slug>.md` riêng. Không đổi contract OpenAPI; bắt buộc đổi thì dừng và báo.

### Đơn vị 1 — Lời dẫn khám phá có chuyện kể, không lặp (lỗi A)

- File: `agents/steps/prompts.py` (chỉ `EXPLORE_PROMPT`), `agents/steps/exploration.py` (chỉ `about`, `_card_input`,
  `ABOUT_CHARS`); test mới `src/backend/tests/unit/agents/test_explore_storytelling.py`.
- Câu mở đầu có không khí điểm đến. Mỗi thẻ 2–3 câu: nơi đó là gì, khoảnh khắc đáng trải nghiệm, hợp với ai, một mẹo
  nhỏ — chỉ lấy từ `about`/`tags`/tên (grounding).
- Một cụm khen xuất hiện tối đa 1 lần mỗi câu trả lời; `reasons` không bắt buộc nêu.
- Nâng `ABOUT_CHARS` (~700), thêm `highlights` từ `tags`. Giữ cấm số, giờ, điểm đánh giá trừ thẻ `asked`/`price_asked`.
- Nghiệm thu: chạy "không thích đi Nha Trang" ≥ 3 lần, không lần nào lặp cụm khen, mỗi thẻ ≥ 2 câu.

### Đơn vị 2 — Hỏi về một nơi cụ thể chỉ trả lời nơi đó (lỗi B)

- File: `agents/steps/exploration.py` (chỉ `pick`, câu kết trong `explored` nếu cần); test mới
  `test_explore_asked_place.py`.
- Có thẻ `asked` và câu là câu hỏi về nơi đó (giờ mở cửa, giá vé vào, có gì) → chỉ thẻ đó, tối đa thêm 1 điểm
  gần/liên quan, không khách sạn. Câu đầu trả lời thẳng câu hỏi (dùng `openingHours`).
- Nút gợi ý dẫn tiếp: "Hà Nội còn gì đáng đi?", "Lên lịch Hà Nội".
- Nghiệm thu: "Văn Miếu có mở cửa buổi tối không?" khớp cảnh 9 artifact kịch bản.

### Đơn vị 3 — Câu hỏi vé: hỏi lại khi mơ hồ, nhớ ngữ cảnh, rẻ nhất/đắt nhất (lỗi C, D, E, F)

- File: `agents/steps/fares.py`, `agents/nodes.py` (chỉ chỗ gọi `fares.detected` trong hai hàm classify và nhánh
  `fare_question` trong `explore_node_async`), `agents/steps/messages.py` (khoá `fare_*` mới); test mới
  `test_fares_followups.py`.
- "vé" không rõ loại ("vé nào rẻ", "vé ở Hà Nội") → hỏi "vé máy bay, khách sạn hay vé tham quan?" kèm 3 nút.
- "tao hỏi vé máy bay mà" (nhắc vé máy bay, không có từ hỏi giá) khi lượt trước là câu hỏi vé → nhánh giá vé.
- Sau khi trả lời, giữ ngữ cảnh trong `pending_fare` (`{"origin", "destination", "answered": true}`, không thêm khoá
  state mới) để "đắt nhất thì sao", "rẻ nhất chưa", "ngày khác thì sao" trả lời tiếp bằng luật. "rẻ nhất chưa" khi đã
  chọn ngày → so với ngày rẻ nhất cả cửa sổ.
- "đi đâu cũng được, miễn đắt/rẻ nhất" khi đang hỏi vé → so các tuyến từ nơi đi (thiếu nơi đi thì hỏi), không khám phá.
- Đã có lịch (chờ chốt mục 3.1): trước hết tái hiện E để biết vì sao điều kiện `previous_plan` không chặn; sau đó câu hỏi
  giá vé trả lời theo chặng bay của lịch hoặc so ngày khác, không lập lịch lại.

### Đơn vị 4 — Nhớ câu hỏi đang dở khi trợ lý hỏi lại nơi (lỗi G)

- File: `agents/steps/classification.py` / `conversation.py` (ghi câu hỏi gốc khi `converse` hỏi lại điểm đến),
  `agents/nodes.py` (`CONVERSATION_PHASE` thêm `pending_question`), `agents/state.py`, `exploration.py` (chỉ `search`:
  câu tìm khách sạn dùng cả câu hỏi gốc); test mới `test_pending_question.py`.
- Lượt sau nêu điểm đến ("hà nội cha ơi") → `explore` chạy với câu hỏi gốc + điểm đến → khách sạn có hồ bơi gần phố cổ
  Hà Nội.
- "phố cổ" không kèm thành phố → hỏi "Hà Nội hay Hội An?" kèm hai nút.

### Đơn vị 5 — Ngày ngoài cửa sổ mở bán: không chỉ nói "không có sản phẩm" (lỗi H)

- File: `application/itinerary/retrieval.py` (`_drop_reason`), `agents/steps/composition.py` (`_no_results_message`, đường
  dựng lịch tham khảo), `prompts.py`/`narration` (chỉ câu cho lịch tham khảo nếu cần), `messages.py` (khoá mới); test mới
  `test_out_of_window_dates.py`; cập nhật mục NO_RESULTS trong `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Điểm công cộng / vào cửa tự do (`free_entry` hoặc không bán vé) không bị loại theo ngày.
- Mọi sản phẩm bán vé bị loại vì ngày → vẫn dựng lịch tham khảo từ các điểm nổi tiếng. Điểm tham quan cào về có giá được
  coi là vé tham quan; đánh dấu "chưa mở bán cho ngày này", không tính vào `bookableCount`.
- Cảnh báo `PRODUCT_NOT_ON_SALE_FOR_DATE` (code là chuỗi tự do, contract không đổi).
- Câu mở đầu: "Mình chưa tìm thấy vé mở bán cho ngày 12/11 (đang mở bán đến <ngày cuối>), nhưng đây là những nơi…" rồi
  dẫn chuyện; nút gợi ý ngày gần nhất còn bán.
- Grounding giữ 100%: mọi thẻ vẫn là sản phẩm Search.

### Đơn vị 6 — Bộ golden kịch bản bản 5 + các lỗi lần này (lỗi I)

- File: mới `src/evaluation/datasets/agent_scenarios_v5.yaml`; `src/evaluation/agent/golden.py` (thêm khoá kiểm
  `questionMatches`, `suggestionsMin`, `cardsMin`, `cardsMax`, `firstCard`); `src/evaluation/tests/test_golden.py`.
- Case theo mã cảnh artifact: SC-MAIN (luồng chính 1→11), SC-06 giá vé, SC-09 Văn Miếu, SC-10 ngày không có chuyến,
  SC-H1…H9 người dùng khó, SC-OUT ngoài phạm vi, SC-CHG đổi khách sạn/vé; thêm một case cho mỗi lỗi A–H với câu nguyên
  văn ở mục 1.
- Ngày dùng placeholder `{today+N:…}` như `agent_test_cases_nhat.yaml`. Case của lỗi chưa sửa được phép FAIL; chỉ cần
  `test_golden.py` (cú pháp dataset, khoá mới) PASS.

## 5. Cách chạy cho worker

1. Worktree không có `.env`, `.venv`, dữ liệu: dùng `.venv` và chép `.env` từ repo chính trên máy dev (không commit —
   đã gitignore).
2. Test nhanh: `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false <python> -m pytest -q -p no:cacheprovider
   src/backend/tests/unit/agents src/backend/tests/unit/domain`; trước khi commit chạy cả `src/backend/tests`.
3. Live với LLM thật (đơn vị 1–5): `HF_HUB_OFFLINE=1 SEARCH_PREWARM=false ITINERARY_DATA_MODE=inprocess <python> -m
   uvicorn src.backend.app.main:app --host 127.0.0.1 --port <8020+số đơn vị>`; chờ log "Application startup complete".
   Gửi `POST /api/v1/assistant/itineraries` với `{"message", "conversationId"}` (lấy `conversationId` từ lượt trước),
   in `question`/`message`, `searchResults`, `suggestions`. Chạy đúng câu nguyên văn của lỗi mình sửa, mỗi câu ≥ 3 lần
   nếu phụ thuộc LLM. Xong thì kill đúng PID đã lưu (không `pkill -f`).
4. Đơn vị 6: `<python> -m pytest -q src/evaluation/tests/test_golden.py`; live không bắt buộc.

## 6. Quy tắc chung cho worker

- Đọc `AGENTS.md`, `docs/spec/agent/working-context.md`, skill `.agents/skills/building-itinerary-agent/SKILL.md`.
- Luật tất định trước LLM; LLM chỉ viết chữ; mọi sản phẩm/giá từ tool (grounding 100%); comment và câu chữ tiếng Việt
  như code xung quanh.
- Chỉ sửa file/hàm được giao; test vào file test mới của đơn vị.
- Ghi `history/2026-10-10-<slug-đơn-vị>.md` theo `history/README.md` (file đổi, lý do, quyết định, lệnh kiểm tra + kết
  quả thật).
- Commit trên nhánh `batch/<slug-đơn-vị>` tạo từ `feat/agent`, message tiếng Việt kiểu `fix(agent): …`; PR base là
  `feat/agent`, không phải `main`.

## 7. Nghiệm thu (người điều phối, sau khi các PR về)

- Merge lần lượt vào `feat/agent` (dễ xung đột ở `messages.py`, `nodes.py`, docs), chạy cả bộ backend và
  `validate_contract.py`.
- Chạy `agent_scenarios_v5.yaml` và `agent_test_cases_nhat.yaml` với `--trace-project` trên backend local; báo bảng
  PASS/FAIL theo mã cảnh và theo lỗi A–H.
- Chat lại tay đúng chuỗi câu ở mục 1 trên frontend để xác nhận với người dùng.
