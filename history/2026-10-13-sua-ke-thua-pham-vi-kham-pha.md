# Sửa kế thừa phạm vi khám phá và số lượng theo yêu cầu

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: agent, backend, frontend, contract, docs

## Mục tiêu

Người dùng báo: tìm toàn catalog rồi "10 chỗ khác" bị thu về Vũng Tàu; "không chỉ Vũng Tàu" vẫn tìm Vũng Tàu.
Sửa phạm vi theo FR-AGT-06/AC-AGT-06, giữ NFR-REL-01; áp dụng số lượng linh hoạt sau khi người dùng chốt.
Tiến trình cần giải thích quyết định tìm kiếm của lượt hiện tại theo AC-AGT-09.
Phần triển khai và kiểm tra nội bộ đã xong; chưa nghiệm thu model thật/bản ghi hội thoại mới.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-AGT-06/AC-AGT-06 dùng số lượng được yêu cầu, mặc định 3/2/4, tổng tối đa 20.
- `docs/prd/architecture.md` — sửa: số lượng có cấu trúc, code kiểm và áp dụng trong ngân sách.
- `docs/prd/update-archive/2026-10-13-so-luong-goi-y-theo-yeu-cau.md` — thêm, chuyển từ update sau chốt:
  ghi quyết định và trạng thái đã áp dụng. File chưa tracked nên dùng rename thay git mv.
- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa: bổ sung phạm vi/số lượng, ghi nhu cầu cập nhật cassette.
- `docs/spec/agent/nghiep-vu/tro-chuyen-va-kham-pha.md` — sửa: phạm vi tìm khác thành phố của thẻ, số lượng,
  continuation và trả một phần.
- `docs/spec/agent/state-fields.md` — sửa: nghĩa null của via.destination, excluded_destinations,
  requested_count thuộc lượt và không nhân theo alias.
- `docs/spec/agent/langgraph-nodes.md` — sửa: cạnh continuation cho số lượng còn thiếu và mức thẻ mặc định/được yêu cầu.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: contract 1.28.0, schema khám phá, scope tiến trình.
- `docs/spec/product.md` — sửa: giải thích đổi phạm vi, nơi không xét và mục tiêu số lượng ở bước hiểu yêu cầu.
- `src/backend/app/agents/models.py` — sửa: Job.scope_mode, excluded_destinations, requested_count nội bộ cho orchestrator.
- `src/backend/app/agents/steps/jobs.py` — sửa: kế thừa điều kiện chung, giữ destination=null của via; thay phạm vi,
  chuẩn hoá/lọc nơi không xét; brief có số lượng; lỗi continuation giữ source_job và số lượng nguồn.
- `src/backend/app/agents/steps/shown.py` — sửa: lưu excluded_destinations có giá trị trong via, không lưu requested_count.
- `src/backend/app/agents/steps/prompts.py` — sửa: hiểu mở rộng phạm vi, ưu tiên yêu cầu mới; không lấy thành phố
  thẻ cuối làm lựa chọn của khách; số lượng theo yêu cầu; không continue_from khi đổi phạm vi.
- `src/backend/app/agents/steps/orchestration.py` — sửa: lấy thêm brief trong phanh khi số lượng chưa đủ;
  báo số thực chọn/yêu cầu và lý do thiếu, thông báo trần 20 bằng code.
- `src/backend/app/agents/steps/progress.py` — sửa: scope công khai gồm quyết định giữ/thay, nơi không xét và số lượng;
  không gửi query thô.
- `src/backend/app/agents/steps/validation.py` — sửa: kiểm tổng 20 trong response khám phá trước finalize.
- `src/backend/app/domain/itinerary/gatekeeper.py` — sửa: kiểm lại nơi không xét, trần số lượng theo nguồn, tổng 20;
  bù thẻ từ mã mới đã liệt kê, không nhân số lượng theo alias; giữ thẻ vé trong giới hạn tổng.
