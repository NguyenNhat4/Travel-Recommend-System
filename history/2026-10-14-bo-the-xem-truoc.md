# Bỏ thẻ xem trước trong khung tiến trình trợ lý

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs
- Mã FR/NFR: AC-AGT-09 (FR-AGT-01, FR-AGT-06)
- Thay thế: `2026-10-14-de-xuat-bo-the-xem-truoc.md`

## Mục tiêu

Người dùng thấy khối thẻ 2 cột × 3 dòng ("Đã chọn xong, đang viết lời tư vấn") hiện trước câu trả lời, coi là bug và
chốt bỏ hẳn (chat 14/10: "bỏ nhanh vào luôn"). Áp dụng đề xuất
`docs/prd/update-archive/2026-10-14-bo-the-xem-truoc-trong-tien-trinh.md`.

## File thay đổi

- `docs/prd/requirements.md` — sửa AC-AGT-09: không hiện thẻ trước câu trả lời.
- `docs/prd/user-flow.md` — sửa §4 Khung tiến trình: bỏ câu preview.
- `docs/prd/architecture.md` — sửa §3: bỏ dòng preview, "Preview và tool thử lịch" → "Tool thử lịch".
- `docs/prd/update/2026-10-14-bo-the-xem-truoc-trong-tien-trinh.md` → `docs/prd/update-archive/…` — đã áp dụng, lưu trữ
  (file chưa từng được commit nên chuyển bằng `mv`).
- `src/backend/app/agents/orc_v2.py` — sửa: thôi phát sự kiện `preview` sau `plan_itinerary`; bỏ import `card` thừa.
- `src/backend/app/agents/steps/progress.py` — sửa: xoá hàm `preview` và phát `run.preview` sau compose (v1).
- `src/backend/app/api/v1/routes/assistant.py` — sửa: chỉ chuyển `node.activity`.
- `src/backend/tests/unit/agents/test_progress.py` — xoá test preview.
- `src/shared/contracts/paths/itinerary-agent.yaml`, `src/shared/contracts/schemas/itinerary-agent.yaml`,
  `src/shared/contracts/schemas/assistant-v2.yaml` — sửa mô tả: giữ schema cho client cũ, server không còn phát.
- `src/frontend/src/features/itinerary/widget/WidgetProgressPreview.tsx` — xoá.
- `src/frontend/src/context/assistantState.ts` — sửa: bỏ state `preview`/`previewVisible`/`previewAt` và hai action.
- `src/frontend/src/context/AssistantProvider.tsx` — sửa: bỏ xử lý `preview`/`run.preview` và hẹn giờ 5 giây.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: bỏ khối thẻ xem trước.
- `src/frontend/src/features/itinerary/widget/AssistantProgressDiagnostics.tsx` — sửa: bỏ dòng mốc preview.
- `src/frontend/src/services/assistantStream.ts` — sửa: bỏ `run.preview` khỏi union tên sự kiện.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — sửa: bỏ test preview, thêm test bỏ qua `run.preview` của server cũ.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/product.md`,
  `docs/spec/agent/working-context.md` — sửa: bỏ phần preview.
- `history/2026-10-14-de-xuat-bo-the-xem-truoc.md` — thêm dòng "Bị thay thế bởi".

## Quyết định

- Contract giữ schema `EventPreview` (v2) và `AssistantRunPreview`/`run.preview` (v1), chỉ đổi mô tả: không xoá trong
  v1 (AGENTS.md §3). Frontend không còn xử lý sự kiện này nên server cũ có phát cũng bị bỏ qua.
- Giữ "xem trước phương án" (thẻ phương án khác trong câu trả lời) vì không thuộc khung chờ.
- Không sinh lại `api.gen.ts`/`assistant-v2.gen.ts`: chỉ đổi mô tả, không đổi hình dạng.

## Kiểm tra

- `validate_contract.py`: PASS (v2 36 schemas/8 fixtures/14 negative; v1 130 schemas/106 fixtures; CDP 12/7/11).
- Frontend `tsc --noEmit`: pass; `vitest run`: 89 file, 935 passed.
- Backend `pytest src/backend/tests`: 3081 passed, 42 skipped, 3 xfailed, 2 failed —
  `test_search_contract.py::test_contract_declares_every_domain_constant` và
  `test_search_llm_contract.py::test_contract_declares_every_llm_constant` đòi version 1.28.0 trong khi `openapi.yaml`
  đã là 1.29.0 do thay đổi catalog có sẵn trong working tree trước task này; task này không đổi version.
- Chưa kiểm bằng trình duyệt; backend cổng 8000 cần khởi động lại để chạy code mới.

## Còn lại / rủi ro

- Hai test version contract đỏ thuộc thay đổi catalog đang dở (nâng 1.29.0), cần người làm phần đó cập nhật test.
