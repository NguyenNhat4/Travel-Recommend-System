# Orc v2: gợi ý kể chuyện theo sở thích, không xếp theo buổi khi chưa đồng ý lập lịch

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation

## Mục tiêu

Người dùng phản hồi lời gợi ý của trợ lý ở dạng liệt kê, muốn có chút kể chuyện; sau đó chốt thêm: kể theo sáng/chiều/tối
là lập lịch, chỉ được làm khi khách đồng ý hoặc tự yêu cầu. Phục vụ FR-AGT-01, FR-AGT-06, AC-AGT-07 (mỗi thẻ đứng
sau câu đầu tiên nhắc nó, câu dẫn 2–3 câu: nơi đó là gì, khoảnh khắc đáng trải nghiệm, hợp với ai; không liệt kê thẻ
thành khối; một cụm khen tối đa một lần). Không lệch PRD: prompt v2 trước đó chỉ yêu cầu "một hai câu (nơi đó là gì,
hợp với ai)", thiếu so với AC-AGT-07.

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa `PROMPT` (mục khám phá): kể theo mạch trải nghiệm/sở thích có câu mở, câu
  chuyển, lời mời; cấm xếp theo buổi/ngày và giọng "bắt đầu ở… sau đó ghé" khi chưa đồng ý lập lịch; mỗi câu một sản
  phẩm, 2–3 câu dẫn, không nhắc lại tên sau đoạn product, chi tiết chỉ lấy từ description/thuộc tính, một cụm khen tối
  đa một lần; thêm ví dụ cấu trúc đoạn.
- `src/evaluation/agent/assistant_v2_cases.py` — thêm ca `explore-story`, `follow-up-vs-new`.

## Quyết định

- Sửa ở prompt (giọng văn/hiểu câu), không thêm luật code kiểm câu dẫn: luật cứng sẽ tốn lượt sửa của orc (giới hạn 5
  lần gọi model) mà chất lượng câu chữ vẫn phải do model viết.
- Ảnh người dùng gửi là luồng v1 (widget mặc định v1; nhãn tiến trình "trùng nơi" là mã DUPLICATE của v1). Chỉ sửa v2
  (luồng sẽ thay v1 ở E13); v1 không đổi.

## Kiểm tra

Tầng bằng chứng: LLM thật (model cấu hình trong môi trường), graph orc v2 thật, tool giả đọc catalog snapshot
`src/data_collection/snapshots/2026-09-30` (không phải backend + Postgres/Weaviate). Script repro nằm ngoài repo.

- Trước sửa, "Đi TP. Hồ Chí Minh chơi có gì hay" ×2: liệt kê, mỗi thẻ 1 câu, lặp tên ngay sau thẻ ("[Dinh Độc Lập]
  Dinh Độc Lập là…").
- Bản kể theo sáng/chiều/tối (bị người dùng bác): "đi hcm" ×5 đạt về cấu trúc nhưng là xếp lịch khi chưa đồng ý.
- Bản cuối: "đi hcm" ×3 và "Đà Lạt có gì chơi" ×3 — 6/6 không xếp theo buổi, mỗi thẻ một đoạn có câu dẫn, không lặp
  tên, có lời mời; 6/6 không lỗi.
- Follow-up với yêu cầu mới (model thật, `RunAssistantV2` + store memory): "khách sạn ở Huế có hồ bơi" → "xem thêm"
  ×3: 3/3 giữ hồ bơi + Huế, không lặp thẻ. "đi hcm" → "còn Đà Lạt thì sao" → "khách sạn rẻ hơn": đổi sang Đà Lạt
  rồi giữ Đà Lạt. "đi Đà Nẵng" → "thôi, cho mình xem Nha Trang" → "có gì cho trẻ con": 2/3 đạt, 1/3 lượt Nha Trang
  lỗi LLM_UNAVAILABLE (model quá giờ) nên lượt sau còn ở Đà Nẵng.
- `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/unit/application
  src/backend/tests/architecture src/backend/tests/contract/test_assistant_v2_contract.py`: 2598 passed, 3 xfailed,
  2 failed — hai test snapshot v1 (`test_behavior_snapshot.py`) đỏ sẵn từ baseline E00, không liên quan.
- Toàn backend (Redis local, bỏ `AUTH_REDIS_URL`/`ITINERARY_LLM_REASONING_EFFORT` của môi trường): chỉ còn 2 lỗi
  snapshot trên.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Chưa chạy `assistant_v2_cases.py` qua API thật + catalog thật (cần backend, Postgres, Weaviate).
- Quan sát thêm, chưa sửa: orc có lúc lấy trang tiếp bằng con trỏ với tham số khác (CURSOR_MISMATCH, tốn một lượt
  tool); "gợi ý hợp với mình" có lượt không đưa thẻ nào; model quá giờ thỉnh thoảng làm lượt lỗi LLM_UNAVAILABLE.
- Ca "chưa phân biệt follow-up với yêu cầu mới" người dùng nêu: các ca đã thử trên v2 đạt; cần hội thoại cụ thể (v1 hay
  v2) để tái hiện.
