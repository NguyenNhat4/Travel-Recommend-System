# Đề xuất: trợ lý gợi ý điểm đến và khám phá trước, chỉ hỏi thông tin chuyến khi muốn lập lịch

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Bị thay thế bởi: 2026-10-09-sua-de-xuat-hoi-truoc-khi-lap-lich.md

## Mục tiêu

Người dùng thấy trợ lý quá cứng: "Hà Nội có gì?" bị coi là yêu cầu lập lịch nên bị hỏi số ngày, rồi hiện form ở mọi
lượt. Người dùng muốn trợ lý thân thiện hơn, thu thập nhu cầu dần:

1. Chưa có điểm đến: trò chuyện, gợi ý điểm đến.
2. Có điểm đến: giới thiệu điểm tham quan, khách sạn nổi bật.
3. Chỉ khi người dùng muốn lập lịch mới hỏi thông tin chuyến và sở thích (hồ bơi, phù hợp trẻ nhỏ...), rồi hiện form.

Việc này lệch AC-AGT-01, sơ đồ `architecture.md` §3 và `user-flow.md` §3.2, §4.2, nên theo AGENTS.md mục 8 chỉ tạo đề
xuất, chưa sửa source.

## File thay đổi

- `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` — thêm: đề xuất FR-AGT-06, AC-AGT-06, sửa FR-AGT-01,
  AC-AGT-01, architecture §3, user-flow §3.2 và §4.2 (chờ chốt).
- `history/2026-10-09-de-xuat-goi-y-truoc-khi-lap-lich.md` — thêm: entry này.

## Quyết định

- Trước đề xuất, trong phiên đã đưa ba hướng: luồng khám phá, tự đoán giá trị thiếu rồi lập lịch nháp, agent tự chọn
  tool. Người dùng mô tả hướng mình muốn, gần với luồng khám phá. Đề xuất viết theo hướng đó.
- Nguyên nhân đọc từ code: `classify` chỉ có bốn nhãn (`travel`, `vague`, `conversation`, `out_of_scope`), mọi câu
  `travel` đi luồng thu thập thông tin lập lịch. Chưa tái hiện bằng trace LangSmith.
- Mã AC mới là AC-AGT-06, vì AC-AGT-05 đã được dùng trong đề xuất đang chờ
  `2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md`.
- Ranh giới "muốn lập lịch" đề xuất làm bằng luật tất định: câu nêu số ngày, ngày đi, số người, ngân sách hay nơi đi;
  nút lập lịch; xác nhận form. LLM chỉ nhận câu nói rõ "lập lịch, lên kế hoạch" và câu hỏi khám phá. Như vậy
  "Hà Nội 3 ngày" vẫn lập lịch ngay như AC-AGT-01.
- Bốn điểm để người dùng chốt:
  - kiểu response (đề xuất `NEEDS_CLARIFICATION` + `searchResults` tuỳ chọn);
  - sở thích là ưu tiên hay bắt buộc (đề xuất ưu tiên, vì dữ liệu tiện ích còn thiếu);
  - lời khám phá do LLM viết hay code viết (đề xuất LLM, có kiểm grounding);
  - 5 lựa chọn sở thích có dữ liệu.
- Vé máy bay khi chưa lập lịch và gợi ý điểm đến theo từng người để đề xuất sau.

## Kiểm tra

- Chỉ sửa tài liệu, không chạy test. Đã đối chiếu các đoạn trích PRD trong đề xuất với `docs/prd/requirements.md`,
  `docs/prd/architecture.md`, `docs/prd/user-flow.md` hiện tại.
- Đã kiểm trong code và contract:
  - Web đã hiển thị `suggestions` cho `NEEDS_CLARIFICATION` (`useFloatingWidget.ts`).
  - Thẻ `searchResults` hiện chỉ dựng cho `COMPLETED`/`FALLBACK` (`widgetPlan.ts`).
  - `TripIntent.interests` đã có và được ghép vào câu tìm (`tool_planning.py`).

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất và bốn điểm mở. Sau khi chốt: cập nhật PRD trước, rồi contract 1.24.0, rồi backend,
  frontend, spec, test theo mục "Thay đổi source sau khi chốt" của đề xuất.
- Nên lấy trace LangSmith của hội thoại "Hà Nội" → "Hà Nội có gì?" để xác nhận nguyên nhân trước khi code.
- Working tree đang có thay đổi chưa commit của task khác:
  - `composition.py`, `option_swap.py`, `test_option_swap.py`, `sua-lich-qua-nhieu-luot.md`;
  - `docs/spec/agent/slide/`;
  - hai entry `history/` ngày 09/10.

  Không chạm vào và không đưa vào commit này.
