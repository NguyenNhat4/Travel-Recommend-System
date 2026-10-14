# Orc v2: kèm tên điểm đến catalog trong system prompt

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs

## Mục tiêu

"sài gòn có gì chơi" trả lời không tìm được gì. Trace LangSmith (project `nhat-10-7`, 13/10 20:25–20:27) cho thấy orc
truyền `destination` theo cách khách viết: `Sài Gòn`, `HCM`, `Hồ Chí Minh` → 0 kết quả; chỉ `TP. Hồ Chí Minh` → 50–52.
Model đoán khác nhau giữa các lần nên lúc được lúc không; tới khi gọi `list_destinations` thì đã hết 3 lượt gọi tool.
Phục vụ FR-AGT-01, FR-AGT-02, AC-AGT-07.

## File thay đổi

- `src/backend/app/application/itinerary/destination_names.py` — thêm: `DestinationNames` lấy tên điểm đến qua
  `list_destinations`, cache TTL 10 phút trong process; lỗi thì dùng bản cũ (lùi một chu kỳ) hoặc None.
- `src/backend/app/agents/orc_v2.py` — sửa: `system_prompt()` nối danh sách vào cuối `PROMPT`; luật destination phải là
  một tên trong danh sách, nơi ngoài danh sách là chưa có dữ liệu; `OrcV2Runtime(destinations=...)` lấy danh sách trước graph.
- `src/backend/app/application/itinerary/orc_contracts.py` — sửa mô tả `DESTINATION`, `list_destinations`.
- `src/backend/app/main.py` — sửa: một `DestinationNames` trên `app.state`, truyền vào runtime v2.
- `src/backend/tests/unit/agents/test_orc_loop.py` — thêm test prompt kèm danh sách, gọi catalog một lần cho hai lượt.
- `src/backend/tests/unit/application/test_destination_names.py` — thêm: cache TTL, lỗi giữ bản cũ / None.
- `src/evaluation/agent/assistant_v2_cases.py` — thêm ca `alias-saigon`, `alias-short`, `alias-no-diacritics`.
- `docs/spec/agent/working-context.md` — sửa §3.1: ghi danh sách điểm đến trong prompt.

## Quyết định

- Danh sách lấy từ catalog lúc chạy, không viết cứng: catalog đổi theo job cào; `products.jsonl` local chỉ có 7 nơi
  trong khi backend dev có Hà Nội, TP. Hồ Chí Minh.
- LLM tự đổi cách viết sang tên catalog nhờ danh sách (không thêm bảng alias vào dispatcher). Không lệch PRD: không
  thêm sản phẩm hay chọn thay orc; danh sách là mô tả giá trị hợp lệ của tham số (PRD architecture §3 "từng tham số có
  mô tả… ví dụ"). Request lấy danh sách nằm ngoài ngân sách 10 request của lượt vì được cache dùng chung — nếu reviewer
  coi đây là "code tự thêm truy vấn" thì cần đề xuất.
- Đặt trong system prompt (không trong payload từng bước) để phần đầu prompt ổn định giữa các lượt.

## Kiểm tra

- `pytest src/backend/tests/unit/agents src/backend/tests/unit/application src/backend/tests/unit/domain
  src/backend/tests/contract src/backend/tests/architecture`: 2742 passed, 3 xfailed, 2 failed. Hai fail là
  `test_behavior_snapshot` (luồng v1) do đổi "V-OTA" → "Sota" trong `ORCHESTRATOR_PROMPT` chưa commit từ trước
  (cassette miss X01-plan-doi), không liên quan thay đổi này.
- LLM thật, backend local `inprocess` cổng 8001, `assistant_v2_cases --repeat 3 alias-saigon alias-short
  alias-no-diacritics`: 9 lượt đều gọi tool với tên catalog (`TP. Hồ Chí Minh`, `Đà Lạt`) và có kết quả; 8/9 trả thẻ.
  Lượt hỏng (`alias-saigon#2`) bị `NUMBER_WITHOUT_FACT` hai lần (model viết số trong text) — lỗi khác.

## Còn lại / rủi ro

- `NUMBER_WITHOUT_FACT` làm hỏng cả lượt sau một lần sửa; `CURSOR_MISMATCH` lặp lại khi orc xin trang tiếp với tham
  số khác — chưa xử lý.
- Hai test `test_behavior_snapshot` cần ghi lại cassette theo đổi tên Sota (người làm thay đổi đó).
