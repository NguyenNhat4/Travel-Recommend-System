# Sở thích trong form: vài lựa chọn cố định và một ô tự nhập, bỏ AI

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-12 (chat: "oke chot", 5 lựa chọn và ô 150 ký tự)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-01; `docs/prd/user-flow.md` §4.2 (Form thông tin chuyến đi); `docs/prd/architecture.md` §3 (Viết sở thích bằng AI)
- Mã FR/NFR: FR-AGT-01, FR-AGT-06

## Lý do

Sau khi dùng thử, người dùng muốn bỏ ô "Mong muốn cho chuyến đi" cùng nút Viết bằng AI (chốt sáng 12/10, `update-archive/2026-10-12-so-thich-mot-doan-mo-ta.md`). Thay vào đó là vài lựa chọn bấm nhanh và một ô để tự nhập thêm khi cần (trả lời trong chat 12/10: "vài cái cố định và 1 box để họ tự nhập thêm", "bỏ hẳn" nút AI).

## Nội dung đề xuất

AC-AGT-01, phần sở thích. Hiện tại:

> Sở thích là **một ô văn bản** (không bắt buộc, tối đa 300 ký tự), không chia nhóm, không có chip. Nút **Viết bằng AI** tạo đoạn 1–3 câu …

Thay bằng:

> Sở thích (không bắt buộc) gồm **5 lựa chọn cố định** bấm chọn nhiều — Hồ bơi, Phù hợp trẻ nhỏ, View biển, Có bữa sáng, Spa — và **một ô tự nhập** ngắn (tối đa 150 ký tự) cho mong muốn khác. Lựa chọn đã biết từ hội thoại được tích sẵn; mong muốn khác đã biết được điền sẵn vào ô. Không có nút AI, không gọi LLM khi mở hay điền form. Xác nhận form thì lựa chọn đi trong câu yêu cầu dưới dạng "ưu tiên khách sạn có …", nội dung ô tự nhập đi sau đó; bước hiểu yêu cầu đọc như mọi tin nhắn. Sở thích là ưu tiên mềm.

User-flow §4.2 sửa câu tương ứng. Architecture §3 bỏ mục "Viết sở thích bằng AI".

## Thay đổi source sau khi chốt

- Contract: bỏ `POST /assistant/preferences`, `TripPreferenceRequest`, `TripPreferenceResponse` (thêm hôm nay, chưa phát hành); giữ `autoOpen`; `clarificationForm.interestOptions` là 5 lựa chọn cố định; version giữ 1.26.0.
- Backend: xoá `application/itinerary/preference_suggestions.py`, route và wiring trong `api/v1/routes/assistant.py`, `api/v1/schemas/itinerary.py`, `main.py`; bỏ `preference_products` khỏi port/adapter/fake nếu không còn dùng; `agents/steps/conversation.py` gửi đúng 5 lựa chọn cố định. `domain/itinerary/preference_options.py` chỉ giữ bảng nhãn tiện ích nếu `preferences.py` còn dùng.
- Frontend: `TripPreferenceFields.tsx` thành chip + ô tự nhập; xoá `services/tripPreferences.ts`; `TripDetailsForm.tsx` ghép câu xác nhận như trên.
- Test, spec (`hop-dong-tich-hop-itinerary-assistant.md`, `agent/langgraph-nodes.md`) cập nhật theo.
