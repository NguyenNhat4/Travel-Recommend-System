# Tư vấn vé máy bay và các sửa sau chat thử 11/10

- Ngày: 2026-10-11
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng (source và contract 1.25.0 ngày 2026-10-11; PRD cùng ngày)
- Chốt bởi / ngày: agent chốt theo uỷ quyền của Nguyễn Minh Nhật ("về phần technical PRD mình cho bạn quyết định mọi thứ"),
  2026-10-11
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-06, thêm FR-AGT-07), §2.3 (NFR-SEC-04), §3 (AC-AGT-06,
  AC-AGT-07, thêm AC-AGT-08); `docs/prd/architecture.md` §3; `docs/prd/user-flow.md` §3.2, §4.2
- Mã FR/NFR: FR-AGT-06, NFR-REL-01, NFR-SEC-04; mới: FR-AGT-07, AC-AGT-08

## Lý do

Người dùng chat thử trợ lý ngày 2026-10-11 và góp ý:

- **M05:** hỏi vé mới chỉ trả lời được rẻ nhất/đắt nhất. Chưa tư vấn được theo giờ ("đi sớm"), theo ngày ("ngày 20/10"),
  ngày nào có chuyến, hay "tại sao đắt" (trợ lý lặp lại câu báo giá). Câu trả lời liệt kê ngày và giá bằng chữ, dài, không
  bấm được.
- **M06:** câu chỉ nói "vé" ("đi đâu cũng đc miễn vé rẻ") bị hiểu là vé máy bay, không hỏi loại vé.
- **M09:** lịch tham khảo (ngày đi chưa mở bán) chỉ có câu "bạn nhắn 'Đi Phú Quốc 3 ngày từ ngày …'", không có nút.
- **M03:** "chùa thiên mậu ở đâu" ra danh sách khách sạn (chữ "ở đâu" bị hiểu là hỏi chỗ ở).
- **M04:** "khách sạn nào đắt nhất / rẻ nhất" chỉ chọn trong vài kết quả Search, không phải đắt nhất/rẻ nhất của cả thành phố.
  Nơi không có trong dữ liệu thì mọi lượt lặp một câu cố định.
- Xin form ("cho mình cái form") thì trợ lý hỏi lại bằng câu chữ.
- "Đổi sang chỗ khác" khi chuyến chưa đủ thông tin thì ra form điền sẵn điểm đến cũ.

PRD chưa có yêu cầu tư vấn vé máy bay. Hỏi giá vé trước khi lập lịch mới được ghi ở mục "Quyết định khi áp dụng" của đề xuất
`2026-10-09-goi-y-truoc-khi-lap-lich.md`, chưa vào PRD.

## Nội dung đề xuất

### 1. `requirements.md` §1.4, thêm FR-AGT-07

> **FR-AGT-07 (Tư vấn vé máy bay):** Trợ lý trả lời câu hỏi về vé máy bay trước hoặc sau khi lập lịch, không lập lịch lại:
> vé rẻ nhất hoặc đắt nhất của tuyến trong đợt đang mở bán; vé của một ngày cụ thể; vé theo khung giờ; ngày nào có, ngày nào
> không có chuyến; "tại sao vé này đắt"; so nhiều tuyến khi người dùng "đi đâu cũng được". Câu "vé" không nói rõ loại (máy
> bay, khách sạn hay tham quan) thì trợ lý hỏi lại kèm 3 nút. Mọi chuyến và giá lấy từ chuyến bay của catalog
> (NFR-REL-01); câu trả lời gọn, chỉ nêu chuyến trả lời câu hỏi, các chuyến khác hiện thành hàng thẻ ngày–giá mở được trang
> vé máy bay (AC-AGT-08).

### 2. `requirements.md` §3, thêm AC-AGT-08

Tình huống: *"vé sg ra hn bao nhiêu"*, *"ngày 20/10 thì sao"*, *"đi sớm thì sao"*, *"ngày nào không có chuyến"*, *"đắt nhất
thì sao?"*, *"tại sao đắt vậy"*; *"tao ở sài gòn, đi đâu cũng được miễn vé rẻ"*; *"có vé nào rẻ đi hn ko"*; trước và sau khi
có lịch. Kết quả mong đợi:

