# Think/Act/Observe, kiểm phòng và khơi tò mò bằng dữ liệu

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành (triển khai v2 và kiểm kỹ thuật); chất lượng LLM người dùng tự eval
- Phạm vi: agent, backend, frontend, contract, docs
- Mã FR/NFR: FR-AGT-01–06, NFR-REL-01, NFR-PERF-02, NFR-MAINT-02; AC-AGT-01/02/04/06/07/09
- Thay thế phần trạng thái chờ chốt/chưa triển khai: `2026-10-13-de-xuat-giai-thich-quyet-dinh-agent.md`, `2026-10-13-plan-cai-thien-agent-tien-trinh-va-gia.md`, `2026-10-13-de-xuat-khoi-goi-to-mo-agent.md`.

## Mục tiêu

Người dùng đồng ý Think → Act → Observe thay câu mẫu, xác nhận lịch thiếu chiều và phòng sức chứa 8 người, rồi yêu cầu thực thi. Sau đó chốt phân biệt mất hứng với dừng rõ: một lựa chọn mới có nguồn khơi tò mò khi mất hứng; dừng rõ/từ chối tiếp thì dừng. Người dùng tự eval chất lượng sau triển khai.

## File thay đổi

- `docs/prd/architecture.md` — sửa.
- `docs/prd/requirements.md` — sửa.
- `docs/prd/user-flow.md` — sửa.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa.
- `docs/spec/product.md` — sửa.
- `src/backend/app/agents/orc_v2.py` — sửa.
- `src/backend/app/application/itinerary/orc_contracts.py` — sửa.
- `src/backend/app/application/itinerary/v2_final.py` — sửa.
- `src/backend/app/domain/itinerary/draft_validation.py` — sửa.
- `src/backend/app/domain/itinerary/orc_guardrails.py` — sửa.
- `src/backend/tests/contract/test_assistant_v2_contract.py` — sửa.
- `src/backend/tests/fakes/orc_tools.py` — sửa.
- `src/backend/tests/unit/agents/test_orc_loop.py` — sửa.
- `src/backend/tests/unit/application/test_assistant_v2_final.py` — sửa.
- `src/backend/tests/unit/domain/test_orc_draft_validation.py` — sửa.
- `src/frontend/src/context/AssistantProvider.tsx` — sửa.
- `src/frontend/src/context/assistantState.ts` — sửa.
- `src/frontend/src/features/itinerary/widget/WidgetProgress.tsx` — sửa.
- `src/frontend/src/features/itinerary/widget/progressModel.ts` — sửa.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa.
- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa.
- `src/frontend/src/features/itinerary/widget/widgetV2.ts` — sửa.
- `src/frontend/src/types/assistant-v2.gen.ts` — sinh lại từ contract.
- `src/frontend/tests/unit/widgetV2.test.ts` — sửa.
- `src/shared/contracts/assistant-v2.openapi.yaml` — sửa.
- `src/shared/contracts/schemas/assistant-v2.yaml` — sửa.
- `docs/plan/2026-10-13-cai-thien-agent-tien-trinh-gia-phong-va-loi-goi-y.md` — thêm và cập nhật tiến độ triển khai.
- `docs/prd/update-archive/2026-10-13-giai-thich-quyet-dinh-agent-trong-tien-trinh.md` — đổi tên từ docs/prd/update/ và sửa: đã áp dụng PRD sau người dùng chốt.
- `docs/prd/update-archive/2026-10-13-khoi-goi-to-mo-khi-khach-mat-hung.md` — đổi tên từ docs/prd/update/ và sửa: đã áp dụng PRD sau người dùng chốt.
- `history/2026-10-13-de-xuat-khoi-goi-to-mo-agent.md` — thêm.
- `src/frontend/tests/e2e/widget-v2-progress.spec.ts` — thêm.
- `history/2026-10-13-think-act-observe-va-tu-van-co-nguon.md` — thêm.

## Quyết định

