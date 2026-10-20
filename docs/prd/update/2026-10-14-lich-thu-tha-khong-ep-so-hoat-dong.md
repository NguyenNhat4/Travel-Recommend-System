# Lịch thư thả không bị ép thêm hoạt động

- Ngày: 2026-10-14
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3; `docs/prd/requirements.md` §3 AC-AGT-04
- Mã FR/NFR: FR-AGT-01/03/04, AC-AGT-04, NFR-REL-01

## Lý do

AC-AGT-04 ghi không lấp đầy mọi buổi, nhưng architecture §3 ghi ngày trọn vẹn có 2–3 hoạt động.
`plan_itinerary` hiện trả `TOO_FEW_ACTIVITIES` nếu lịch ít hơn hai hoạt động và còn ứng viên khác.
Vì vậy yêu cầu nghỉ nhiều hoặc chỉ đi một nơi mỗi ngày có thể bị từ chối dù lịch hợp lệ về thời gian và nguồn.

Người dùng chỉ chọn sửa mục 3 và 4 của bản expected outcome (mất hứng/dừng và câu phủ định theo ngữ cảnh).
Đề xuất nhịp lịch này chưa được chốt và không được áp dụng trong task sửa prompt.

## Nội dung đề xuất

Trong `architecture.md` §3, thay:

> Ngày trọn vẹn có 2–3 hoạt động, tối đa một sản phẩm mỗi buổi sáng/chiều/tối; hoạt động cả ngày dùng
> cả sáng và chiều nhưng tính một sản phẩm. Ngày đến/về theo giờ bay có thể ít hơn.

Bằng:

> Khi khách chưa nêu nhịp đi, orc có thể đề xuất 2–3 hoạt động cho ngày trọn vẹn; đây là gợi ý mềm,
> không phải số lượng tối thiểu để lịch hợp lệ. Khách muốn nghỉ nhiều, chỉ chọn một nơi hoặc không có
> ứng viên phù hợp thì được để trống buổi. Không tự thêm điểm để đủ số lượng. Tối đa một sản phẩm mỗi
> buổi sáng/chiều/tối; hoạt động cả ngày dùng cả sáng và chiều nhưng tính một sản phẩm. Giữ mọi kiểm
> tra nguồn, trùng địa điểm, giờ mở, ngày dùng, mốc khóa và khoảng đệm chuyến bay.

Trong `requirements.md` AC-AGT-04, bổ sung sau “không lấp đầy mọi buổi”:

> Số hoạt động theo nhịp đi và lựa chọn của khách; lịch không bị từ chối chỉ vì ngày trọn vẹn có ít
> hơn hai hoạt động, kể cả khi đã tra được ứng viên khác.

Không cho phép lịch hoàn toàn rỗng giả thành lịch hoàn chỉnh; giữ kiểm tra hiện hành cho trường hợp này.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/orc_v2.py`: hướng dẫn nhịp mặc định mềm, ưu tiên yêu cầu nghỉ ngơi của khách.
- `src/backend/app/domain/itinerary/draft_validation.py`: bỏ vi phạm bắt buộc `TOO_FEW_ACTIVITIES`;
  không đổi các kiểm tra thời gian, nguồn, trùng, khóa hay chi phí.
- `src/backend/tests/unit/domain/test_orc_slot_planning.py`: lịch một hoạt động hợp lệ dù còn ứng viên;
  giữ hồi quy lịch rỗng, trùng điểm và buổi không phù hợp.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`: đồng bộ luật nhịp đi.
- Bộ đo trước/sau: câu yêu cầu mỗi ngày một điểm, dành thời gian nghỉ.
