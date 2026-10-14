# Hoàn thiện UI tiến trình agent trên orchestrator, Phần A và C

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành (triển khai và kiểm local); B10a staging chưa chạy
- Phạm vi: agent, backend, frontend, contract, docs
- Phục vụ: FR-AGT-01/02/03/06/07, NFR-REL-01, NFR-PERF-02, NFR-SEC-01, AC-AGT-09

## Mục tiêu

Người dùng yêu cầu đọc plan và hoàn thiện việc dở; sau đó xác định lại: “mình cần gỡ code cũ và fix luồng UI hiển thị tiến trình agent”. Người dùng chốt rõ “Chốt cả A và C, thêm thẻ xem trước”. Đã cập nhật PRD trước source, không dùng skill. Không triển khai Phần B, không coi lời chốt UI là bỏ ý AC hoặc chấp nhận lỗi baseline D3.

## File thay đổi trong lượt này

- `docs/prd/requirements.md` — sửa: thêm AC-AGT-09 theo Phần A/C đã chốt.
- `docs/prd/user-flow.md` — sửa: khung tiến trình, dòng tóm tắt, preview và chẩn đoán mức 1.
- `docs/prd/architecture.md` — sửa: grounding tiến trình và preview.
- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: ghi chốt A/C, giữ B chờ chốt.
- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: tiến độ, trọng tâm người dùng và các giới hạn kiểm chứng.
- `docs/spec/product.md` — sửa: bước theo loại lượt, activity, preview và đồng hồ chậm.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: stream 1.27.0 và quy tắc gộp/hiển thị.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: activity, progress, preview và ranh giới bằng chứng.
- `docs/spec/agent/working-context.md` — sửa: bản đồ runtime stream.
- `src/backend/app/agents/graph.py` — sửa: wrapper phát STARTED, gắn progress và preview khi stream.
- `src/backend/app/agents/runtime_dependencies.py` — sửa: stream state/custom trong collector theo request.
- `src/backend/app/application/ports/itinerary_planner.py` — sửa: khai báo cặp state/event.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: chuyển activity/preview và progress thành SSE.
- `src/backend/app/agents/nodes.py` — sửa: activity tìm kiếm, giá/availability và số chuyến bay.
- `src/backend/app/agents/steps/progress.py` — thêm: collector, loại lượt, dữ kiện, mã và preview đã kiểm nguồn.
- `src/backend/app/agents/steps/jobs.py` — sửa: đếm qua các bộ lọc hiện có, nhóm/con trỏ và báo tra cứu thất bại.
- `src/backend/app/agents/steps/fares.py` — sửa: đếm tại bộ lọc chuyến một chiều còn bán.
- `src/backend/app/agents/steps/evaluation.py` — sửa: nhận bộ đếm ở collect, lọc sở thích và lịch tham khảo.
- `src/backend/app/application/itinerary/retrieval.py` — sửa: tham số bộ đếm tuỳ chọn tại nơi lọc.
- `src/backend/app/application/itinerary/flights.py` — sửa: callback activity và bộ đếm tuỳ chọn.
- `src/backend/app/application/itinerary/progress_counts.py` — thêm: mỗi productId một trạng thái đếm, bất biến và giao chosen.
- `src/backend/app/main.py` — sửa: version 1.27.0 khớp OpenAPI.
- `src/backend/tests/unit/agents/test_progress.py` — thêm: phân hoạch, đếm tại trang, gần mốc, preview, stream và parity JSON.
- `src/backend/tests/contract/test_assistant_contract.py` — sửa: kiểm payload progress và không có debug/secret.
- `src/backend/tests/contract/test_search_contract.py` — sửa: đồng bộ version contract.
- `src/backend/tests/contract/test_search_llm_contract.py` — sửa: đồng bộ version contract.
- `src/frontend/src/context/assistantState.ts` — sửa: state tiến trình, activity, run, preview và ảnh chụp tóm tắt vào transcript.
- `src/frontend/src/context/AssistantProvider.tsx` — sửa: đọc sự kiện và đồng hồ 5 giây/12 giây.
- `src/frontend/src/services/assistantStream.ts` — sửa: sự kiện mới.
- `src/frontend/src/features/itinerary/widget/progressModel.ts` — thêm: gộp theo groupId và khoá thông báo, không cộng số.
- `src/frontend/src/features/itinerary/widget/widgetProgressLabels.ts` — thêm: nhãn tiếng Việt, dữ kiện và lý do loại.
- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa: bước theo loại lượt và activity thật.
- `src/frontend/src/features/itinerary/widget/WidgetProgress.tsx` — sửa: dữ kiện, lưu ý, trạng thái, hỗ trợ giảm chuyển động.
- `src/frontend/src/features/itinerary/widget/WidgetProgressSummary.tsx` — thêm: thu gọn/mở rộng với aria-expanded/controls.
- `src/frontend/src/features/itinerary/widget/WidgetProgressPreview.tsx` — thêm: tối đa 6 thẻ chỉ xem, mở panel chi tiết.
- `src/frontend/src/features/itinerary/widget/AssistantProgressDiagnostics.tsx` — thêm: run/request, thời gian, activity và số đếm công khai.
- `src/frontend/src/components/common/DebugPanel.tsx` — sửa: gắn chẩn đoán trợ lý mức 1.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: tiến trình mới, preview và tóm tắt trước lời đáp/thẻ.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: đưa progress của transcript vào message.
- `src/frontend/src/features/itinerary/widget/widgetTypes.ts` — sửa: kiểu progress của message.
- `src/frontend/src/types/api.gen.ts` — sinh lại từ contract, không sửa tay.
- `src/frontend/tests/unit/progressModel.test.ts` — thêm: số cộng dồn, nhóm bị thay, đổi loại lượt.
- `src/frontend/tests/unit/widgetProgress.test.ts` — sửa: kiểm các loại lượt từ fixture stream.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — sửa: activity, preview 5 giây, không nháy và dừng.
- `src/frontend/tests/unit/debugPanelAssistant.test.tsx` — thêm: chẩn đoán tắt/bật và thời gian/request.
- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: stream theo thời gian, preview/summary và 390/1024 px.
- `src/shared/contracts/openapi.yaml` — sửa: version 1.27.0 và component mới.
- `src/shared/contracts/paths/itinerary-agent.yaml` — sửa: mô tả các sự kiện mới.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: schema progress, activity, preview và node.completed.
- `src/shared/contracts/tests/validate_contract.py` — sửa: kiểm data từng sự kiện, negative check.
- `src/shared/mocks/index.json` — sửa: đăng ký 8 fixture stream.
- `src/shared/mocks/itinerary-agent/stream-plan.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `src/shared/mocks/itinerary-agent/stream-explore-jobs.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `src/shared/mocks/itinerary-agent/stream-fare-superseded.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `src/shared/mocks/itinerary-agent/stream-fare-job.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `src/shared/mocks/itinerary-agent/stream-fare-button.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `src/shared/mocks/itinerary-agent/stream-clarify.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `src/shared/mocks/itinerary-agent/stream-answer.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `src/shared/mocks/itinerary-agent/stream-blocked.json` — thêm: fixture stream theo contract; dữ liệu tổng hợp cho kiểm thử, không phải demo LLM thật.
- `history/2026-10-13-hoan-thien-ui-tien-trinh-agent.md` — thêm: entry này.

## Quyết định và tài liệu đã đọc

- Đọc PRD README, architecture (§2,3,6), requirements (FR-AGT/NFR/AC), user-flow (§4.2), test-plan, implementation-plan; contract guide, minimal-fields, OpenAPI và fragment assistant/common/search; tài liệu tích hợp backend/frontend/agent, product (§6), backend/frontend README, frontend AGENTS; agent README/working-context/state/response; mocks README và architecture-repo. Đọc hai plan, đề xuất tiến trình và history README; các entry review plan 12/10, ưu tiên demo, chốt orchestrator, D0/D2/D3, gỡ luồng cũ và history UI liên quan.
- Code cũ đã gỡ trước lượt này. Kiểm lại runtime/graph/config: không còn classify_node, explore_node, CLASSIFY_PROMPT, EXPLORE_PROMPT, TurnRoute, ExploreNarration hay cờ bật/tắt ITINERARY_ORCHESTRATOR. Các biến MODEL/PROVIDER/REASONING của orchestrator vẫn là cấu hình đang dùng, không phải cờ luồng cũ. Không xoá helper còn dùng hoặc nhận là lượt này đã làm lại việc xoá cũ.
- Theo trọng tâm mới, thực hiện UI A/C, không mở rộng sang sửa lỗi demo D4–D5. Collector theo request trong stream, không vào AgentState lưu, không đổi response JSON, payload LLM hay tham số tool. Snapshot D3 giữ nguyên trong lượt này; 4 ca phát lại xanh trong bộ backend.
- Phần B chưa chốt nên đề xuất vẫn trong update/, ghi rõ A/C đã áp dụng. Chưa thêm khoá debug, chưa phát tool/LLM details. Không tự chốt B.
- Bộ đếm ở đúng chỗ lọc, mỗi productId một ô. Job tiếp dùng nhóm gốc; superseded ẩn nhóm và thông báo. Query/tổng nguồn không dùng cho câu người dùng. Câu vé có ngày/khung giờ nhưng thẻ có ngày/giờ lân cận bỏ số khi không biểu diễn đúng phạm vi được; job không khai taxonomy trả nhiều loại không gán giả một loại. Không ước lượng.
- Preview sau compose chỉ từ response đã có nguồn, không vé bay, tối đa 6, đợi 5 giây; thẻ chỉ mở chi tiết. Dừng/lỗi/hoàn tất gỡ preview. Transcript chỉ giữ tóm tắt trong phiên Web; archive tải lại không có tiến trình, đúng giới hạn A/Q7 đã chốt.
- Instrument bộ lọc hiện có trước D4 theo trọng tâm người dùng; D4 sau này phải cập nhật bộ đếm/test nếu thay bộ lọc. Không tăng giới hạn tool, không sửa prompt hoặc ghi lại snapshot để che hồi quy.

## Kiểm tra thực tế

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS, 129 schemas, 104 fixtures, gồm 8 fixture stream và negative checks khoá/mã/groupId/preview quá 6.
- `HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false timeout 120s .venv/bin/python -m pytest -q src/backend/tests`: **2859 passed, 36 skipped, 3 xfailed**, 43.38s; exit 0. Xfail là 3 lỗi AC-AGT-08 của baseline, không tăng hoặc coi đã sửa. Một cảnh báo Starlette/AnyIO deprecation.
- Focused backend: progress, orchestrator jobs, snapshot, assistant contract và architecture: **55 passed**, gồm kiểm stream thật qua graph với model/tool giả và JSON parity; không gọi LLM thật.
- Frontend `npm exec -- vitest run --maxWorkers=1`: **843 passed, 81 files**, 60.63s; exit 0. Kiểm kiểu `tsc --noEmit` và ESLint file UI/context đã sửa: exit 0.
- `npm run build:web`: PASS; Next.js 16.3.5, build TypeScript và static pages xong. Build và graph tests chạy ngoài sandbox sau khi sandbox chặn tiến trình con hoặc treo asyncio khi teardown; không thay cấu hình dự án để lách.
- Playwright `widget-opening.spec.ts` + `widget-detail.spec.ts`: **10 passed**. Sau chỉnh fixture thống nhất ý định/response và chủ động giữ trạng thái để chụp, chạy lại 2 ca tiến trình: **2 passed**, 390/1024 px; preview không có Thêm/Đặt ngay, tóm tắt có aria-expanded, không overflow. Ảnh `/tmp/travel-agent-progress-390.png`, `/tmp/travel-agent-progress-1024.png`.
- Đã xem ảnh 390 px: khung tiến trình, lưu ý và thẻ preview nằm trong màn, chữ xuống dòng; không dùng ảnh này làm bằng chứng dữ liệu catalog/LLM thật.
- Lần kiểm rộng ban đầu: backend 2 lỗi do version test khoá 1.26.0, đã đồng bộ 1.27.0; lần 90s bị cắt khi khoảng 52%. Frontend một ca instantSearchPanel quá thời gian khi chạy nhiều worker, chạy riêng 6/6 và cả bộ tuần tự 843/843 xanh. Không báo các lần ban đầu là xanh.
- `git diff --check`: sạch. Không commit. Dọn đúng hai tiến trình pytest do lượt này chạy trong sandbox bị treo; giữ nguyên backend đang chạy của người dùng.

## Còn lại / rủi ro

- B10a: chưa triển khai hoặc tổng duyệt staging với LLM thật, chưa đối chiếu số/preview với LangSmith cùng requestId. Không có bằng chứng SLA hoặc latency staging từ các test fixture này.
- D4–D5 và G0/G2/G3/G4/G7 của plan chung vẫn riêng; các lỗi demo/AC trong D1/D3 không tự biến thành đạt vì UI đã sửa.
- Phần B của đề xuất tiến trình còn chờ người dùng chốt. Không cần chốt lại A/C.
- Working tree có nhiều thay đổi của phiên trước, đã giữ nguyên. Entry này chỉ liệt kê file sửa/thêm trong lượt này; thay đổi gỡ code cũ đã có history riêng D3.
