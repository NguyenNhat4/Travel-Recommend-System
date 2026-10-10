# Khách sạn cho đoàn đông: tìm theo số khách một phòng, tính tiền theo số phòng

- Ngày: 2026-10-09
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-09 (chốt nội dung chính; hai điểm mở giữ như mục "Nội dung đề xuất")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-01), §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-01, FR-AGT-04, FR-BKG-08 (trần 9 phòng một mục)

## Lý do

Lượt "bao nhieu cungx dudoc" (LangSmith project `nhat-10-7`, 09/10/2026, 7 ngày Phú Quốc, 10 người lớn), lịch chỉ có
một khách sạn. Nguyên nhân:

- Agent gửi cả đoàn làm `travelContext.guests = {adults: 10}` khi search khách sạn. Contract hiểu `guests` là sức chứa
  của **một** phòng (`minOccupancy = adults + children`), nên engine loại mọi khách sạn có phòng chứa dưới 10 người.
  Kết quả: `total: 0`, chỉ còn 2 khách sạn đến từ Recommendation (không lọc số khách).
- Catalog local (09/10/2026): 9.487/9.854 hạng phòng có `maxOccupancy`; trong 2.442 khách sạn biết sức chứa, trung vị
  của phòng lớn nhất là **2 người**. Đoàn từ 3 người trở lên đã bị lọc mất phần lớn khách sạn.
- Tổng tiền tính khách sạn như một phòng (`giá × số đêm`), nên đoàn 10 người được báo giá như đoàn 2 người
  (đang là điểm ⚠️ chờ xác nhận ở `docs/spec/agent/nghiep-vu/xep-lich.md`, mục Edge case).

Không muốn cố định "bao nhiêu người một phòng" trong code. Đề xuất lấy số phòng từ chính dữ liệu giá của khách sạn:
2.728/2.782 khách sạn có `attributes.priceAdults` (số người lớn mà `unitPrice` một đêm đã gồm, hiện đều là 2).

## Nội dung đề xuất

### FR-AGT-01 — thêm một gạch đầu dòng

> Khi tìm khách sạn cho lịch trình, trợ lý lọc theo số khách của **một phòng**, không theo cả đoàn: số khách gửi cho
> Search là số khách tối thiểu mỗi phòng để cả đoàn ở vừa tối đa 9 phòng (FR-BKG-08), tức `ceil(tổng khách / 9)`.
> Đoàn đến 9 người thì không loại khách sạn nào vì sức chứa phòng.

### AC-AGT-04 — thêm vào phần tính tiền

> Tiền khách sạn trong tổng = giá một đêm × số đêm × **số phòng**. Số phòng của từng khách sạn =
> `ceil(số người lớn / priceAdults)`, trong đó `priceAdults` là số người lớn mà giá niêm yết của khách sạn đó đã gồm;
> trẻ em ở cùng phòng người lớn, không tính thêm phòng. Khách sạn cần quá 9 phòng thì không chọn. Khách sạn thiếu
> `priceAdults` thì tính 1 phòng và có cảnh báo "giá chưa tính đủ số phòng". Mục "Nơi nghỉ" và thẻ phương án ghi số
> phòng (ví dụ "5 phòng") khi từ 2 phòng trở lên. So sánh ngân sách và chênh tiền giữa các phương án dùng tổng đã nhân số phòng.

## Điểm cần chốt

1. **Lọc search theo `ceil(tổng/9)`.** Với đoàn 10 người, gửi 2, nên khách sạn có phòng 2 người vẫn được giữ. Đánh đổi:
   gia đình 2 người lớn + 2 trẻ em giờ gửi 1 thay vì 4, nên khách sạn chỉ có phòng đôi cũng lọt, và tiền vẫn tính
   1 phòng (trẻ em không tính phòng). Nếu muốn giữ lọc chặt cho gia đình nhỏ thì chọn thêm: đoàn ≤ 9 người gửi nguyên
   như hiện tại, chỉ đoàn > 9 mới chia.
2. **Trẻ em không tính phòng.** Khớp với cách giá niêm yết (theo người lớn), nhưng có thể vượt sức chứa thật của phòng.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/steps/tool_planning.py` — `travelContext.guests` của search khách sạn theo số khách một phòng.
- `src/backend/app/domain/itinerary/planning.py` — `_known_cost` nhân số phòng cho khách sạn; loại khách sạn cần quá
  9 phòng; hàm số phòng thuần (dùng `domain/booking/party.MAX_ROOMS`).
- Lời diễn giải và widget: hiện số phòng ở mục "Nơi nghỉ" và thẻ phương án (`agents/steps/narration.py`,
  `src/frontend/src/features/itinerary/widget/`). Response hiện chưa có trường số phòng: cần thêm field additive
  vào fragment OpenAPI của assistant trước (contract minor).
- `docs/spec/agent/nghiep-vu/tim-ung-vien.md`, `xep-lich.md` (bỏ điểm ⚠️ số phòng),
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Unit test cho hàm số phòng và tiền khách sạn; golden case đoàn 10 người lớn có nhiều khách sạn từ Search.
