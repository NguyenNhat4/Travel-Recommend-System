# Form qua nút gợi mở và sở thích từ thuộc tính catalog

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-12 (xác nhận trong chat: sở thích gồm tham quan/tour/combo, sau đó “ok”)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-01, AC-AGT-04; `docs/prd/user-flow.md` §4.2; `docs/prd/architecture.md` §3
- Mã FR/NFR: FR-AGT-01, FR-AGT-03, FR-AGT-06, FR-SRC-03, NFR-REL-01

## Lý do

Người dùng làm rõ trong chat: form dùng lại các trường hiện có, chỉ mở khi bấm nút ở phần gợi mở sau câu trả lời. Sở thích cố định không tận dụng đủ thuộc tính sản phẩm; cần để LLM tạo gợi ý từ danh sách thuộc tính có dữ liệu và cho người dùng tinh chỉnh. Nhóm thẻ khách sạn cần được đề xuất để người dùng duyệt trước khi triển khai.

Code hiện tại: `TripDetailsForm.tsx` chỉ có nút chọn sở thích, chưa có ô tự điền hay nút LLM; `preferences.py` giới hạn năm sở thích. `WidgetChat.tsx` dựng form ngay khi response có `clarificationForm`. PRD cập nhật ngày 12/10 vẫn yêu cầu form tự hiện và gợi ý trong năm sở thích.

## Nội dung đề xuất

### 1. AC-AGT-01 và user-flow §4.2 — mở form qua nút

Hiện tại: "Câu hỏi gộp này kèm luôn form thông tin chuyến đi điền sẵn"; form hiện ở mỗi lượt khi còn thiếu trường bắt buộc.

Thay bằng: câu trả lời trong luồng lập lịch có lời gợi mở và nút **Điền thông tin chuyến đi** khi cần làm rõ. Bấm nút mở form hiện có với thông tin đã biết; không tạo một lượt LLM chỉ để mở form. Người dùng vẫn trả lời bằng chat được. Yêu cầu lập lịch đã đủ thông tin tiếp tục tạo lịch ngay. Người dùng trực tiếp xin form thì mở form ngay. Xác nhận form vẫn gửi yêu cầu hoàn chỉnh theo cơ chế hiện có.

### 2. AC-AGT-01 và architecture §3 — sở thích linh hoạt theo dữ liệu

Hiện tại: ô chỉ liệt kê sở thích "trong năm sở thích trên"; LLM chọn tối đa ba nhãn từ danh sách đó.

Thay bằng: hệ thống tổng hợp thuộc tính có ý nghĩa với nhu cầu tìm kiếm từ catalog đang phục vụ; phạm vi gồm nơi ở, tham quan/tour và combo, theo điểm đến đang chọn; UI phân nhóm rõ. Bao gồm thuộc tính khách sạn và thuộc tính hạng phòng có liên quan, phân biệt tiện ích cấp khách sạn với tiện ích chỉ ở một hạng phòng. Không đưa thuộc tính kỹ thuật như mã nội bộ hay thời điểm thu thập vào lựa chọn người dùng.

Nút **Tạo sở thích bằng AI** dùng danh sách thuộc tính có dữ liệu, số khách sạn ghi nhận và thông tin chuyến đi để tạo gợi ý ưu tiên dễ đọc. Người dùng được thêm, bỏ, sửa và tự điền trước khi xác nhận; yêu cầu tự điền phải được giữ trong câu gửi và dùng cho Search. Nhãn/thuộc tính do LLM gợi ý phải đối chiếu với dữ liệu; không biến "có bữa sáng" thành "bữa sáng miễn phí", không suy ra "yên tĩnh" chỉ từ địa chỉ. Không có dữ liệu thì không tự tạo lựa chọn rồi trình bày như một thuộc tính đã xác minh. Gợi ý chỉ là ưu tiên; điều kiện người dùng nói rõ bắt buộc vẫn theo luật hiện có. LLM lỗi hoặc quá giờ thì form và ô tự điền vẫn dùng được.

Phạm vi đã chốt gồm cả nơi ở, tham quan/tour và combo. Thuộc tính có dữ liệu (tiện ích, loại trải nghiệm, thành phần gói) được tổng hợp và phân nhóm, không giới hạn năm nhãn. Gợi ý và nội dung tinh chỉnh được đưa vào câu Search đúng loại dịch vụ; không mặc định yêu cầu đặt combo nếu người dùng chỉ đánh dấu sở thích combo.

