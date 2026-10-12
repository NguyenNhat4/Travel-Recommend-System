# Áp dụng: sở thích là 5 lựa chọn cố định và một ô tự nhập, bỏ AI

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs
- Thay thế: `history/2026-10-12-so-thich-mot-doan-mo-ta.md`, `history/2026-10-12-sua-422-viet-so-thich-bang-ai.md` (phần Viết bằng AI); hoàn tất `history/2026-10-12-de-xuat-so-thich-chip-co-dinh.md`

## Mục tiêu

Người dùng bỏ ô "Mong muốn cho chuyến đi" và nút Viết bằng AI; thay bằng vài lựa chọn cố định và một ô tự nhập thêm. Chốt trong chat 12/10 ("oke chot"): 5 lựa chọn Hồ bơi, Phù hợp trẻ nhỏ, View biển, Có bữa sáng, Spa; ô tự nhập tối đa 150 ký tự. Đề xuất: `docs/prd/update-archive/2026-10-12-so-thich-chip-co-dinh-va-o-tu-nhap.md` (AC-AGT-01; FR-AGT-01, FR-AGT-06).

## File thay đổi

- `docs/prd/requirements.md` (AC-AGT-01), `docs/prd/user-flow.md` (§4.2) — sửa: 5 lựa chọn cố định và ô tự nhập; `docs/prd/architecture.md` (§3) — sửa: bỏ mục Viết sở thích bằng AI.
- `docs/prd/update-archive/2026-10-12-so-thich-chip-co-dinh-va-o-tu-nhap.md` — thêm (chuyển từ `docs/prd/update/`, đã áp dụng).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/langgraph-nodes.md` — sửa: mô tả ô sở thích.
- `src/shared/contracts/openapi.yaml`, `src/shared/contracts/paths/itinerary-agent.yaml`, `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: bỏ `POST /assistant/preferences`, `TripPreferenceRequest`, `TripPreferenceResponse`; giữ `autoOpen`; mô tả `fields.interests`, `interestOptions`; version 1.26.0. `paths/itinerary-agent.yaml` trở về đúng bản HEAD.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại.
- `src/backend/app/application/itinerary/preference_suggestions.py`, `src/backend/app/domain/itinerary/preference_options.py` — xoá.
- `src/backend/app/api/v1/routes/assistant.py`, `src/backend/app/main.py` — sửa: bỏ route và wiring `trip_preferences` (trở về HEAD, trừ version app 1.26.0).
- `src/backend/app/api/v1/schemas/itinerary.py`, `src/backend/app/application/ports/product_query.py`, `src/backend/app/infrastructure/persistence/postgres_catalog.py`, `src/backend/tests/fakes/catalog.py`, `src/backend/app/domain/itinerary/preferences.py` — trở về bản HEAD (bỏ `TripPreferenceRequestModel`, `preference_products`, danh sách tiện ích mở rộng).
- `src/backend/app/agents/steps/conversation.py` — sửa: `interestOptions` là 5 lựa chọn của `preferences.PREFERENCES`.
- `src/backend/tests/unit/api/test_trip_preferences.py`, `src/backend/tests/unit/application/test_trip_preference_suggestions.py` — xoá.
- `src/backend/tests/unit/agents/behavior_snapshot/snapshot.json` — sửa: 22 kịch bản chỉ đổi `interestOptions` (8 → 5 nhãn), làm mới từ cassette, không gọi LLM.
- `src/frontend/src/services/tripPreferences.ts` — xoá.
- `src/frontend/src/components/assistant/TripPreferenceFields.tsx` — sửa: chip cố định + ô tự nhập (maxLength 150), không gọi API.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: tích sẵn lựa chọn đã biết, phần `defaults.interests` ngoài lựa chọn điền vào ô tự nhập; câu xác nhận "… ưu tiên khách sạn có X, Y. <ô tự nhập>".
- `src/frontend/tests/unit/tripDetailsForm.test.tsx` — sửa: test chip, ô tự nhập, không gọi `/assistant/preferences`.

## Quyết định

- 5 lựa chọn là bộ sở thích gốc đã có dữ liệu (`preferences.PREFERENCES`), dùng chung cho mọi điểm đến; không cần endpoint riêng.
- Sở thích đã biết ngoài 5 lựa chọn (ví dụ "ẩm thực") điền sẵn vào ô tự nhập để không mất khi xác nhận.
- So snapshot cũ/mới bỏ qua `interestOptions`: không còn khác biệt nào, nên chỉ làm mới snapshot.

## Kiểm tra

- `validate_contract.py`: PASS (120 schemas).
- Backend unit + architecture + contract: 2788 passed, 2 skipped (trước khi làm mới snapshot: 1 failed `test_each_turn_matches_the_recorded_behavior`, chỉ do `interestOptions`).
- Frontend: `tsc --noEmit` sạch; lint không lỗi; `vitest run` 831/831 passed.
- Chưa kiểm tra tay trên trình duyệt.

## Còn lại / rủi ro

- Thử trên trình duyệt: tích chip, nhập ô tự nhập, xác nhận ra lịch.
- Đề xuất `docs/prd/update/2026-10-12-dong-bo-ac-agt-06-voi-nut-mo-form.md` vẫn chờ chốt.
- Chưa commit theo yêu cầu người dùng.
