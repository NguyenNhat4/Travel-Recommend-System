# LLM hiểu câu chữ (vé, nơi, thành phố) thay cho regex và bảng tên viết tay (chat thử 16 kiểu: M03–M08, M11, M12, M15)

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: fix/chat-messy
- Trạng thái: hoàn thành
- Phạm vi: agent
- Thay thế: `history/2026-10-11-khong-bia-gio-gia-ten-goi-khac.md` (phần bảng tên dân gian và chốt chặn từ khoá của `converse`)

## Mục tiêu

Việc 1 và việc 2 của `docs/plan/2026-10-10-chia-viec-sua-loi-chat-thu-16-kieu.md` (FR-AGT-01, FR-AGT-04, FR-AGT-06, NFR-REL-01).

Bản đầu của việc 1 và việc 2 vá bằng hardcode:
- bảng 12 tên dân gian (`place_aliases.py`);
- regex lỗi gõ ("bao nhiu", "bn"), từ tiếng Anh, "tao ở X", "chuyến về";
- regex "phố cổ" ghi tay Hà Nội và Hội An.

Người dùng yêu cầu (2026-10-11):
- "Nó cần generalize";
- giảm luật tất định;
- bỏ qua mức latency 5 giây của BRD/PRD, vì đó chỉ là gợi ý;
- test bằng hội thoại thật và xem trace, không dựa vào chạy test.

## Thiết kế

- **LLM hiểu, code đối chiếu.**
  - `TurnRoute` (output của `classify`) có thêm nhãn `fare` và các trường ý định:
    - `fare` (`FareQuestion`): nơi đi, nơi đến, đi đâu cũng được, đắt nhất, chuyến về, ngày khác, rẻ hơn, chưa rõ loại vé;
    - `place`: tên nơi thường dùng, kể cả nơi muốn ở gần;
    - `city`, `focus` (`hotels`/`sights`), `price` (`asks`/`cheap`), `other_questions`.
  - Mọi tên nơi được đối chiếu với catalog trước khi dùng: điểm đến, tuyến bay, `named_in`, `closest_matches`. Grounding không đổi.
- **Bỏ luật dò câu chữ:**
  - `fares.asked/vague/detected` cùng mọi regex của chúng;
  - `place_aliases.py`;
  - `_QUESTION_WORDS`;
  - chốt chặn từ khoá `_FACT_CLAIM`;
  - luật "phố cổ" (`ask_old_quarter`).
- **Giữ luật cấu trúc, không dò câu chữ:**
  - tra chuyến, chọn ngày rẻ nhất, chiều về theo chuyến đi;
  - câu hỏi còn dở (`open_question`, nay kèm `open_understood`);
  - đối chiếu tên với catalog.

## File thay đổi

- `src/backend/app/agents/models.py` — sửa: `FareQuestion`; `TurnRoute` thêm nhãn `fare` và các trường ý định.
- `src/backend/app/agents/steps/prompts.py` — sửa:
  - `CLASSIFY_PROMPT`: định nghĩa nhãn `fare` (mọi cách viết; câu hỏi tiếp; chuyến của lịch đã có; chọn khách sạn sau câu hỏi loại vé là `explore`) và cách điền từng trường;
  - `EXPLORE_PROMPT`: `ticketPrice` là giá thật để chép nguyên văn; lý do `low_price`;
  - `CONVERSATION_PROMPT`: giữ câu cấm nói giờ, giá khi không có dữ liệu.
- `src/backend/app/agents/steps/classification.py` — sửa: `understood()` ghi các trường vào state (câu hỏi khác > 60 ký tự thì bỏ); nhãn `fare` đi `explore` nhánh giá vé.
- `src/backend/app/agents/nodes.py` — sửa:
  - `classify` không còn gọi `fares.detected` trước LLM;
  - `intake` reset các trường mới;
  - `CONVERSATION_PHASE` thêm `open_understood`;
  - `_fare_settled` bỏ `open_understood` cùng `open_question`.
- `src/backend/app/agents/state.py` — sửa: thêm `fare_ask`, `explore_place`, `explore_city`, `explore_focus`, `explore_price`, `other_questions`, `open_understood`.
- `src/backend/app/agents/steps/fares.py` — sửa: bỏ toàn bộ phần dò câu; `answer()` đọc `fare_ask`.
  - `_place` đối chiếu tên với điểm đến và tuyến của catalog ("sg", "saigon" → TP. Hồ Chí Minh; "Cần Thơ" giữ nguyên để tra tuyến).
  - Chỗ LLM để trống lấy từ `pending_fare` rồi `intent`.
  - `return_leg` lấy chiều về từ chính chuyến đi; trước đây đảo chiều hai lần khi LLM đã tự đảo.
  - `other_days` nêu các ngày kế tiếp; `cheaper` nói "đây đã là vé rẻ nhất".
  - `other_questions` thành nút.
  - `_talked_about`: chưa lập lịch thì nơi đang hỏi vé thành điểm đến đang nói tới.
  - Đi đâu cũng được: thêm nút "<nơi rẻ nhất> có gì chơi?" và ghi nơi đó vào `pending_fare.best`.