### 3. AC-AGT-04 — nhóm phương án khách sạn đề xuất để duyệt

PRD hiện tại: phương án so tiền và quãng đường, có nhãn tiêu chí và tổng tiền/km; chưa chốt các nhóm dưới đây.

Đề xuất bốn nhóm chính, trong các phương án hợp lệ đã tìm được cho chuyến. Người dùng yêu cầu bổ sung nhóm cao cấp/được yêu thích trong chat ngày 12/10:

- **Tiết kiệm nhất:** tiền lưu trú toàn chuyến thấp nhất, tính đủ đêm và phòng cần cho đoàn.
- **Ít di chuyển nhất:** tổng khoảng cách ước tính của phương án thấp nhất, có đủ toạ độ để so.
- **Cân bằng chi phí và di chuyển:** ưu tiên trong ngân sách; với mức khoảng cách tương đương theo luật hiện có, chọn phương án rẻ hơn. Cần kiểm chứng nhãn phù hợp kết quả, không mặc định nhãn này là tốt nhất.
- **Cao cấp, được yêu thích:** một phương án riêng khi có ứng viên phù hợp, không chỉ thêm khi người dùng chủ động yêu cầu hạng sao. Đề xuất ưu tiên khách sạn 4–5 sao có điểm đánh giá tốt và dữ liệu số lượt đánh giá; hiển thị cả hạng sao, điểm và số lượt để người dùng hiểu căn cứ. Chi tiết triển khai: hạng sao từ 4, điểm từ 4,5/5 và ít nhất 50 lượt đánh giá (cùng ngưỡng bằng chứng nhãn combo hiện hành); xếp theo điểm đánh giá rồi số lượt, hạng sao và giá để phá hoà. Không đủ đánh giá thì chỉ ghi “Cao cấp”. Nếu phương án vượt ngân sách thì ghi rõ, không âm thầm thay phương án đang chọn. Không gắn nhãn tuyệt đối "được yêu thích nhất" chỉ từ hạng sao hoặc giá cao.

Số sao không phải điểm đánh giá. Một phương án thắng nhiều tiêu chí thì dùng một thẻ với nhiều nhãn, không tạo thẻ trùng. Không bắt buộc đủ bốn thẻ khi không có các phương án khác biệt hoặc thiếu dữ liệu để chứng minh tiêu chí. Phạm vi so sánh phải được nói rõ là trong các phương án tìm được, không khẳng định rẻ nhất toàn điểm đến.

Mỗi thẻ có tiền lưu trú toàn chuyến, tổng tiền lịch trình và tổng km ước tính với nhãn rõ ràng; chênh lệch chỉ là dòng phụ. Km hiện tại tính từ toạ độ bằng đường chim bay, không trình bày là quãng đường ô tô thực tế.

### 4. Combo

Người dùng cho phép sáng tạo về hình thức: ảnh lớn, phân cấp nổi bật, màu nền/viền riêng, nút Đặt ngay rõ ràng. Dùng nhãn theo dữ liệu đã được PRD quy định ngày 12/10; không tự khẳng định "tốt nhất" hay "được yêu thích nhất" thiếu căn cứ. Phần này không cần đổi PRD nếu giữ hành vi và tiêu chí nhãn hiện hành.

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md`, `docs/prd/user-flow.md`, `docs/prd/architecture.md` — cập nhật các đoạn tương ứng trước.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, `useFloatingWidget.ts` — mở form qua nút gợi mở.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sở thích linh hoạt, gợi ý LLM, giữ nội dung tinh chỉnh.
- `src/shared/contracts/paths/itinerary-agent.yaml`, `schemas/itinerary-agent.yaml` — contract trước nếu cần dữ liệu/nút/endpoint mới.
- `src/backend/app/domain/itinerary/preferences.py`, `src/backend/app/agents/steps/conversation.py`, phần application liên quan — dùng thuộc tính đã tổng hợp cho gợi ý và Search.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx`, phần tính phương án trong `src/backend/app/domain/itinerary/routing.py` — nhóm/nhãn theo tiêu chí đã duyệt.
- Spec và test thuộc phạm vi cập nhật trong từng phần triển khai; không đổi DDL chỉ để thêm lựa chọn sở thích.

UI phân biệt nhãn loại với trạng thái Đang chọn/Đang xem trước; mỗi loại có câu giải thích và số tuyệt đối. Người dùng đã chốt phạm vi trong chat; cập nhật PRD trước source.
