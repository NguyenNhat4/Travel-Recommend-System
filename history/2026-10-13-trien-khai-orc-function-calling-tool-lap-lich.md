# Triển khai orc function calling và tool lập lịch theo buổi

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, docs
- Mã FR/NFR: FR-AGT-01/02/03/05/06/07, NFR-REL-01, NFR-MAINT-01/02; AC-AGT-01/02/04/07/09

## Mục tiêu

Người dùng yêu cầu xem plan mới sửa rồi thực hiện; chốt A–G và triển khai toàn bộ trong chat. Plan
`docs/plan/2026-10-13-orc-function-calling-va-tool-lap-lich.md`. Sau khi automatic review từ chối gọi model thật,
người dùng cho phép cụ thể gửi prompt/câu hội thoại mẫu/catalog local tới OpenAI gpt-6-luna để kiểm thử.
Sau đó người dùng yêu cầu "ko cần đo" và "hoàn thiện đi": dừng các phép đo thật, hoàn tất triển khai và kiểm kỹ thuật local.

## File thay đổi

- `docs/prd/architecture.md` — sửa: áp dụng A–G, function calling và lịch theo buổi.
- `docs/prd/requirements.md` — sửa: bộ tool và tính giờ/đêm/phòng có căn cứ.
- `docs/spec/agent/working-context.md` — sửa: bản đồ tool v2 mới.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: giao thức, lập lịch và giá phòng v2.
- `docs/plan/2026-10-13-orc-function-calling-va-tool-lap-lich.md` — cập nhật plan có sẵn trong working tree: tiến độ và giới hạn nghiệm thu.
- `src/backend/app/agents/orc_v2.py` — sửa: native tool messages, control tools, quota, prompt và tiến trình.
- `src/backend/app/agents/steps/messages.py` — sửa: log binding function tools.
- `src/backend/app/application/itinerary/orc_contracts.py` — sửa: năm tool nghiệp vụ và hai control schemas.
- `src/backend/app/application/itinerary/orc_dispatch.py` — sửa: gộp tìm/duyệt, phòng lồng, detail theo batch, Similar và lập lịch.
- `src/backend/app/application/itinerary/product_registry.py` — sửa: metadata buổi/ngày và lỗi cursor có nguyên nhân.
- `src/backend/app/application/itinerary/v2_final.py` — sửa: phòng đã tính, fact theo index mảng, format giờ và cảnh báo giá.
- `src/backend/app/application/ports/llm.py` — sửa: binding options tuỳ chọn, giữ provider defaults cho v1.
- `src/backend/app/domain/itinerary/draft_validation.py` — sửa: tính buổi, đêm, phòng, chi phí, savings và kiểm ứng viên còn dùng được.
- `src/backend/app/infrastructure/llm/client.py` — sửa: wire strict nullable và adapter riêng từng provider.
- `src/backend/tests/fakes/orc_tools.py` — sửa: AIMessage/tool-call fakes và phòng theo property.
- `src/backend/tests/unit/agents/test_orc_contracts.py` — sửa: kiểm schemas mới và strict conversion.
- `src/backend/tests/unit/agents/test_orc_loop.py` — sửa: hội thoại nối thêm, controls, quota, final repair và stop/rekindle.
- `src/backend/tests/unit/agents/test_orc_tool_dispatch.py` — sửa: request vật lý, paging/filter, lỗi từng phòng/ref và consent feedback.
- `src/backend/tests/unit/agents/test_orc_registry.py` — sửa: kiểm availability_by_date.
- `src/backend/tests/unit/application/test_assistant_v2_final.py` — sửa: fact giờ/mảng và cảnh báo giá phòng.
- `src/backend/tests/unit/domain/test_orc_slot_planning.py` — thêm: kiểm số học, giờ mở, sân bay, lịch cả ngày, savings và sparse days.
- `src/backend/tests/unit/infrastructure/test_llm_factory.py` — sửa: kiểm provider options, Responses clone và binding v1.

- `docs/prd/update/2026-10-13-thiet-ke-lai-bo-tool-orc.md` → `docs/prd/update-archive/2026-10-13-thiet-ke-lai-bo-tool-orc.md` — áp dụng A–G đã chốt, lưu trữ.
- `docs/prd/update/2026-10-13-diem-den-trong-system-prompt-bo-tool-destinations.md` → `docs/prd/update-archive/2026-10-13-diem-den-trong-system-prompt-bo-tool-destinations.md` — áp dụng A và lưu trữ cùng.
- `history/2026-10-13-trien-khai-orc-function-calling-tool-lap-lich.md` — thêm: entry này.

## Quyết định

- Không dùng skill hay sub-agent. Đọc plan/PRD/spec/contract/history, cập nhật PRD trước code sau người dùng chốt A–G.
- Năm tool nghiệp vụ + update_trip/respond; chỉ gọi tool đã qua schema, mọi provider kiểm local. Metadata evidence
  vẫn bắt buộc và không commit context/plan/shown trước final hợp lệ. Tool lỗi không huỷ call độc lập thành công.