- **Chung:** mọi chuyến, giá, giờ là chuyến một chiều thật của catalog còn bán từ hôm nay. Code viết câu trả lời, LLM chỉ
  hiểu câu hỏi. Không lập lịch lại; lịch đã có giữ nguyên. Câu chỉ nêu chuyến trả lời câu hỏi; các chuyến khác (tối đa 4 thẻ)
  là hàng thẻ ngày–giá. Mỗi thẻ mở `/flights?origin&destination&checkIn=<ngày bay>` đúng tuyến, đúng ngày.
- **Thiếu thông tin:** "vé" không rõ loại thì hỏi lại kèm 3 nút (vé máy bay, khách sạn, vé tham quan). Thiếu điểm đến hoặc
  nơi đi thì hỏi kèm nút của các tuyến có thật.
- **Rẻ nhất, đắt nhất:** của cả đợt đang mở bán, kèm ngày bay. "Rẻ hơn nữa không" thì nói rõ đây đã là vé rẻ nhất.
- **Một ngày cụ thể:** chuyến của ngày đó, so với cả đợt. Không có chuyến thì nói rõ, nêu tối đa 2 ngày gần nhất có chuyến
  và ngày rẻ nhất cả đợt.
- **Khung giờ:** đi sớm trước 09:00; sáng 05:00–12:00; chiều 12:00–18:00; tối từ 18:00. Không có chuyến trong khung thì nói
  rõ và tính mọi giờ.
- **Ngày có, không có chuyến:** đợt mở bán, số ngày có chuyến, các ngày chưa có chuyến (tối đa 8, dài hơn thì "…").
- **Giá minh hoạ:** catalog có 797/1.707 chuyến hạng Thương gia giá mô phỏng (`cabinClass: BUSINESS`, `simulated: true`).
  Chúng chỉ được tính khi tuyến không còn chuyến giá thật; nếu không, "đắt nhất" luôn là vé mô phỏng (chat thử lần 3:
  2.385.000 ₫ "Thương gia (giá minh hoạ)"). Thẻ ghi hạng ghế khác Phổ thông và "giá minh hoạ".
- **Tại sao đắt:** nói rõ dữ liệu có giá, hãng, hạng ghế, ngày, giờ (không có hành lý, điều kiện vé, ghế còn lại) nên không
  khẳng định lý do. Rồi chỉ nêu số liệu: gấp bao nhiêu lần vé rẻ nhất; so với giá phổ biến (trung vị giá các chuyến trong
  đợt); khác hạng ghế với vé rẻ nhất; giá minh hoạ; khác hãng với vé rẻ nhất; bay sát ngày (trong 7 ngày tới). Kèm thẻ của
  vé đó.
- **Đi đâu cũng được:** so các tuyến từ nơi đi, nêu nơi rẻ nhất, nút "<nơi> có gì chơi?".
- **Nút:** nút do trợ lý tạo ("Từ TP. Hồ Chí Minh", "Đắt nhất thì sao?", "Ngày nào còn vé?") khi bấm đi thẳng nhánh vé, không
  qua LLM.

### 3. `requirements.md` §1.4 FR-AGT-06 và §3 AC-AGT-06: thêm các trường hợp

- (a) Người dùng xin form ("cho mình cái form") thì lượt đó luôn có form điền sẵn, coi như đồng ý lập lịch.
- (b) "Đổi sang chỗ khác" chưa nêu nơi mới thì hỏi lại "đổi sang đâu", kèm 3 nút điểm đến khác của catalog; không hiện form.
- (c) Hỏi vị trí một nơi có trong catalog ("chùa Thiên Mụ ở đâu") thì trả lời bằng địa chỉ của catalog, không ra danh sách
  khách sạn.
- (d) Hỏi khách sạn rẻ nhất/đắt nhất của cả điểm đến thì lấy theo giá trong catalog của mọi khách sạn còn phòng. Hỏi gần một
  nơi thì chỉ trong các khách sạn tìm được quanh nơi đó và nói rõ phạm vi.
- (e) Nơi người dùng hỏi không có trong dữ liệu: trợ lý tự nói bằng lời của mình là không kiểm được, không nêu giờ hay giá
  (code chặn câu có giờ, giá), không dùng một câu cố định lặp lại.
- (f) Lịch tham khảo khi ngày đi chưa mở bán có nút "Đi <nơi> <n> ngày từ ngày <ngày gần nhất còn bán>".

