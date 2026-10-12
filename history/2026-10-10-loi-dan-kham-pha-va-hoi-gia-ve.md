# Lời dẫn khám phá nói nơi đó có gì hay; hỏi giá vé trước khi lập lịch

- Ngày: 2026-10-10
- Người thực hiện: Nguyễn Minh Nhật / Claude Code
- Trạng thái: hoàn thành
- Mã FR/NFR: FR-AGT-06, NFR-REL-01 (grounding)
- Đề xuất liên quan: `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` (đã chốt, mục "Quyết định khi áp dụng" bổ
  sung hai điểm dưới đây); tiếp nối `history/2026-10-10-tro-ly-kham-pha-truoc-khi-lap-lich.md`.

## Lý do

1. Góp ý của người dùng: khi nhắn "Hà Nội", câu chat có điểm và lượt đánh giá ("Hồ Hoàn Kiếm … 1.139 lượt đánh giá"), giờ mở
   cửa. Những thứ đó đã nằm trên thẻ và khung chi tiết bên phải; câu chat phải nói nơi đó là gì, vì sao nên tới, có gì hay.
2. Người dùng chốt cảnh 6 của kịch bản: hỏi "vé ra Hà Nội bao nhiêu?" mà thiếu thông tin thì hỏi lại; chỉ tiếng Việt, chưa
   làm tiếng Anh.

## Thay đổi

### Lời dẫn khám phá (`agents/steps/exploration.py`, `prompts.py` `EXPLORE_PROMPT`, `messages.py`)

- Payload LLM mỗi thẻ có `about` (mô tả catalog đã bỏ câu lặp tên và câu chỉ có số liệu: giờ mở cửa, địa chỉ, thời gian
  tham quan, loại hình) và `tags`. Giờ mở cửa (`facts`) chỉ đưa cho nơi người dùng hỏi tới (lý do `asked`).
- Prompt: mỗi dòng nói loại nơi, điều đáng xem/làm, hợp với ai, lấy từ `about`/`tags`/tên; cấm điểm, lượt đánh giá, giờ, giá;
  `reasons` chỉ dùng nhẹ, không số ("nhiều người ghé", "được khen nhiều").
- Code ép: `_fill` bỏ placeholder điểm/lượt đánh giá; giá chỉ điền khi người dùng hỏi giá (`price_asked`), khi đó prompt bảo
  LLM chèn giá vào cuối dòng và không nói "chưa có dữ liệu giá".
- `_relinked`: chữ link trùng tên một thẻ thì id theo tên đó (LLM thật gắn tên khách sạn với id Hồ Hoàn Kiếm); gỡ dấu cách
  trong `(product: id)`.
