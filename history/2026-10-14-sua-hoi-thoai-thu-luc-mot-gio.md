# Sửa ngữ cảnh, phạm vi tìm và lời tư vấn của assistant v2

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: agent, backend, frontend, docs
- Mã FR/NFR: FR-AGT-01/02/04/06, AC-AGT-01/06/07, NFR-REL-01

## Mục tiêu

Sửa các case người dùng thử khoảng 01:00 ngày 14/10: quên ngày thứ Sáu khi bổ sung số người/số ngày; tìm khách sạn
Le Phan ngoài Phan Thiết bị hiểu thành ngoài trời hoặc vẫn tìm trong Phan Thiết; tên lặp phía trên thẻ; giọng bán
hàng; ưu tiên tham quan miễn phí khi khám phá chung; chuyển sang nghỉ ngơi nhẹ khi không muốn đi chơi.
Người dùng xác nhận “sửa đi” sau phần đối chiếu hành vi. Triển khai và kiểm thử nội bộ đã xong; còn xác minh model thật.

## File thay đổi

- `docs/prd/update-archive/2026-10-14-sua-hoi-thoai-thu-luc-mot-gio.md` — thêm: nội dung đã chốt trong chat, tạo ở
  update rồi áp dụng PRD và chuyển sang archive (file mới, chưa track nên dùng rename).
- `docs/prd/requirements.md` — sửa AC-AGT-01/06/07: nghỉ nhẹ, ưu tiên tự do mềm, giọng và tên trùng.
- `docs/prd/user-flow.md` — sửa §4.2: lược dòng chỉ lặp tên trước thẻ.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — thêm mục v2: context patch cùng final, phạm vi/tên, trải nghiệm.
- `src/backend/app/agents/orc_v2.py` — sửa prompt năm nhóm case; guard kiểm evidence và giới hạn rekindle của final patch.
- `src/backend/app/application/itinerary/orc_contracts.py` — giữ context_patch trong function respond; thêm
  name_contains/excluded_destinations vào find_products nội bộ, mô tả phạm vi tách khỏi chuyến đang lưu.
- `src/backend/app/application/itinerary/orc_dispatch.py` — lọc cụm tên theo ranh giới từ và loại điểm đến trước cấp
  ref; không áp tên property lên phòng con, giữ cursor/coverage theo trang nguồn.
- `src/backend/tests/unit/agents/test_orc_contracts.py` — kiểm final-only vẫn nhận patch có evidence, strict schema.
- `src/backend/tests/unit/agents/test_orc_loop.py` — kiểm final lưu ngày, sửa patch thiếu căn cứ, nghỉ nhẹ/dừng/từ chối tiếp.
- `src/backend/tests/unit/agents/test_orc_tool_dispatch.py` — kiểm đúng tên/ngoài địa điểm, trang rỗng còn cursor,
  đổi phạm vi cursor, phòng khác tên khách sạn.
- `src/backend/tests/unit/application/test_assistant_v2_use_case.py` — hội thoại bốn lượt qua runtime và store thật,
  model viết sẵn: bổ sung ngày → khách → số ngày không làm mất thông tin.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — lược tiêu đề chỉ có tham chiếu tên trước thẻ mới;
  giữ câu dẫn, ref lạ, tên ở lần nhắc sau, vé và hàng thẻ lưu trú.
- `src/frontend/tests/unit/widgetNarration.test.tsx` — kiểm tên chỉ hiện một lần, mở chi tiết, câu dẫn và ref lạ.
- `history/2026-10-14-sua-hoi-thoai-thu-luc-mot-gio.md` — thêm: entry này.

## Quyết định và bằng chứng

- Working tree sạch trước task. Không dùng skill/sub-agent, không commit/push/deploy hay đổi env.
- Log `.logs/web-demo.log` ngày 14/10 01:18–01:19 xác nhận chuỗi hỏi ngày cùng conversationId, 01:37–01:38 có
  find_products thật. Log không chứa arguments/context từng quyết định, chưa xác định gốc lỗi model/lưu ngày.
