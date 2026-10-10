# Không bịa giờ, giá, quy định; nhận tên gọi khác của điểm nổi tiếng (chat thử 16 kiểu, M03)

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: fix/chat-messy
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Việc 1 của `docs/plan/2026-10-10-chia-viec-sua-loi-chat-thu-16-kieu.md` (ưu tiên cao nhất, FR-AGT-04, NFR-REL-01, FR-AGT-06).
Chat thử 10/10 (M03) có ba lỗi:
- "văn miếu tối mở ko b" được trả lời "không mở cửa buổi tối". Câu này sai: catalog ghi 08:00–17:00, 18:00–22:00.
- "lăng bác mấy giờ mở cửa vậy" và "hồ gươm có mất vé ko" thì LLM tự nói giờ và giá vé.
- Cả ba lượt đều đi `explore → extract → converse` và không có thẻ nào.

## Nguyên nhân (đo trên backend local, catalog thật, trước khi sửa)

- "văn miếu tối mở ko b":
  - `place_destination` tìm cả câu và Search trả **0 kết quả**.
  - Đo trên `/api/v1/search`: "văn miếu tối mở" trả về 1 kết quả, nhưng hễ câu có "ko" là 0 kết quả ("văn miếu mở ko b", "văn miếu tối mở ko").
  - Lý do: Search coi "ko" là từ phủ định (`domain/search/hypothesis._NEGATION_TOKENS`).
  - Câu đúng chính tả "…có mở không?" vẫn ra kết quả, vì có chữ "có".
- "lăng bác", "hồ gươm" không khớp tên catalog ("Lăng Chủ tịch Hồ Chí Minh", "Hồ Hoàn Kiếm").
  - Search "lăng bác" trả 0 kết quả.
  - Search "Lăng Chủ tịch Hồ Chí Minh", kể cả khi lọc `destination=Hà Nội`, chỉ trả sản phẩm ở TP. Hồ Chí Minh: Search hiểu "Hồ Chí Minh" trong tên là điểm đến.
- `converse` không có dữ liệu sản phẩm nào, nhưng prompt không cấm nói giờ và giá, nên LLM trả lời bằng kiến thức của nó.

## File thay đổi

- `src/backend/app/domain/itinerary/place_aliases.py` — thêm:
  - bảng tên dân gian → `Place(name, destination, query)` cho 12 nơi nổi tiếng có trong catalog;
  - `place_of`, `place_named`, `with_catalog_names`.
- `src/backend/app/agents/steps/exploration.py` — sửa:
  - `place_query`: câu tìm nơi lấy từ bảng; không có trong bảng thì bỏ đuôi hỏi "ko/k/không/b/vậy…".
  - `_asked` và `place_destination` so tên trên câu đã kèm tên catalog. Nơi có trong bảng thì lấy luôn điểm đến, không cần tìm.
  - `destination_for`: nơi nổi tiếng được nêu quyết định điểm đến, kể cả giữa cuộc chat về thành phố khác.
  - `_card_input` của nơi được hỏi có thêm `facts.entry = free_no_ticket_sold` (nơi công cộng không bán vé) hoặc `facts.ticketPrice` (placeholder giá).
  - `_PRICE_ASKED` nhận thêm "mất vé, vé vào, phí vào, thu phí, miễn phí".
  - `_price_text`: điểm tham quan không có giá là "tham quan tự do", giống `narration._price` (người dùng chốt 01/10).
  - `_with_asked_price`: hỏi giá vé mà LLM không nêu giá thì code thêm "Giá vé từ …".
  - `_link_plain_name`: LLM nêu tên thẻ mà không gắn link thì code gắn link tại chỗ, thay vì chèn thêm một dòng lặp nơi đó.
- `src/backend/app/agents/steps/conversation.py` — sửa:
  - `invents_fact` nhận ra câu nói giờ mở cửa, giá vé, vé vào cửa, miễn phí, ngày lễ, quy định.
  - `conversational_update` thay những câu đó bằng câu cố định "chưa kiểm được…", vẫn giữ nút gợi ý.
- `src/backend/app/agents/steps/prompts.py` — sửa:
  - `CONVERSATION_PROMPT` cấm nói giờ, giá, quy định.
  - `EXPLORE_PROMPT` thêm cách dùng `facts.entry` và `facts.ticketPrice`; câu có/không phải đúng câu hỏi ("có mất vé không" thì trả lời "Không"); câu "không kiểm được" chỉ nói một lần ở câu mở đầu.