- `_ensure_cards`: thẻ LLM bỏ sót được chèn đúng thứ tự thẻ (trước đây dồn xuống cuối); dòng chỉ có link trơn thay bằng dòng
  của code. Dòng của code: điểm tham quan dùng câu đầu mô tả; khách sạn dùng tiện ích có thật ("khách sạn có hồ bơi, spa, hợp
  gia đình có trẻ nhỏ") cộng lý do không số. Lý do đổi chữ: "nhiều người ghé nhất ở đây", "được du khách khen nhiều", "giá
  mềm". Bỏ hai câu `explore_rating`, `explore_reviews`.
- `place_destination`: câu nêu tên một nơi mà không nêu thành phố ("Văn Miếu buổi tối có mở không?") tìm nguyên câu trên cả
  catalog; nơi khớp tên thì điểm đến lấy từ chính sản phẩm đó. Trước đó `extract` (LLM) phải đoán Hà Nội và 4/4 lần không
  đoán ra, trả lời bịa "đóng vào buổi tối".

### Hỏi giá vé (`agents/steps/fares.py` mới, `nodes.py`, `state.py`, `messages.py`)

- `fares.detected` chạy trong `classify` sau `changes.detected`, trước LLM: câu có từ vé/chuyến bay ("vé máy bay", "vé ra",
  "vé từ", "bay ra"…) và từ hỏi giá; hoặc câu ngắn (≤ 5 từ, không "?", không "thôi") khi đang có `pending_fare`. Đã có lịch
  thì không bắt. Đi `explore` với `fare_question`.
- `fares.answer` (gọi từ `explore_node_async`, không LLM): điểm đến từ câu, rồi `pending_fare`, rồi chuyến đang nói ("vé ra
  đó" sau khi hỏi Hà Nội); nơi đi từ "từ X", tên catalog, nơi có tuyến tới điểm đến (`originCity`), hoặc câu trả lời trơn
  khi đang chờ nơi đi. Thiếu điểm đến: hỏi kèm 3 nút điểm đến. Thiếu nơi đi: hỏi kèm nút "Từ <nơi>" của các tuyến có thật.
  Đủ: `flight_options` (như chặng bay của lịch), vé một chiều rẻ nhất còn bán từ hôm nay (hoặc đúng `startDate`), tối đa 3
  ngày rẻ khác, câu "giá theo dữ liệu hiện có". Không có chuyến hay lỗi tải thì nói rõ.
- State: `pending_fare` (lưu qua lượt qua `CONVERSATION_PHASE`, `_fare_settled` bỏ khi lượt khác), `fare_question` (trong
  lượt). Contract không đổi (response `NEEDS_CLARIFICATION` + `suggestions` sẵn có).

### Tài liệu

- `docs/spec/agent/langgraph-nodes.md`: hai dòng bảng `classify` (giá vé, nơi nêu tên không kèm thành phố), mô tả `explore`.
- `docs/spec/agent/state-fields.md`: `pending_fare`, `fare_question`.
- `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md`: thêm lời dẫn khám phá, hỏi giá vé, chỉ tiếng Việt.

## File đã đổi

- Mới: `src/backend/app/agents/steps/fares.py`, `src/backend/tests/unit/agents/test_fares.py`, entry này.
- Sửa: `src/backend/app/agents/steps/exploration.py`, `src/backend/app/agents/steps/prompts.py`,
  `src/backend/app/agents/steps/messages.py`, `src/backend/app/agents/nodes.py`, `src/backend/app/agents/state.py`,
  `src/backend/tests/unit/agents/test_exploration.py`, `docs/spec/agent/langgraph-nodes.md`,
  `docs/spec/agent/state-fields.md`, `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md`,
  `src/evaluation/reports/eval-2026-10-10-agent-test-cases.md` (chạy lại golden).

## Kiểm tra

- Unit agent + domain: `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false .venv/bin/python -m pytest -q -p no:cacheprovider
  src/backend/tests/unit/agents src/backend/tests/unit/domain` → 1899 passed.
- Cả bộ backend (cùng biến môi trường, `src/backend/tests`) → 2692 passed, 36 skipped, 0 failed.
- Golden LLM thật (`HF_HUB_OFFLINE=1 .venv/bin/python -m src.evaluation.agent.golden --dataset
  src/evaluation/datasets/agent_test_cases_nhat.yaml --api-base-url http://127.0.0.1:8010`, backend `inprocess`, chạy trước
  phần giá vé): PASS 21/23, Grounding 1.0, Structured Output 1.0, Tool Calling 1.0. FAIL: TC-01 lượt 1 (có sẵn từ trước),
  TC-11 lượt 2 (giám khảo: hai mục Safari trùng trải nghiệm, phần `filter`, không thuộc thay đổi này). TC-04 lượt 3 lần này PASS.
- Chạy tay LLM thật, catalog thật (`inprocess`):
  - "Hà Nội", "Hà Nội có gì chơi?", "Hội An có gì?", "Đà Lạt có gì hay?", "Phú Quốc khách sạn có hồ bơi": mỗi thẻ một dòng mô
    tả, không còn số điểm/lượt đánh giá/giờ; "Nha Trang khách sạn nào rẻ?" có giá cuối mỗi dòng.
  - "Văn Miếu buổi tối có mở không?": 3/3 lần ra thẻ Văn Miếu và "18:00–22:00" (trước sửa 0/4, đi `converse` và bịa giờ).
  - Giá vé: "vé máy bay ra Hà Nội bao nhiêu?" → hỏi nơi đi, nút TP. Hồ Chí Minh/Cần Thơ/Huế; "Sài Gòn" → 632.000 ₫/khách
    ngày 12/10 (VJ124) và 3 ngày khác; "vé từ Đà Nẵng ra Phú Quốc giá sao" → trả lời ngay; "vé máy bay bao nhiêu vậy" → hỏi
    điểm đến; "Hà Nội có gì chơi?" → "vé ra đó bao nhiêu?" → "từ Huế" → 645.000 ₫. Mỗi lượt giá vé ~0,1 giây.

## Còn lại

- Golden case cho giá vé và cho lời dẫn không có số chưa thêm vào dataset (đã có unit test và chạy tay).
- Mô tả catalog của một số điểm là văn dịch máy ("quốc tịch Việt Nam"); dòng dự phòng của code có thể chép câu đó.
- Giá vé chỉ báo vé một chiều; vé khứ hồi chưa nêu.
- Như entry trước: TC-01 lượt 1, cập nhật PRD theo đề xuất (người dùng cho bỏ qua).
