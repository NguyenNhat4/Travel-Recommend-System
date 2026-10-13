# Số lượng gợi ý theo yêu cầu của người dùng

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13 ("Chốt số lượng theo yêu cầu, trần 20")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4, §3 AC-AGT-06; `docs/prd/architecture.md` §3
- Mã FR/NFR: FR-AGT-06, NFR-REL-01

## Lý do

Người dùng yêu cầu "giới thiệu 10 chỗ khác đi" nhưng trợ lý chỉ trả 3 thẻ. Đây là giới hạn có chủ ý trong PRD,
được lặp ở prompt, bộ gác cổng và contract; sửa riêng prompt không giải quyết được.
Số lượng nên là yêu cầu của lượt chat, còn giới hạn lời gọi và grounding tiếp tục do code kiểm.

## Nội dung đề xuất

### `requirements.md` §1.4, FR-AGT-06

Giữ nội dung hiện hành; bổ sung:

> Khi người dùng nêu số lượng gợi ý, trợ lý tìm và giới thiệu theo số lượng đó trong giới hạn AC-AGT-06.
> Nếu thiếu sản phẩm hợp lệ hoặc hết ngân sách thực thi, trả số thực tìm được và nói rõ phần còn thiếu.

### `requirements.md` §3, AC-AGT-06

Hiện tại:

> Mỗi lượt tối đa **3 điểm tham quan/tour**, **2 khách sạn khi hỏi chung, 4 khi hỏi riêng chỗ ở**; LLM được chọn ít hơn.

Thay bằng:

> Khi người dùng không nêu số lượng, giữ mức gợi ý hiện tại: tối đa 3 điểm tham quan/tour,
> 2 khách sạn khi hỏi chung hoặc 4 khi hỏi riêng chỗ ở; LLM được chọn ít hơn.
> Khi người dùng nêu số lượng, dùng số lượng đã hiểu thay cho mức mặc định của nhóm được hỏi;
> tối đa 20 thẻ trong một lượt. Yêu cầu vượt 20 thì trả tối đa 20 và nói rõ giới hạn.
> Ví dụ "giới thiệu 10 chỗ khác" trả 10 điểm tham quan/tour chưa xem khi có đủ sản phẩm hợp lệ và ngân sách thực thi.
> Nếu chỉ tìm được ít hơn, trả số thực tìm được và giải thích thiếu dữ liệu hay đã hết ngân sách thực thi;
> không lấy sản phẩm trùng hoặc ngoài điều kiện để điền đủ số. Các giới hạn của lịch trình và logic chọn vé giữ nguyên.

Giữ tối đa 3 việc/vòng, 3 vòng thực thi/lượt, trần 10 lời gọi công cụ và kiểm dữ liệu trong chính lượt đó.
"10 chỗ khác" sau danh sách nhiều thành phố vẫn tìm trong phạm vi nhiều thành phố; mở rộng phạm vi là sửa lỗi
tuân thủ yêu cầu hiện hành, không phụ thuộc việc chốt thay đổi số thẻ này.

### `architecture.md` §3, gác cổng trước finalize

Hiện tại:

> Tối đa 3 điểm tham quan/tour, 2 khách sạn khi hỏi chung hoặc 4 khi hỏi riêng chỗ ở.

Thay bằng:

> Số thẻ theo AC-AGT-06: giữ mức mặc định khi không nêu số lượng; số lượng người dùng yêu cầu được orchestrator
> trích có cấu trúc, code kiểm và dùng cho cả tìm ứng viên lẫn chọn thẻ. Tổng tối đa 20 thẻ/lượt.
> Tiếp tục dùng bản rút gọn và con trỏ `continue_from` để lấy thêm ứng viên trong ngân sách;
> không tăng vô hạn số lời gọi hay gửi toàn catalog cho LLM để đủ số thẻ.

## Thay đổi source sau khi chốt

- `src/shared/contracts/schemas/itinerary-agent.yaml`: nới giới hạn searchResults của lượt khám phá để nhận 10–20 thẻ;
  không tăng số hoạt động của lịch đã xếp. Cập nhật mô tả/version ở `openapi.yaml` trước source;
  thêm fixture và kiểm contract, sinh lại `src/frontend/src/types/api.gen.ts`.
- `src/backend/app/agents/models.py`, `steps/prompts.py`: số lượng có cấu trúc do LLM hiểu, không regex tin nhắn.
- `src/backend/app/agents/steps/jobs.py`, `steps/orchestration.py`: truyền số lượng qua các vòng/continuation;
  yêu cầu thêm ứng viên từ bản rút gọn khi cần; hết dữ liệu/budget thì trả một phần và nói rõ.
- `src/backend/app/domain/itinerary/gatekeeper.py`: bỏ trần cố định cho nhóm có số lượng được yêu cầu;
  vẫn kiểm từng mã, phạm vi, trùng, dữ liệu mới và giới hạn tổng 20.
- Kiểm đường hiển thị `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, danh sách thẻ trên màn hẹp;
  tiến trình ghi số thực chọn và lý do thiếu, không số do LLM đoán.
- Cập nhật spec khám phá và plan orchestrator; kiểm hồi quy chuỗi: khám phá nhiều thành phố → 10 chỗ khác →
  không chỉ thành phố cuối → hỏi lại một thẻ. Kiểm cả đủ 10, thiếu 10, vượt 20, continuation và tool lỗi.