- `src/backend/app/agents/steps/fares.py` — sửa:
  - câu nêu nơi nổi tiếng không bị coi là "vé" mơ hồ, cũng không vào nhánh giá vé máy bay (trừ khi có "vé máy bay/chuyến bay");
  - "vé vào cửa/cổng" không còn khớp mẫu "vé vào <nơi>" của vé máy bay.
- `src/backend/app/agents/steps/messages.py` — thêm `title_unverified_fact`, `unverified_fact`, `explore_asked_price` (vi, en).
- `src/backend/tests/unit/agents/test_place_facts.py` — thêm: 11 test (bảng tên, câu tìm, chọn thẻ, dữ kiện vé, giá, gắn link, điểm đến, nhánh vé, chốt chặn `converse`).
- `src/backend/tests/unit/agents/test_exploration.py` — sửa: `facts` của nơi được hỏi giờ có thêm khoá vé, nên test chỉ so `openingHours`.
- `docs/spec/agent/langgraph-nodes.md` — sửa: thêm chốt chặn `converse` và dòng bảng "tên dân gian".

## Quyết định

- Bảng tên gọi khác là dữ liệu tĩnh trong `domain` (hàm thuần). Chỉ ghi nơi có thật trong catalog, mỗi nơi ghi luôn điểm đến và câu tìm. Lý do: Search không tìm đúng bằng tên dân gian, cũng không tìm đúng bằng tên có chứa tên thành phố. Không sửa Search: việc đó thuộc team Search, và bảng đủ cho các nơi hay được hỏi.
- Chốt chặn `converse` là luật: câu có từ khoá giờ, giá, vé vào, miễn phí… hoặc có giờ dạng 7:30/18h00 thì thay bằng câu cố định. Bắt nhầm (một câu hỏi lại có chữ "giá vé") chỉ đổi sang câu cũng nói "chưa kiểm được", không sai sự thật.
- Nơi công cộng không bán vé (Hồ Hoàn Kiếm) thì nói "tham quan tự do, không cần mua vé". Cách này khớp với lịch (`FREE_ENTRY_ASSUMED`) và câu dẫn lịch.

## Kiểm tra

- Test mới fail trên code cũ (thiếu `place_aliases`, `place_query`, `invents_fact`).
- `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain`: 1964 passed.
- Hội thoại thật: backend local `inprocess`, LLM thật, catalog snapshot, `chat_replay --only M03`.
  - Trước (báo cáo 10/10): Lỗi nặng.
  - Sau, kết quả từng lượt:

    | Câu | Kết quả |
    |---|---|
    | "lăng bác mấy giờ mở cửa vậy" | **Tốt**: thẻ Lăng Chủ tịch Hồ Chí Minh, "08:00–11:00 (Thời gian nhận khách kết thúc vào 10:15)" |
    | "hồ gươm có mất vé ko" | **Tốt**: "Không, Hồ Hoàn Kiếm tham quan tự do, không cần mua vé" |
    | "văn miếu tối mở ko b" | **Tốt**: "Có, … mở 08:00–17:00, 18:00–22:00", một thẻ |
    | "xung quanh đó ăn gì ngon" | **Tạm**: nói một lần "chưa kiểm tra được quán ăn", gợi ý điểm dạo ở Hà Nội; chưa hiểu "đó" là Văn Miếu |

- Thử thêm cách nói khác, mỗi câu chạy 1 lần:

  | Câu | Kết quả |
  |---|---|
  | "lang bac may h mo cua", "ho guom vao co mat phi k", "van mieu quoc tu giam toi co mo k" | đều đúng |
  | "chợ bến thành mở tới mấy giờ", hỏi ngay sau Văn Miếu | thẻ Chợ Bến Thành, 09:00–00:00, đổi sang TP. Hồ Chí Minh |
  | "bà nà vé bao nhiêu" | thẻ Sun World Bà Nà Hills, "vé từ 970.000 ₫" |
  | "văn miếu vé vào cửa bao nhiêu" | "Vé vào … từ 299.000 ₫" |

  Trước khi sửa: "bà nà vé bao nhiêu" bị hỏi lại loại vé; "văn miếu vé vào cửa…" bị hỏi "bay đến đâu".

## Còn lại / rủi ro

- "xung quanh đó …" sau khi hỏi về một nơi chưa lấy nơi đó làm mốc, nên trợ lý gợi ý chung cả Hà Nội.
- Search trả 0 kết quả khi câu có "ko", và hiểu tên có "Hồ Chí Minh" là điểm đến. Cần báo team Search. Agent đã tránh được hai lỗi này cho câu tìm nơi.
- Bảng tên gọi khác mới có 12 nơi; nơi khác vẫn dựa vào tên catalog nằm trọn trong câu.
