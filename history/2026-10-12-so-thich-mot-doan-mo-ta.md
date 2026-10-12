# Áp dụng: sở thích trong form là một đoạn mô tả, nút Viết bằng AI

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs
- Thay thế: phần sở thích 3 nhóm/chip trong `history/2026-10-12-trien-khai-gop-y-widget-tro-ly.md`; hoàn tất `history/2026-10-12-de-xuat-so-thich-mot-doan-mo-ta.md`
- Bị thay thế bởi: `history/2026-10-12-so-thich-chip-co-dinh.md`

## Mục tiêu

Form hiện quá nhiều thứ. Người dùng chốt (chat "chot", 12/10): ô sở thích chỉ còn một đoạn văn tối đa 300 ký tự; bấm **Viết bằng AI** thì AI viết đoạn ngắn mô tả mong muốn để Search tốt hơn; người dùng sửa hoặc tự viết. Đề xuất: `docs/prd/update-archive/2026-10-12-so-thich-mot-doan-mo-ta.md` (AC-AGT-01; FR-AGT-01, FR-AGT-06, FR-SRC-03).

## File thay đổi

- `docs/prd/requirements.md` (AC-AGT-01), `docs/prd/user-flow.md` (§4.2), `docs/prd/architecture.md` (§3) — sửa: sở thích là một đoạn văn, nút Viết bằng AI.
- `docs/prd/update-archive/2026-10-12-so-thich-mot-doan-mo-ta.md` — thêm (chuyển từ `docs/prd/update/`, đã áp dụng).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/langgraph-nodes.md` — sửa: mô tả ô sở thích mới.
- `src/shared/contracts/openapi.yaml` — sửa: version 1.26.0, bỏ `TripPreferenceOption`.
- `src/shared/contracts/paths/itinerary-agent.yaml` — sửa: bỏ `GET /assistant/preferences`; POST trả đoạn văn.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: `TripPreferenceResponse {text ≤ 300, status}`; mô tả `fields.interests`, `autoOpen`, `interestOptions` theo 1.26.0.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại.
- `src/backend/app/application/itinerary/preference_suggestions.py` — sửa: LLM viết đoạn văn từ thông tin chuyến và tối đa 40 thuộc tính có dữ liệu tại điểm đến; code gộp khoảng trắng, cắt ở ranh giới từ ≤ 300; lỗi catalog/LLM/quá giờ/rỗng → `unavailable`.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: bỏ route GET; đổi câu lỗi.
- `src/backend/app/main.py` — sửa: version app 1.26.0.
- `src/backend/app/agents/steps/classification.py`, `src/backend/app/domain/itinerary/search_hints.py` — sửa: trả về bản HEAD (bỏ regex tách "sở thích ưu tiên:" và tách theo tiền tố nhóm).
- `src/backend/app/domain/itinerary/preferences.py` — sửa: bỏ xử lý tiền tố nhóm; giữ danh sách tiện ích mở rộng để câu tự do vẫn nhận ra ưu tiên mềm.
- `src/frontend/src/components/assistant/TripPreferenceFields.tsx` — sửa: một textarea (maxLength 300, bộ đếm) và nút Viết bằng AI.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: điền sẵn từ `defaults.interests`; câu xác nhận thêm "Mong muốn (ưu tiên, không bắt buộc): …".
- `src/frontend/src/services/tripPreferences.ts` — sửa: chỉ còn `suggestTripPreferences`.
- `src/backend/tests/unit/api/test_trip_preferences.py`, `src/backend/tests/unit/application/test_trip_preference_suggestions.py`, `src/frontend/tests/unit/tripDetailsForm.test.tsx` — sửa: theo hành vi mới.
- `src/backend/tests/contract/test_search_contract.py`, `src/backend/tests/contract/test_search_llm_contract.py` — sửa: version 1.26.0.

## Quyết định

- Đoạn văn đi trong câu xác nhận để `extract` (LLM) đọc như mọi tin nhắn, thay cho regex tách theo nhóm; `_soft_preferences` vẫn nhận tiện ích trong câu và giữ chúng là ưu tiên mềm.
- Prompt cấm nhắc lại điểm đến, số ngày, số người, ngân sách: lần thử đầu với LLM thật lặp các thông tin này, dễ mâu thuẫn khi người dùng sửa form sau khi bấm nút.
- Contract lên 1.26.0: endpoint, `autoOpen` (Codex thêm chưa tăng version) và `TripPreferenceResponse` mới.
- Vẫn gửi `clarificationForm.interestOptions` (trường tuỳ chọn có từ 1.24.0) để không đổi snapshot; Web không hiện nữa.

## Kiểm tra

- `validate_contract.py`: PASS (122 schemas).
- Backend unit + architecture + contract: 2795 passed, 2 skipped (lần đầu 1 failed do test so version 1.25.0, đã sửa).
- Frontend: `tsc --noEmit` sạch; lint 0 lỗi (3 cảnh báo có sẵn); `vitest run` 833/833 passed.
- Gọi thật (LLM + catalog local, ITINERARY_DATA_MODE=inprocess): Đà Nẵng/Hà Nội/Phú Quốc đều `ready`, 118–202 ký tự, chỉ nhắc tiện ích có trong catalog.
- Chưa kiểm tra tay trên trình duyệt.

## Còn lại / rủi ro

- Thử trên trình duyệt: mở form, Viết bằng AI, sửa đoạn văn, xác nhận ra lịch có dùng sở thích.
- Đề xuất `docs/prd/update/2026-10-12-dong-bo-ac-agt-06-voi-nut-mo-form.md` vẫn chờ chốt.
- Chưa commit theo yêu cầu người dùng.