- Đọc PRD README/requirements/architecture/user-flow/project-brief/DoD/test-plan, các đề xuất liên quan, history README và các entry mới nhất/v2/kể chuyện/tiến trình; tài liệu backend/frontend/agent/contract theo phạm vi và kiểm source trực tiếp trước sửa.
- Hai đề xuất được người dùng đồng ý trong chat, cập nhật PRD trước contract/code và lưu trữ cùng thay đổi. Không dùng skill.
- Giữ graph decide ⇄ dispatch và provider/quota. explanation công khai ngắn nằm trong cùng quyết định, kiểm trước phát; không xuất suy luận nội bộ, không thêm model call. Thiếu hoặc có số liệu/link/secret không kiểm được thì bỏ explanation, không phá final.
- Act từ call đã kiểm; Observe phát khi từng call song song xong, results trong state vẫn giữ thứ tự call. Số chọn/hiển thị cập nhật cùng group không thêm vòng giả. UI v2 giữ danh sách vòng thay vì chuyển về ba bước v1, phân biệt found/eligible/selected/displayed và empty/error/needs_input.
- engagement do LLM chọn với evidence của message/nút. Code chặn tool khi dừng rõ, chặn build_itinerary khi stopped, kiểm một lần khơi tò mò và không lặp refs đã shown. Chỉ commit curiosity_offered sau final hợp lệ; dừng hủy consent, tiếp tục khám phá không tự cấp consent. Đồng ý lập lịch mới có căn cứ vẫn được nhận.
- Prompt chủ động tra catalog/recommendation khi khách chưa biết gì, khơi tò mò bằng dữ kiện cụ thể, không chỉ hẹn quay lại. Prompt kể chuyện v2 đã có từ trước được giữ; chưa tái hiện trace/model thật của lỗi liệt kê nên không nhận đã chứng minh hết lỗi đó.
- Không thay công thức ceil(adults/priceAdults) đã chốt. Kiểm maxOccupancy riêng gồm trẻ em; phòng chứa 8 và giá gồm 8 khác phòng chứa 8 nhưng giá gồm 2. Thiếu cơ sở giá trả rooms=null, total unknown; bỏ cảnh báo sai “tạm một phòng”; widget giữ số phòng chưa xác định. Vượt sức chứa trả violation cho orc chọn lại; thiếu sức chứa có warning.
- Prompt phân bổ sáng/chiều cho ngày đủ cửa sổ/dữ liệu, giữ ngoại lệ chỉ sáng/hoạt động cả ngày/giờ bay. Adapter/UI kiểm giữ giờ chiều. Đây chưa phải bằng chứng LLM thật luôn lập lịch hợp lý.
- `src/backend/app/agents/steps/prompts.py` có thay đổi ngoài task xuất hiện trong lúc làm (V-OTA → S-OTA); giữ nguyên, không sửa/stage và không nhận là thay đổi của task này. Hai entry history đề xuất/plan trước đó đã có từ lượt trước, giữ nguyên nội dung.
- Không commit/push/deploy, không sửa cấu hình mặc định widget. Build kiểm với NEXT_PUBLIC_ASSISTANT_API=v2 chỉ tạo artifact local; client v1 giữ tương thích.

## Kiểm tra

- Backend trọng tâm (orc_loop, orc_contracts, draft_validation, assistant_v2_final/use_case, contract v2, architecture): lần cuối 58 passed; 1 cảnh báo Starlette/AnyIO deprecation có sẵn. Lệnh: `HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_orc_loop.py src/backend/tests/unit/agents/test_orc_contracts.py src/backend/tests/unit/domain/test_orc_draft_validation.py src/backend/tests/unit/application/test_assistant_v2_final.py src/backend/tests/unit/application/test_assistant_v2_use_case.py src/backend/tests/contract/test_assistant_v2_contract.py src/backend/tests/architecture`.
- Frontend: widgetV2/widgetDays/widgetStayOptions/progressModel/widgetProgress/assistantState/assistantProvider: 78 passed; TypeScript và ESLint các file frontend/test sửa: PASS sau sửa kiểu của fixture test.
- `validate_contract.py`: PASS, v2 36 schemas/8 fixtures/14 negative; v1 130 schemas/106 fixtures; CDP 12 schemas/7 fixtures/11 negative. `generate:assistant-v2-types`: PASS.
- Build `NEXT_PUBLIC_ASSISTANT_API=v2 npm run build:web`: PASS; bản build bao gồm kiểm TypeScript tại thời điểm build.
- Browser: `NEXT_PUBLIC_ASSISTANT_API=v2 PLAYWRIGHT_PORT=3118 npm exec -- playwright test tests/e2e/widget-v2-progress.spec.ts`: 2 passed, 390 và 1024 px. Ảnh `/tmp/travel-v2-progress-{390,1024}.png`; đã xem ảnh 390 px, không cuộn ngang, các vòng/giải thích/số đúng fixture.
- Trong sandbox, backend async đứng chờ và build lỗi đọc cấu hình TypeScript từ process con. Dừng các lệnh đứng, chạy ngoài sandbox được automatic review cho phép: đạt. Lần Playwright đầu dùng binary trực tiếp thiếu PATH cross-env; dùng npm exec rồi đạt. Không nhận các lần lỗi là pass.
- Một lần kiểm TypeScript sau thêm test unknown rooms báo fixture thiếu status theo kiểu sinh; sửa cast cùng cách các fixture hiện có rồi kiểm lại. Không thay dữ liệu runtime để làm test xanh.
- `git diff --check`: PASS trước ghi entry; tài liệu mới kiểm khoảng trắng/conflict marker trước bàn giao.

## Còn lại / rủi ro

- Chưa chạy model/catalog thật, chưa có trace đầy đủ của hội thoại người dùng. Người dùng tự eval các ca trong plan; fixture/scripted model chỉ chứng minh thực thi và hiển thị, không chứng minh tự chủ/giọng văn/chất lượng lịch.
- Không chạy toàn bộ backend/frontend; không nói baseline snapshot v1 hoặc toàn bộ CI đã xanh. Không thay cassette.
- pytest-cov chưa cài; chưa đo DoD coverage domain/application ≥80%, không nhận đã đạt toàn bộ DoD/production acceptance. Không thay DB/seed nên không chạy db/verify.sql.
- Muốn dùng bản này cần bật NEXT_PUBLIC_ASSISTANT_API=v2 khi chạy/build frontend cho eval; chưa tự chuyển mặc định v2 hoặc ngừng v1. Theo plan E12/E13 hiện có cho nghiệm thu/chuyển phiên bản.
