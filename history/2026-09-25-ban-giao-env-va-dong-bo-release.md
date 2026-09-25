# Bàn giao env/deploy fresh catalog và đồng bộ release-mvp-v1

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs, agent, frontend

## Mục tiêu

Người dùng yêu cầu cung cấp env mới, hướng dẫn bên deploy và lấy cập nhật release-mvp-v1 về nhánh hiện tại. Bộ bàn giao phục vụ FR-CAT-01/03, NFR-SEC-01; không đổi hành vi sản phẩm hay PRD.

## File thay đổi

Thay đổi bàn giao trong task này:

- `src/data_collection/fresh-catalog.env.example` — thêm: cấu hình riêng crawler/monitor, placeholder DB qua tunnel 15432, Cohere/Weaviate và ngân sách Trip 30/10/180.
- `src/data_collection/fresh-catalog-runner.env.example` — thêm: image/path/network phía host, không secret; dùng cho cron và systemd.
- `docs/plan/2026-09-25-ban-giao-fresh-catalog-vm.md` — thêm: build/push, env, chuyển job cũ, full kiểm tra, systemd monitor, cron tick, nghiệm thu và rollback.
- `src/data_collection/README.md` — sửa: liên kết bộ bàn giao.
- `history/2026-09-25-ban-giao-env-va-dong-bo-release.md` — thêm: entry này.

File nhận từ release khi fast-forward (A = thêm, M = sửa):

- `docs/spec/agent/README.md` — nhận nguyên trạng từ release (M).
- `docs/spec/agent/field-review.md` — nhận nguyên trạng từ release (M).
- `docs/spec/agent/langgraph-nodes.md` — nhận nguyên trạng từ release (M).
- `docs/spec/agent/presentation-script.md` — nhận nguyên trạng từ release (M).
- `docs/spec/agent/presentation-slides.html` — nhận nguyên trạng từ release (M).
- `docs/spec/agent/state-fields.md` — nhận nguyên trạng từ release (M).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — nhận nguyên trạng từ release (M).
- `history/2026-09-24-doc-gio-hang-checkout-k1.md` — nhận nguyên trạng từ release (A).
- `history/2026-09-24-form-mo-dau-tro-ly.md` — nhận nguyên trạng từ release (A).
- `history/2026-09-24-go-banner-tro-ly-ai-trang-chi-tiet.md` — nhận nguyên trạng từ release (A).
- `history/2026-09-24-memory-lich-su-hoi-thoai-agent.md` — nhận nguyên trạng từ release (A).
- `history/2026-09-24-noi-vong-dat-cho-goi-y-k1.md` — nhận nguyên trạng từ release (A).
- `history/2026-09-25-merge-release-mvp-v1-vao-feat-agent.md` — nhận nguyên trạng từ release (A).
- `history/2026-09-25-sua-e2e-clarification-theo-ui-moi.md` — nhận nguyên trạng từ release (A).
- `src/backend/app/agents/nodes.py` — nhận nguyên trạng từ release (M).
- `src/backend/app/agents/state.py` — nhận nguyên trạng từ release (M).
- `src/backend/app/agents/steps/classification.py` — nhận nguyên trạng từ release (M).
- `src/backend/app/agents/steps/conversation.py` — nhận nguyên trạng từ release (M).
- `src/backend/app/agents/steps/history.py` — nhận nguyên trạng từ release (A).
- `src/backend/app/agents/steps/prompts.py` — nhận nguyên trạng từ release (M).
- `src/backend/app/agents/steps/tool_planning.py` — nhận nguyên trạng từ release (M).
- `src/backend/tests/unit/agents/test_conversation_history.py` — nhận nguyên trạng từ release (A).
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — nhận nguyên trạng từ release (M).
- `src/frontend/src/components/assistant/AssistantConversation.tsx` — nhận nguyên trạng từ release (M).
- `src/frontend/src/components/assistant/AssistantTripStarter.tsx` — nhận nguyên trạng từ release (A).
- `src/frontend/src/components/assistant/AssistantView.tsx` — nhận nguyên trạng từ release (M).
- `src/frontend/src/components/detail/ProductDetailView.tsx` — nhận nguyên trạng từ release (M).
- `src/frontend/src/services/destinations.ts` — nhận nguyên trạng từ release (A).
- `src/frontend/src/types/api.gen.ts` — nhận nguyên trạng từ release (M).
- `src/frontend/tests/e2e/routes.spec.ts` — nhận nguyên trạng từ release (M).
- `src/frontend/tests/unit/assistantConversationStarter.test.tsx` — nhận nguyên trạng từ release (A).
- `src/frontend/tests/unit/assistantTripStarter.test.tsx` — nhận nguyên trạng từ release (A).
- `src/frontend/tests/unit/destinationsService.test.ts` — nhận nguyên trạng từ release (A).

