# Trần 5 thẻ mỗi loại và trả lời câu hỏi "có bao nhiêu"

- Ngày: 2026-10-14
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` AC-AGT-06, FR-AGT-06
- Mã FR/NFR: FR-AGT-06, AC-AGT-06, NFR-REL-01

## Lý do

1. **Trần thẻ.** AC-AGT-06 hiện cho tối đa 10 thẻ mỗi loại (hotel/attraction/combo/golf/flight). Mười thẻ một loại
   quá dài trong khung chat. Muốn hạ xuống 5, orc tự quyết số lượng trong trần. Khách xin nhiều hơn 5 thì trả 5 và
   nói rõ mỗi lần chỉ gửi được 5, mời xem thêm ở lượt sau.
2. **Câu hỏi số lượng** ("Hà Nội có bao nhiêu khách sạn?"). Hiện orc không trả lời được bằng số: `coverage.total`
   của lời gọi tìm không nằm trong `data`, nên `fact` không trích được, viết số vào câu thì guard báo
   `NUMBER_WITHOUT_FACT`. Muốn trả lời ước lượng có căn cứ, ví dụ "Theo những gì mình tìm được, hệ thống có hơn 130
   khách sạn ở Hà Nội", không khẳng định là toàn bộ khách sạn ngoài thực tế.

## Nội dung đề xuất

### `docs/prd/requirements.md` AC-AGT-06

Hiện tại:

> Phần gợi ý tối đa 10 sản phẩm khác nhau mỗi taxonomy hotel/attraction/combo/golf/flight trên hợp recommendations và
> alternatives toàn lượt; không có trần tổng 20, không nhân trần theo call/group/nguồn/continuation. Không áp trần gợi
> ý lên lịch nhiều ngày. Orc quyết số lượng/thứ tự, không buộc đủ 10; thiếu dữ liệu/ngân sách thực thi thì nói rõ.

Thay bằng:

> Phần gợi ý tối đa 5 sản phẩm khác nhau mỗi taxonomy hotel/attraction/combo/golf/flight trên hợp recommendations và
> alternatives toàn lượt; không nhân trần theo call/group/nguồn/continuation. Không áp trần gợi ý lên lịch nhiều ngày.
> Orc quyết số lượng/thứ tự, không buộc đủ 5. Khách xin nhiều hơn 5 thì trả tối đa 5 và nói rõ mỗi lượt chỉ gửi được
> 5, mời xem thêm; thiếu dữ liệu/ngân sách thực thi thì nói rõ.
>
> Câu hỏi số lượng ("có bao nhiêu khách sạn ở Hà Nội") trả lời bằng tổng của lời gọi duyệt Catalog có cùng điều kiện,
> làm tròn xuống và nói là số trong hệ thống theo kết quả tìm ("hơn 130"), không khẳng định toàn bộ thực tế. Tổng của
> Search theo chủ đề chỉ là số khớp trong trang đã tìm, không dùng làm số lượng.

### `docs/prd/requirements.md` FR-AGT-06

Câu "Khi nêu số lượng gợi ý, trợ lý tìm và giới thiệu theo số lượng đó trong giới hạn AC-AGT-06" giữ nguyên; giới hạn
mới lấy theo AC-AGT-06 sửa ở trên.

## Thay đổi source sau khi chốt

- `src/backend/app/application/itinerary/orc_contracts.py`, `src/backend/app/domain/itinerary/orc_guardrails.py`:
  `MAX_CARDS_PER_TAXONOMY = 5`; mô tả alternatives "trần 5 thẻ mỗi loại".
- `src/backend/app/agents/orc_v2.py` `PROMPT`: "Tối đa năm thẻ mỗi loại…; khách xin nhiều hơn thì nói rõ giới hạn";
  cách trả lời câu hỏi số lượng.
- `src/backend/app/application/itinerary/orc_dispatch.py`: kết quả duyệt Catalog thêm `data.total` và
  `data.total_rounded` (làm tròn xuống: dưới 100 theo hàng chục, từ 100 theo hàng chục, từ 1.000 theo hàng trăm) để
  orc trích bằng fact `cN` + `total_rounded`; Search không thêm.
- `src/shared/contracts/schemas/assistant-v2.yaml`: `maxItems` 10 → 5 cho các mảng thẻ theo loại và mô tả
  alternatives. Hạ trần ở response không phá client (client vẫn nhận ≤ 10).
- Tests: `test_orc_guardrails.py` (trần 5), `test_orc_tool_dispatch.py` (total_rounded), `test_orc_contracts.py`;
  `validate_contract.py`.
- Spec: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/working-context.md`.

## Điểm cần chốt

1. Trần 5 **mỗi loại** (5 khách sạn + 5 điểm tham quan trong một lượt) hay 5 **tổng cả lượt**? Đề xuất: mỗi loại.
2. Cách làm tròn số lượng ở trên có được không, hay nói số chính xác kèm "trong hệ thống"?