- `src/backend/app/main.py` — sửa: version khớp contract 1.28.0.
- `src/backend/tests/unit/agents/test_orchestrator_jobs.py` — sửa: hồi quy thẻ nhiều thành phố, legacy và thay phạm vi.
- `src/backend/tests/unit/agents/test_orchestrator_runtime.py` — sửa: graph đổi phạm vi, đủ 10, thiếu dữ liệu,
  hết vòng, lỗi trang tiếp, yêu cầu hơn 20.
- `src/backend/tests/unit/agents/test_progress.py` — sửa: scope tiến trình mới đúng contract, không query thô.
- `src/backend/tests/unit/domain/test_orchestrator_gatekeeper.py` — sửa: phạm vi loại nơi, số lượng, alias,
  tổng 20, thẻ chưa liệt kê/đã xem, giữ thẻ vé.
- `src/backend/tests/contract/test_search_contract.py` — sửa: version pin 1.28.0.
- `src/backend/tests/contract/test_search_llm_contract.py` — sửa: version pin 1.28.0.
- `src/shared/contracts/openapi.yaml` — sửa: version 1.28.0, schema khám phá riêng.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: ExplorationSearchResults tối đa 20/nhóm, flight vẫn 4;
  không nới kết quả đi kèm lịch đã xếp; thêm scopeMode/excludedDestinations/requestedCount của tiến trình.
- `src/shared/contracts/tests/validate_contract.py` — sửa: chấp nhận 10/20, từ chối 21 cùng nhóm và 5 flight.
- `src/shared/mocks/index.json` — sửa: đăng ký fixture explore-ten.
- `src/shared/mocks/itinerary-agent/explore-ten.json` — thêm: 10 khách sạn từ sample thật.
- `src/shared/mocks/itinerary-agent/README.md` — sửa: hướng dẫn fixture mới.
- `src/frontend/src/types/api.gen.ts` — sinh lại từ OpenAPI bằng generate:api-types.
- `src/frontend/src/features/itinerary/widget/widgetProgressLabels.ts` — sửa: giải thích thay phạm vi,
  nơi không xét và mục tiêu số lượng từ scope công khai.
- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa: nhãn bước giải thích bằng tiếng Việt.
- `src/frontend/tests/unit/widgetProgress.test.ts` — sửa: giải thích phạm vi nhiều nơi và mục tiêu 10.
- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: 10 thẻ và giải thích phạm vi/số lượng ở 390/1024 px.
- `history/2026-10-13-sua-ke-thua-pham-vi-kham-pha.md` — thêm: entry của task này.

Danh sách đối chiếu git status, chỉ file sửa trong task này; giữ diff có sẵn của các task trước, không commit.
next-env.d.ts do build đổi đường dẫn sinh tự động được trả về nội dung đầu task, không có diff sau cùng.

## Quyết định

- Trước sửa, inherited dùng thành phố/via của thẻ cuối. Kiểm thử tái hiện destination=null thành thành phố
  của thẻ cuối, cả khi via lưu null rõ ràng và khi thẻ legacy không có via.
- Phân biệt kế thừa với thay phạm vi bằng quyết định cấu trúc của LLM; không thêm regex đoán câu người dùng.
  Đây là sửa việc giữ điều kiện chưa đổi và trả đúng yêu cầu, không thay FR/AC về phạm vi.
- Loại nơi trong việc tìm không đồng nghĩa khách chê nơi đó cho cả hội thoại.
- Người dùng chốt: "Chốt số lượng theo yêu cầu, trần 20". Áp dụng PRD và lưu trữ đề xuất trước code số lượng.
- requested_count khai nguyên số đã hiểu để code tự thông báo trần 20; không nêu thì null, không kế thừa số lượt cũ.
  Nguồn còn thì lấy tiếp brief trong phanh có sẵn; LLM vẫn hiểu yêu cầu/điều phối chung, code kiểm dữ liệu và số lượng.
- Không lấy sản phẩm chưa được liệt kê trong brief, trùng hoặc ngoài điều kiện để điền đủ số.
- Tiến trình giải thích quyết định bằng phạm vi/số lượng có cấu trúc, không suy luận thô, prompt hay query.
- Không thay cassette cũ bằng đáp án tự dựng hoặc bỏ hai lỗi snapshot khỏi báo cáo để gọi toàn suite xanh.