- Code cũ: context được truyền cho model cùng sáu lượt gần nhất; store merge patch, không tự xóa ngày. Nhưng respond
  bị bỏ context_patch khỏi schema, model phải gọi update_trip riêng/cùng batch. Nay final tự mang cập nhật có evidence,
  cùng validation/commit sau final hợp lệ, kể cả vòng repair chỉ bind respond. Không tự trích ý bằng regex.
- Đường find_products không tự kế thừa destination từ context. Thêm công cụ biểu đạt loại điểm đến và cụm tên cho
  orc, prompt hướng hiểu câu nối tiếp. Lọc bằng chuỗi chỉ thực thi tham số đã khai, không đoán ý khách hay tự gọi tool.
- Ưu tiên tự do không ghi thành free_only bắt buộc. Giữ assumed_free/disclosure và tính grounding.
- Nghỉ nhẹ không tạo sản phẩm/cơ sở ngoài nguồn. Một lần gợi ý ý tưởng cũng tính curiosity_offered; dừng giữ lịch,
  hủy planning_consent. Không đổi tên thương hiệu từ ví dụ Pengo; vẫn Sota.
- Không đổi shape HTTP/SSE, OpenAPI, DB/seed hoặc thuật toán Search/Recommendation. Các spec cũ mô tả v1 không được
  dùng để thay luồng v2. Không áp đề xuất trần 5 thẻ đang chờ chốt.

## Kiểm tra

- Backend (offline, scripted model): **88 passed**, 1 cảnh báo Starlette/AnyIO có sẵn. Lệnh:
  `HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_orc_loop.py src/backend/tests/unit/agents/test_orc_contracts.py src/backend/tests/unit/agents/test_orc_tool_dispatch.py src/backend/tests/unit/application/test_assistant_v2_use_case.py src/backend/tests/unit/application/test_assistant_v2_store.py src/backend/tests/unit/application/test_assistant_v2_final.py src/backend/tests/unit/domain/test_orc_guardrails.py src/backend/tests/contract/test_assistant_v2_contract.py src/backend/tests/architecture`.
- Frontend: `node_modules/.bin/vitest run tests/unit/widgetNarration.test.tsx`: **17 passed**;
  `node_modules/.bin/tsc --noEmit`: PASS;
  `node_modules/.bin/eslint src/features/itinerary/widget/WidgetNarration.tsx tests/unit/widgetNarration.test.tsx`: PASS.
- Ruff trên bảy file Python thay đổi: PASS (binary cache sẵn có, không cài thêm). Lần đầu có ba lỗi style test,
  đã sửa import và dict literal rồi kiểm lại sạch.
- `git diff --check`: PASS.
- Không đổi OpenAPI/mock nên không chạy validate_contract.py; test contract v2 nằm trong 88 test trên.
- Test backend trong sandbox không tiến triển, đã dừng; chạy lại ngoài sandbox được duyệt và hoàn tất.
- Model thật: script thử chỉ ba câu ngày/khách/số ngày với FakeTools, bị sandbox chặn mạng và đã dừng.
  Escalation bị auto-review từ chối do chưa có quyền cụ thể gửi context tới nhà cung cấp. Không chạy vòng tránh.
  Chưa có kết quả model thật; không coi scripted model là bằng chứng prompt hiểu đúng hay đạt SLA.

## Còn lại / rủi ro

- Cần người dùng cho phép gửi prompt hệ thống và hội thoại mẫu tới model cấu hình để kiểm chứng hành vi ngôn ngữ;
  nếu kiểm catalog thật thì cần cho phép gửi cả dữ liệu sản phẩm trả về. Chưa restart backend đang phục vụ người dùng.
- Chưa kiểm bằng browser/LLM thật; cần thử lại cả năm nhóm case. Không đo coverage toàn domain/application hoặc
  full CI. Root cause chính xác của lượt lịch sử vẫn chưa có trace arguments/state để khẳng định.
