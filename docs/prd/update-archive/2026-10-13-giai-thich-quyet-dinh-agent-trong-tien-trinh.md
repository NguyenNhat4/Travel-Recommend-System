# Agent giải thích quyết định trong tiến trình

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-09; `docs/prd/user-flow.md` §4.2; `docs/prd/architecture.md` §3
- Mã FR/NFR: FR-AGT-01, FR-AGT-06/07, NFR-REL-01; AC-AGT-09

## Lý do

Người dùng phản hồi tiến trình tìm thêm điểm tham quan và khách sạn tại TP. Hồ Chí Minh có vẻ cố định, cần thấy agent hiểu và quyết định gì. Kiểm tra source: `widgetProgressLabels.jobExplanation` ghép câu mẫu theo scope/intent; `widgetProgressView` có câu viết lời tư vấn cố định. Số đếm là dữ kiện từ backend, nhưng các câu này không phải lời giải thích do model viết.

PRD hiện chỉ cho phép mã/số trên SSE. Muốn agent tự giải thích quyết định cần mở rộng nội dung tiến trình, không chỉ thay câu mẫu. Nhánh hiện tại đang triển khai assistant v2, còn v1 giữ cho client cũ; đề xuất ưu tiên v2 và không tự chuyển widget sang v2 trước nghiệm thu.

## Nội dung đề xuất

### `requirements.md` §3, AC-AGT-09

Hiện tại: “SSE chỉ mã/số an toàn, không tên tool/API/query thô, prompt hay suy luận nội bộ.”

Thay bằng: “SSE có mã/số do code tính và lời giải thích ngắn do agent viết cho người dùng ở mỗi vòng quyết định. Lời giải thích nêu cách hiểu yêu cầu, hành động sắp làm và lý do; sau khi có kết quả, nêu điều đã biết, điều còn thiếu và quyết định tìm tiếp hoặc trả lời. Đây là nội dung giải thích công khai được model tạo riêng, không phải suy luận nội bộ, prompt hoặc output thô. Không hiển thị tên tool/API/query thô. Dữ kiện phải khớp quyết định và kết quả đã kiểm của chính lượt.”

Bổ sung nghiệm thu:

- Lượt tìm thêm hai loại sản phẩm diễn giải được hai công việc trong một lời giải thích phù hợp với tin nhắn, không lặp hai câu mẫu như nhau.
- Phát lời giải thích sau khi nhận và kiểm quyết định, trước khi chạy công việc tương ứng. Phân biệt “sẽ tìm” với “đã tìm”. Không giả vờ phát suy nghĩ trong khi model chưa trả kết quả.
- Tìm tiếp, đổi phạm vi, gặp lỗi hoặc dừng vì giới hạn có lời giải thích phù hợp với kết quả và quyết định thật. Thiếu lời giải thích thì chỉ hiện trạng thái công việc; không tạo lời suy nghĩ thay agent.
- Số tìm thấy, bị loại, đủ điều kiện, chọn và hiển thị vẫn do code tính. Agent không được tự tạo số hoặc nhận đã kiểm giá/nguồn trước khi kiểm thực sự xong.
- Mỗi lời giải thích tối đa hai câu, 400 ký tự; không thêm lời gọi model chỉ để viết tiến trình. Thông tin sản phẩm/số liệu cần ref hợp lệ và được render từ nguồn, tương tự câu trả lời cuối; câu không kiểm được bị bỏ.

### `user-flow.md` §4.2, Khung tiến trình

Hiện tại: “Mã/số trên SSE an toàn, không prompt/suy luận nội bộ.”

Thay bằng: “Khung tiến trình hiển thị theo các vòng quyết định và công việc thật. Agent viết lời giải thích ngắn về cách hiểu, việc sắp tra và quyết định sau khi xem kết quả; code hiển thị số đếm và trạng thái thực thi. Không dựng trước chuỗi bước hay thay lời giải thích bằng câu mẫu mang giọng agent. SSE không chứa prompt hoặc suy luận nội bộ. Khi xong vẫn thu gọn để mở xem lại; tiến trình chưa lưu ở server.”

Ví dụ cách hiển thị, chỉ minh họa, không phải transcript thật:

> Mình hiểu “xem thêm” là tìm cả điểm tham quan và khách sạn ở TP. Hồ Chí Minh, giữ những điều kiện bạn đã nêu. Mình sẽ tra thêm trong hai nhóm và đối chiếu với các thẻ đã giới thiệu.
>
> [Kết quả thực thi do code: số tìm thấy, số loại và lý do.]
>
> [Lời agent sau khi có kết quả: đã đủ lựa chọn mới để trả lời, hoặc còn thiếu nhóm nào và vì sao cần tìm tiếp.]

### `architecture.md` §3, Tiến trình

Hiện tại: “SSE chỉ mã/số an toàn, không prompt hay suy luận nội bộ.”

Thay bằng: “SSE có mã/số an toàn do code tính và lời giải thích công khai ngắn trong quyết định có cấu trúc của orc. Kiểm schema, phạm vi lượt, hành động thực thi và refs/facts trước khi phát; không stream raw model tokens, prompt hoặc suy luận nội bộ. Giữ hạn mức model/tool và deadline hiện có.”

## Thay đổi source sau khi chốt

1. Cập nhật ba đoạn PRD ở trên trước; lưu trữ đề xuất sau khi áp dụng.
2. Contract-first: `src/shared/contracts/schemas/assistant-v2.yaml`, fixture `src/shared/mocks/assistant-v2/` và types sinh lại. Thêm lời giải thích có giới hạn, gắn run/vòng quyết định; không đổi semantics sự kiện/số đếm cũ.
3. `src/backend/app/application/itinerary/orc_contracts.py`, `src/backend/app/agents/orc_v2.py`: thêm nội dung giải thích công khai vào cùng quyết định model, kiểm và phát theo vòng thật. Grounding qua `domain/itinerary/orc_guardrails.py` hoặc bộ kiểm tái dùng tương ứng.
4. `src/frontend/src/features/itinerary/widget/widgetV2.ts`, `progressModel.ts`, `widgetProgressView.ts`, `WidgetProgress.tsx`, `src/frontend/src/services/assistantV2Stream.ts`: giữ chuỗi quyết định theo thứ tự, render lời giải thích và công việc thật thay vì ghép v2 vào ba bước cố định.
5. Unit/contract/stream/frontend regression: nhiều vòng, trả lời ngay, thiếu giải thích, lỗi, refs không hợp lệ, hai run, không hiện hoàn tất sớm; kiểm model thật cùng dữ liệu thật để đánh giá câu chữ. Không coi fixture là bằng chứng agent tự giải thích.

Không đổi hành vi tìm/chọn sản phẩm, lưu lịch, lưu trữ tiến trình hay tự triển khai chẩn đoán mức 2. V1 giữ tương thích; chuyển widget sang v2 theo điều kiện nghiệm thu PRD đang có.
