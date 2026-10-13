# Sở thích trong form: một đoạn mô tả ngắn thay cho nhóm và chip

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-12 (chat: "chot", gồm giới hạn 300 ký tự)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-01; `docs/prd/user-flow.md` §4.2 (Form thông tin chuyến đi); `docs/prd/architecture.md` §3 (Gợi ý sở thích bằng AI)
- Mã FR/NFR: FR-AGT-01, FR-AGT-06, FR-SRC-03, NFR-REL-01

## Lý do

Bản đã triển khai sáng 12/10 hiện quá nhiều thứ trong form: ba nhóm Nơi ở / Tham quan–Tour / Combo, mỗi nhóm một hàng chip kèm số sản phẩm và một ô chữ. Người dùng muốn gọn hơn: một ô duy nhất, bấm nút thì AI viết sẵn một đoạn ngắn mô tả mong muốn để Search tìm tốt hơn; người dùng sửa đoạn đó hoặc tự viết.

## Nội dung đề xuất

AC-AGT-01, phần sở thích. Hiện tại:

> Sở thích phân nhóm **Nơi ở**, **Tham quan / Tour**, **Combo**, tổng hợp thuộc tính có ý nghĩa từ catalog đang phục vụ tại điểm đến, phân biệt tiện ích khách sạn và hạng phòng. Không giới hạn năm nhãn cố định. Có ô tự điền và nút **Tạo sở thích bằng AI**: LLM nhận nhãn/thuộc tính có dữ liệu cùng thông tin chuyến, tạo bộ gợi ý; code kiểm nhãn thuộc danh sách. Người dùng thêm, bỏ, sửa trước xác nhận; nội dung tinh chỉnh được giữ và đưa vào Search đúng loại.

Thay bằng:

> Sở thích là **một ô văn bản** (không bắt buộc, tối đa 300 ký tự), không chia nhóm, không có chip. Nút **Viết bằng AI** tạo một đoạn 1–3 câu mô tả mong muốn cho chuyến đi (nơi ở, hoạt động, nhịp đi), dựa trên thông tin chuyến và các thuộc tính có dữ liệu trong catalog tại điểm đến; chỉ nhắc thuộc tính catalog có ghi nhận, không hứa điều dữ liệu không nói (ví dụ không viết "bữa sáng miễn phí" khi chỉ ghi có bữa sáng). Đoạn được điền vào ô; người dùng sửa, xoá hoặc tự viết. Bấm lại thì viết đoạn mới thay đoạn cũ. Xác nhận form thì đoạn văn đi trong câu yêu cầu; bước hiểu yêu cầu (LLM) đọc nó như mọi tin nhắn và ghi sở thích để Search dùng. LLM lỗi hoặc quá giờ thì ô vẫn tự viết được.

Các phần còn lại của AC-AGT-01 (nút mở form, trường, giới hạn, sở thích là ưu tiên mềm, không loại hết khách sạn, sở thích combo không tự thêm combo) giữ nguyên. User-flow §4.2 và architecture §3 sửa câu tương ứng theo đoạn trên.

## Thay đổi source sau khi chốt

- Contract (`schemas/itinerary-agent.yaml`, `paths/itinerary-agent.yaml`): `POST /assistant/preferences` trả `{text, status}`; bỏ `GET /assistant/preferences` và `TripPreferenceOption`, vì form không còn hiện danh sách. Các schema này mới thêm hôm nay, chưa phát hành.
- Backend: `application/itinerary/preference_suggestions.py` cho LLM viết đoạn văn từ danh sách thuộc tính của `domain/itinerary/preference_options.py`. `agents/steps/classification.py` bỏ đoạn regex tách `sở thích ưu tiên:`; bỏ phần tách theo tiền tố nhóm ở `domain/itinerary/search_hints.py` và `preferences.py`.
- Frontend: `components/assistant/TripPreferenceFields.tsx` còn một textarea và nút Viết bằng AI; `TripDetailsForm.tsx` gửi đoạn văn trong câu xác nhận; `services/tripPreferences.ts` bỏ hàm liệt kê.
- Test tương ứng ở `src/backend/tests/unit/{api,application}/test_trip_preference*.py`, `src/frontend/tests/unit/tripDetailsForm.test.tsx`.