Các thay đổi monitor local có trước đã được giữ nguyên (gồm ba file xóa đã staged); xem `history/2026-09-25-hoan-thien-monitor-fresh-catalog.md` để có danh sách và kiểm thử đầy đủ. Chỉ README được bổ sung liên kết bởi task hiện tại.

## Quyết định

- Fetch chính xác `origin/release-mvp-v1`, nhận 10 commit chưa có trong nhánh. Fast-forward từ `287e427` tới `0a9bc66`; không tạo merge conflict hay sửa nội dung upstream.
- Lưu toàn bộ thay đổi local bằng stash có include-untracked, merge --ff-only, apply --index. Kiểm tra SHA256 từng file có trước khớp byte-for-byte sau khôi phục; trạng thái staged của ba file xóa được giữ. Không bỏ thay đổi của người dùng.
- Release đã nhận PR #21 từ test/newcrawl và PR #19 từ feat/agent. Delta thực tế là memory hội thoại, form mở đầu trợ lý, gỡ banner trang chi tiết, chỉnh E2E và types sinh lại. K1 xuất hiện trong lịch sử nhưng phần trùng đã bị thay bằng booking release (theo history merge feat-agent); không mô tả nó như một implementation mới độc lập.
- Hai file env tách biệt: Docker đọc file secret KEY=value không nháy; host shell/systemd đọc runner env không secret. Không đọc/chép secret đang có trên máy người dùng.
- Dùng host network và tunnel DB 127.0.0.1:15432 theo kế hoạch CI/CD hiện hành; không thêm scheduler thứ hai, không khởi động hay reset DB VM.
- Cron mới vẫn fresh-run tick; installer CI cũ vẫn sinh run. Tài liệu yêu cầu đội deploy xử lý bước cài cron cũ trước lần deploy backend tiếp theo, không tự thay workflow trong task bàn giao này.
- Tài liệu cảnh báo thay đổi monitor/bộ bàn giao còn local, phải commit/push trước build từ checkout remote. Không push hoặc triển khai VM trong task này.

## Kiểm tra

- `git fetch origin release-mvp-v1`: thành công; `git rev-list --left-right --count HEAD...origin/release-mvp-v1` sau cập nhật: `0 0`.
- SHA256 toàn bộ file chỉnh sửa/untracked trước merge: khớp sau khôi phục.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/dangkhoi/miniconda3/envs/vsf/bin/python -m pytest -q -p no:cacheprovider src/data_collection/tests`: **330 passed, 3 skipped**.
- Backend test ban đầu dùng Python local 3.10 không collect được do thiếu `enum.StrEnum`; chuyển sang image backend Python phù hợp, mount source read-only, không mount env secret. `test_conversation_history.py` + `test_recsys_refresher.py`: **10 passed**.
- `src/shared/contracts/tests/validate_contract.py`: PASS (83 schema, 62 fixture; CDP clone 12 schema, 7 fixture).
- `bash -n` mọi block bash trong tài liệu và runner env mẫu: PASS.
- `systemd-analyze verify --man=no` unit mẫu (thay User/ExecStart bằng đường dẫn tồn tại local, chỉ verify không start): PASS.
- Docker đọc env mẫu, resolve cấu hình fresh và index: PASS; không kết nối nguồn/DB/Weaviate.
- `git diff --check`: PASS.
- Không chạy lại frontend/E2E tại đây: máy hiện tại chưa có npm/node_modules. Frontend nhận nguyên trạng từ release; kết quả frontend của tác giả upstream nằm trong các entry history mới, không tính là kiểm thử thực hiện ở task này.

## Còn lại / rủi ro

- Chưa commit/push phần monitor và bàn giao, chưa build/push image cho tag triển khai, chưa thay cron/service/firewall VM.
- Đội deploy điền secret, image/tag và DEPLOY_USER thật; dùng cùng volume/env cho cron và monitor. Cấu hình saved trong volume vẫn ưu tiên hơn env.
- Chưa xác minh runtime hoặc quota Trip trên VM. Chạy full và kiểm tra DB/index/log theo mục nghiệm thu trước bật lịch.
- Memory Agent upstream là process-local; restart mất lịch sử. Không triển khai adapter persistence trong task này.