- `src/backend/app/agents/steps/exploration.py` — sửa:
  - `destination_for` dùng `explore_city` khi đó là điểm đến của catalog.
  - Câu nêu tên nơi: catalog quyết định thành phố (`place_destination` chạy trước). Tên khớp nơi ở nhiều thành phố thì hỏi lại (`ask_which_place`, nút là tên catalog); câu đã nêu thành phố thì không hỏi.
  - `place_query`: tên LLM đọc ra; chỉ bỏ tên thành phố khi tìm trên cả catalog.
  - `_in_city`: câu tìm đã lọc thành phố có kèm tên thành phố. Câu "gần <nơi>" không ra khách sạn thì tìm lại bằng câu chung.
  - `near_place_name`: mốc "gần <nơi>" lấy từ tên LLM đọc ra (regex cũ chỉ còn dự phòng). Hỏi chỗ ở thì chỉ thẻ khách sạn; nơi được nêu tên là mốc đo khoảng cách.
  - `_hotel_cards`: muốn chỗ rẻ thì rẻ nhất trước (`cheapest_cards`).
  - `hotel_focus`/`price_asked` theo `explore_focus`/`explore_price`.
  - `facts.ticketPrice` là chuỗi giá do code dựng.
  - Sửa giá dính sau dấu chấm.
  - `resumed` gộp `open_understood`.
- `src/backend/app/agents/steps/conversation.py` — sửa: bỏ chốt chặn từ khoá. Lượt hỏi về một nơi cụ thể (`explore_place`) mà tới `converse` thì trả câu cố định "chưa tìm thấy <nơi>…".
- `src/backend/app/agents/steps/turn_notes.py` — sửa: ghi chú lượt nêu tuyến vừa báo giá và nơi vừa giới thiệu, để LLM lượt sau hiểu "chỗ đó", "ngày khác thì sao".
- `src/backend/app/agents/steps/messages.py` — sửa:
  - thêm `explore_ask_which_place`, `explore_place_joiner`, `reason_low_price`, `note_fare`, `note_fare_anywhere`, `note_explore`, `fare_already_cheapest`, `fare_other_asks`;
  - `unverified_fact` có tên nơi;
  - bỏ `explore_ask_old_quarter`, `chip_old_quarter`.
- `src/backend/app/domain/itinerary/exploration.py` — sửa:
  - `closest_matches`/`closest_named`: tên gần đúng; hoà giữa hai thành phố thì không chọn;
  - `cheapest_cards`, lý do `LOW_PRICE`.