- Append-only messages trong lượt, ToolMessage ghép đúng provider call id và mã server cN; view sản phẩm chỉ gửi
  khi mới/thay đổi. Cả schema final sai và guard sai chỉ được sửa một lần. Giữ 3 rounds, 3 calls/round, 10 nguồn, 5 model calls.
- OpenAI strict buộc optional nullable/required trên wire. Gemini/Anthropic dùng any, không truyền strict OpenAI.
  Kiểm thật gặp 400 gpt-6-luna + reasoning trên Chat Completions: clone model dùng Responses API cho bind_tools,
  giữ model/effort/cấu hình và structured-output v1. Không sửa env, DB, gateway/thuật toán engine hay frontend/contract v2.
- plan_itinerary chọn từ schedule theo buổi, code tính giờ, đêm tối đa N−1, phòng tổng khách/priceAdults hoặc sức chứa
  kèm cảnh báo, giá từng dòng, tỷ trọng/savings; không đổi refs. Combo gợi ý riêng; giữ fixed_times và locked_refs.
- Find hotel kèm phòng vẫn tính request vật lý, báo thiếu/lỗi rõ; nhiều detail giữ refs thành công/lỗi từng ref;
  cursor nói tên tham số đã đổi. Catalog filter áp trên trang trước khi registry cấp refs; không tự tiếp trang.
- View sản phẩm bổ sung buổi vừa thời lượng/giờ mở, cửa sổ/lịch còn chỗ và bảng ngày đã tính để model không phải đếm
  calendar; dữ kiện hiện tại và ngày Việt Nam ở payload. Đọc fact theo index mảng và format phút thành HH:MM.
- Ngày trọn vẹn ít hoạt động nhưng còn ứng viên đã tra phù hợp trả TOO_FEW_ACTIVITIES cho orc sửa; hoạt động cả ngày
  dùng hai buổi, ngày bay ngắn được ít hơn. Không tự bù sản phẩm.
- Các file bẩn trước task: `src/evaluation/agent/assistant_v2_cases.py`, hai history đề xuất/plan do phiên khác tạo
  được giữ nguyên; không nhận thay đổi đó là code task này. Đề xuất/plan đã được người dùng cho phép áp dụng/cập nhật.
- Không commit/push/deploy. Backend gốc 8000 giữ nguyên; đã dừng backend 8001 riêng của task và runner đo thật.

## Kiểm tra

- Bộ kỹ thuật cuối: 257 passed, 1 Starlette/AnyIO deprecation có sẵn, 11.10s. Kiểm unit v2/domain/fare/store,
  contract response, architecture và runtime/tool/history v1; model giả, không gọi model thật.
- Lệnh tái chạy (repo root):

  ```bash
  HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_orc_loop.py src/backend/tests/unit/agents/test_orc_contracts.py src/backend/tests/unit/agents/test_orc_tool_dispatch.py src/backend/tests/unit/agents/test_orc_registry.py src/backend/tests/unit/infrastructure/test_llm_factory.py src/backend/tests/unit/domain/test_orc_draft_validation.py src/backend/tests/unit/domain/test_orc_slot_planning.py src/backend/tests/unit/domain/test_orc_guardrails.py src/backend/tests/unit/application/test_assistant_v2_final.py src/backend/tests/unit/application/test_assistant_v2_use_case.py src/backend/tests/unit/application/test_assistant_v2_store.py src/backend/tests/unit/application/test_orc_flight_lookup.py src/backend/tests/contract/test_assistant_v2_contract.py src/backend/tests/architecture src/backend/tests/unit/agents/test_itinerary_runtime.py src/backend/tests/unit/agents/test_itinerary_tools.py src/backend/tests/unit/agents/test_conversation_history.py
  ```

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS
  (v2 36 schemas/8 fixtures/14 negative; v1 130 schemas/106 fixtures; CDP 12/7/11).
- Ruff check trên toàn bộ 17 file Python của task: PASS; `git diff --check`: PASS.
- Model/catalog thật: đã dừng theo yêu cầu người dùng. Các artifacts trước đó ở
  `/tmp/orc-function-{before,after,final,verified}.json` chỉ là thử nghiệm trong lúc triển khai, không nghiệm thu prompt cuối.
  Không nhận fixture/scripted model là bằng chứng LLM/SLA và không tiếp tục tạo report đo.
- Lần gọi sandbox pytest bị treo; dừng đúng process, chạy ngoài sandbox được duyệt và đạt. Model thật ban đầu bị
  auto-review từ chối; không bypass, hỏi quyền cụ thể và được cho phép. Một lần ruff trong venv không có binary;
  dùng binary cache có sẵn, không cài dependency.

## Còn lại / rủi ro

- Không còn phần triển khai chờ chốt trong A–G. Phần đo model được bỏ theo yêu cầu người dùng; prompt cuối chưa được
  nghiệm thu bằng model thật, không nhận các lần thử trước là kết quả xác minh bản cuối.
- Chưa có pytest-cov/coverage trong môi trường; không nhận DoD toàn domain/application ≥80% đã đạt.
- Không chạy toàn bộ CI hay kiểm v1 bằng model thật; không nhận đạt SLA 4s hoặc model accuracy ≥95% khi chưa chấm đủ.