## Kiểm tra

- Ba kiểm thử phạm vi mới trước sửa → 3 failed: hai lỗi thu phạm vi về thẻ cuối, schema chưa có cách thay phạm vi.
- Unit jobs + gatekeeper sau sửa → 46 passed.
- Jobs + orchestrator runtime + shown + gatekeeper + progress + architecture ban đầu → 98 passed, 4.82 s.
- Runtime + jobs + gatekeeper + assistant contract HTTP + architecture sau số lượng → 101 passed, 9.87 s.
- Toàn backend lần đầu sau đổi prompt → 2 failed, 2869 passed, 36 skipped, 3 xfailed, 36.93 s.
  Hai lỗi thuộc test_behavior_snapshot: payload prompt mới không khớp cassette cũ; nhiều lượt cassetteMiss.
- Backend sau sửa cuối số lượng/giữ thẻ vé, bỏ riêng test_behavior_snapshot.py đã biết cần ghi lại:
  `HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false
  .venv/bin/python -m pytest -q src/backend/tests --ignore=src/backend/tests/unit/agents/test_behavior_snapshot.py`
  → 2871 passed, 36 skipped, 3 xfailed, 35.01 s. Log /tmp/travel-scope-count-backend.log, giữ mã thoát pytest.
  Skipped/xfail không phải pass; không suy ra toàn suite xanh.
- Sau nối scope tiến trình: progress + assistant contract HTTP + gatekeeper → 52 passed, 9.49 s.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → PASS:
  130 schemas, 105 fixtures; CDP 12 schemas/7 fixtures/11 negative checks. Kiểm 10/20, 21 và trần flight.
- `npm run generate:api-types` → PASS, không sửa bundle OpenAPI sinh tự động.
- `npm run build:web` cuối → PASS, Next.js compile + TypeScript + static pages.
- `npm run typecheck` → PASS trước nối scope; build cuối cũng kiểm TypeScript sau nối scope.
- `npm run lint` → 0 errors, 3 warnings có sẵn tại ItineraryMap/useFloatingWidget.
- `npm exec -- vitest run tests/unit/widgetNarration.test.tsx tests/unit/widgetProgress.test.ts
  tests/unit/progressModel.test.ts --maxWorkers=1` cuối → 30 passed, 3 files.
- `npm exec -- playwright test tests/e2e/widget-opening.spec.ts --grep 'ten requested'` cuối → 2 passed, 19.9 s:
  đủ 10 thẻ, xem được thẻ cuối, không tràn ngang, mở xem giải thích bỏ phạm vi cũ/tìm nhiều nơi/mục tiêu 10.
  Ảnh /tmp/travel-ten-recommendations-390.png, /tmp/travel-ten-recommendations-1024.png.
- git diff --check → PASS.
- Lần xin chạy 3 câu qua model OpenAI với dữ liệu giả lập bị automatic approval review từ chối:
  gửi truy vấn/ngữ cảnh ra đích chưa xác nhận, chưa có ủy quyền payload cụ thể. Lệnh không chạy,
  không thử đường khác để vượt chặn. Đã hỏi người dùng cho phép kiểm 3 câu với ngữ cảnh giả lập; đang chờ trả lời.

## Còn lại / rủi ro

- Chưa chạy model thật sau sửa. Kiểm scripted model chứng minh code thực thi đúng quyết định;
  không chứng minh model luôn hiểu câu mở rộng đúng. Chưa đọc trace hội thoại người dùng đã dán.
- Hai kiểm thử snapshot cần ghi cassette mới bằng record và đọc/duyệt diff theo plan D6/G4.
  Không tự đổi baseline hoặc che các lỗi AC đã biết. Việc này không được chứng minh bởi 3 câu model smoke.
- Kiểm browser dùng fixture; chưa chứng minh model thật + Search/Catalog thật qua HTTP/SSE trong hội thoại nhiều lượt.
- Các lỗi D4/D5 khác trong plan orchestrator chưa được coi là hoàn thành bởi task này; Phần B debug vẫn chưa chốt.