- `src/backend/app/domain/itinerary/place_aliases.py` — xóa.
- Test:
  - `test_fares.py`, `test_fares_followups.py` (giả lập `TurnRoute` thay cho dò regex), `test_fares_messy.py` (mới), `test_place_facts.py`, `test_open_question.py`, `test_exploration.py` — sửa;
  - `test_itinerary_runtime.py`: `ScriptedLlm(turn=...)`.
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md` — sửa theo thiết kế mới.

## Quyết định

- Câu hỏi vé luôn qua LLM của `classify`, không còn đường tắt bằng luật. Mỗi lượt giá vé mất khoảng 2 giây thay cho 0,1 giây; người dùng cho bỏ qua mức latency.
- Đính chính entry trước:
  - Câu "Search 'Lăng Chủ tịch Hồ Chí Minh' kể cả khi lọc Hà Nội chỉ trả sản phẩm TP. Hồ Chí Minh" là sai. Lần đo đó gửi `filters.destination`, trong khi contract đặt `destination` ở cấp trên cùng, nên thực ra không có bộ lọc nào.
  - Đo lại đúng: lọc Hà Nội thì ra Lăng. Không lọc thì ra TP. Hồ Chí Minh. Lọc Hội An mà bỏ tên thành phố ("… gần Phố cổ") thì 0 kết quả.
  - Vì vậy chỉ bỏ tên thành phố khi tìm trên cả catalog; khi đã lọc thành phố thì thêm tên thành phố vào câu tìm.
- Chưa lập lịch thì nơi đang hỏi vé thành điểm đến đang nói tới. Bằng chứng: trace LangSmith lượt "khách sạn" (M04) có `city=null`, vì `trip_so_far` ghi "chưa có thông tin chuyến đi" và Hà Nội chỉ nằm trong `pending_fare`.
- Nhiệt độ của model `classify` là 1 nên cùng câu có thể ra trường khác nhau. Ví dụ: "khách sạn gần phố cổ giá rẻ" lần trả `place="phố cổ"`, lần trả `null`. Sau khi prompt nói rõ "nơi muốn ở gần", 3/3 lần ra cùng kết quả.

## Kiểm tra

- Hội thoại thật: backend local `inprocess`, LLM thật, catalog snapshot; nhắn thẳng qua API (`chat_replay` và một script nhắn tay). Xem trace LangSmith project `nhat-10-7` ở các lượt sai.
- M03:
  - "lăng bác mấy giờ mở cửa vậy" → Lăng Chủ tịch Hồ Chí Minh, 08:00–11:00;
  - "hồ gươm có mất vé ko" → "Không, … tham quan tự do";
  - "văn miếu tối mở ko b" → "Có, … 18:00–22:00";
  - "xung quanh đó ăn gì ngon" → nói một lần là không kiểm được quán ăn. **Tốt**, riêng lượt 4 **Tạm**.
- M04: hỏi lại loại vé → "khách sạn" → khách sạn Hà Nội → "rẻ nhất là chỗ nào" → rẻ nhất trước, từ 213.000 ₫. **Tốt.**
  - Có lần LLM coi "có vé nào rẻ đi hn" là vé máy bay và hỏi nơi bay đi; cách hiểu đó cũng hợp lý.
- M05:
  - "vé sg ra hn bao nhiu" → 632.000 ₫;
  - "thế ngày khác thì sao" → 3 ngày kế tiếp;
  - "rẻ hơn nữa ko" → "Đây đã là vé rẻ nhất…";
  - "thôi đắt nhất đi" → 13.590.000 ₫;
  - "còn đi đà nẵng thì sao" → TP. Hồ Chí Minh → Đà Nẵng.

  Mỗi lượt khoảng 2 giây, không lập lịch. **Tốt.**
- M06: "tao ở sài gòn, đi đâu cũng đc miễn vé rẻ" → so tuyến từ TP. Hồ Chí Minh, rẻ nhất Đà Nẵng 365.000 ₫; "chỗ đó có gì chơi" → Đà Nẵng. **Tốt.**
- M07: **Tốt** (như trước).
- M08: "khách sạn gần phố cổ giá rẻ" → "Bạn muốn nói Khu Phố Cổ Hà Nội hay Phố cổ Hội An?" (nút từ catalog, 3/3 lần) → "Phố cổ Hội An" → khách sạn Hội An rẻ nhất trước, từ 261.000 ₫. **Tốt.**
- M11 (đã có lịch):
  - "chuyến bay về mấy giờ" → Hà Nội → TP. Hồ Chí Minh, ngày 25/10;
  - "có chuyến nào rẻ hơn ko" → trả lời từ tuyến của chuyến;
  - "đổi ks rẻ hơn đi" → đổi khách sạn (lập lại lịch, đúng ý).

  **Tốt.**
- M12: trả lời giá vé, nút "Hà Nội có gì chơi?" và "Khách sạn nào gần Hồ Hoàn Kiếm?". **Tốt.**
- M15: "how much is a flight from saigon" → TP. Hồ Chí Minh → Hà Nội 632.000 ₫. **Tốt.**
- Các cách nói khác: "ve tu sai gon di ha noi nhiu tien", "flight from hanoi to da nang price?", "mình ở hà nội, bay đâu rẻ nhất", "chợ bến thành mở tới mấy giờ" (hỏi giữa cuộc chat về Hà Nội), "bà nà vé bao nhiêu" (970.000 ₫), "văn miếu vé vào cửa nhiu" (hỏi ngay sau Bà Nà: Hà Nội, 299.000 ₫), "ks nào gần hồ gươm" → "cái nào rẻ nhất". Tất cả đều đúng.
- `pytest src/backend/tests src/evaluation/tests/test_golden.py` (chạy một lần trước commit): 2840 passed, 36 skipped.

## Còn lại / rủi ro

- `classify` chạy ở nhiệt độ 1 nên cách hiểu thỉnh thoảng lệch giữa các lần chạy. Kiểm bằng trace khi gặp lỗi chập chờn.
- Search trả 0 kết quả với câu có "ko" (bị hiểu là phủ định), và với "gần <nơi>" không kèm thành phố khi đã lọc thành phố. Cần báo team Search; agent đã tránh được cả hai.
- "xung quanh đó …" chưa lấy nơi vừa hỏi làm mốc nếu LLM không đọc ra `place`.
- Còn lại theo plan: việc 3 (M10, M13), việc 4 (M02, M09, M16), việc 5 (Search lọc khách sạn theo ngày).