### 4. `requirements.md` §2.3 NFR-SEC-04 và §3 AC-AGT-07: câu cụt giữa hội thoại

Cùng đợt chat thử (M10): "2 ng" trả lời câu hỏi số người bị luật "gõ bậy" chặn là tin rác. Thêm vào NFR-SEC-04: luật "gõ
bậy" chỉ xét tin nhắn đầu của hội thoại; giữa hội thoại câu cụt ("2 ng", "3n", "t7") để LLM đọc. Rác hiển nhiên, tục tĩu,
chèn lệnh vẫn bị chặn như cũ. AC-AGT-07 mục "Không quen công nghệ" ghi cùng ý.

### 5. `architecture.md` §3

- Sơ đồ: `ClassifyTurn --> Explore` có thêm "hỏi vé máy bay (trước hay sau khi có lịch)"; `Explore --> [*]` có thêm "giá vé
  từ chuyến bay của catalog + hàng thẻ ngày–giá"; `SuggestForm` có thêm "người dùng xin form".
- Gạch đầu dòng "Vé máy bay": câu trả lời vé do code viết từ chuyến bay của catalog; LLM chỉ hiểu câu hỏi; nút của câu trả
  lời vé không qua LLM.
- Gạch đầu dòng "Response phân biệt theo `status`": `NEEDS_CLARIFICATION.searchResults.flight` (1.25.0),
  `COMPLETED.suggestions` (1.25.0).
- Gạch đầu dòng "Lọc đầu vào": luật "gõ bậy" chỉ xét tin nhắn đầu.

### 6. `user-flow.md` §3.2, §4.2

- §3.2: nhánh "Hỏi vé máy bay" → trả lời từ chuyến bay của catalog + hàng thẻ ngày–giá, không lập lịch lại.
- §4.2: mục "Hàng thẻ ngày–giá" (ô thứ, ngày, giờ, hãng, giá; ô trả lời được làm nổi; bấm mở trang vé máy bay đúng tuyến,
  đúng ngày) và mục "Nút gợi ý" (có cả ở `COMPLETED`); form hiện ngay khi người dùng xin form.

## Thay đổi source sau khi chốt

Đã làm cùng ngày, trước khi cập nhật PRD:

- Contract 1.25.0, thêm trường tuỳ chọn, tương thích ngược: `src/shared/contracts/schemas/itinerary-agent.yaml`
  (`ItineraryCompleted.suggestions` tối đa 3; mô tả `ItineraryNeedsClarification.searchResults.flight`),
  `src/shared/contracts/openapi.yaml`; `src/frontend/src/types/api.gen.ts` sinh lại; `src/backend/app/main.py` version.
- Backend agent: `src/backend/app/agents/steps/fares.py` (ngày, khung giờ, ngày có chuyến, "tại sao đắt", thẻ ngày–giá, nút đi
  thẳng nhánh vé), `models.py` (`FareQuestion.day/time_of_day/why/availability`, `price = dear`, `form_request`),
  `classification.py`, `conversation.py` (xin form, "đổi sang đâu", chặn câu có giờ/giá khi nơi không có trong dữ liệu),
  `exploration.py` + `domain/itinerary/exploration.py` (địa chỉ, khách sạn đắt/rẻ nhất cả điểm đến, phạm vi), `narration.py`
  (nút lịch tham khảo), `prompts.py`, `messages.py`, `nodes.py`, `state.py`; `guardrails.py` (câu cụt giữa hội thoại,
  `history/2026-10-11-tra-loi-cut-ngay-chung-nut-chon-noi.md`).
- Frontend widget: `WidgetFareDays.tsx` (mới), `WidgetNarration.tsx`, `WidgetChat.tsx`, `useFloatingWidget.ts`,
  `widgetFlight.ts`.
- Spec đã cập nhật cùng đợt: `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`,
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`.
- `src/backend/app/domain/itinerary/planning.py`: `cabinClass`, `simulated` vào thuộc tính tóm tắt của sản phẩm.
- Test: unit `test_fares*.py`, `test_exploration.py`, `test_place_facts.py`, `test_out_of_window_dates.py`; frontend
  `widgetNarration.test.tsx`, `floatingWidgetOpening.test.tsx`.
