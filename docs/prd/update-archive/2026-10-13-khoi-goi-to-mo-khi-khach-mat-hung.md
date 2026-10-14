# Khơi lại tò mò bằng dữ liệu khi khách mất hứng

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13
- PRD bị ảnh hưởng: `requirements.md` §1.4, §3 AC-AGT-01/06/07; `user-flow.md` §4.2
- Mã FR/NFR: FR-AGT-01/06, NFR-REL-01

## Lý do

Người dùng muốn agent chủ động khơi tò mò thay vì kết thúc bằng “khi nào quay lại…”, nhất là khi khách chưa biết muốn gì. PRD AC-AGT-01 hiện yêu cầu không thuyết phục khi khách nói “không đi nữa”, prompt v2 thực hiện đúng luật đó. Đây là thay đổi hành vi cần chốt trước code.

## Nội dung đề xuất

### `requirements.md` AC-AGT-01 và `user-flow.md` §4.2

Hiện tại: khách không muốn đi/lập lịch nữa → cảm ơn, hẹn gặp lại; không hỏi thêm, không thuyết phục; giữ thông tin chuyến.

Thay bằng: phân biệt khách mất hứng/chưa quyết định với yêu cầu dừng tương tác rõ ràng. Với “không muốn đi nữa”, “chán quá”, “chưa biết có gì hay”, agent ngừng lập lịch và không mở form, nhưng có thể khơi tò mò một lần bằng một lựa chọn khác đã tra trong catalog của lượt này, nêu điểm cụ thể đáng xem từ mô tả/thuộc tính. Không chỉ hứa sẽ giúp khi khách quay lại, không lặp sản phẩm bị chê, không tạo trải nghiệm hoặc lời khen thiếu nguồn. Với “dừng”, “đừng gợi ý nữa”, “không cần tư vấn nữa” hoặc từ chối tiếp sau lần khơi tò mò, kết thúc ngắn, không thẻ/nút/câu hỏi và không gọi tool để níu. Giữ lịch/chuyến đang có, hủy lời mời lập lịch đang chờ; gợi ý mới không phải consent lập lịch.

### `requirements.md` FR-AGT-06, AC-AGT-06/07

Bổ sung: khi khách chưa biết gì/chưa biết đi đâu, orc tự tra catalog/recommendation trong phạm vi phù hợp và giới thiệu một vài lựa chọn thật có điểm khác biệt, không chỉ hỏi lặp “bạn thích gì”. Với lượt khơi lại tò mò, tối đa một thẻ và hai câu, không hỏi thông tin chuyến; có thể có một nút xem thêm đúng lựa chọn. Có yêu cầu dừng rõ thì không níu. Không có dữ kiện phù hợp hoặc tool lỗi thì nói ngắn phần chưa kiểm được, không bịa mồi tò mò. Mọi tìm kiếm vẫn trong quota hiện có.

## Thay đổi source sau khi chốt

- PRD trước, rồi prompt/context của `src/backend/app/agents/orc_v2.py`, mô tả `stopped` và state theo hội thoại ở `application/itinerary/orc_contracts.py` nếu cần để nhớ lần đã khơi tò mò.
- Giữ consent và plan_effect=keep; không cho gợi ý níu tự hồi sinh lập lịch.
- Tests hành vi/context: mất hứng, chưa biết nơi, dừng rõ, từ chối tiếp, tiếp tục khám phá, chỉ lập lại lịch khi consent mới có căn cứ. Không thêm classifier/node/agent riêng.
- Gộp bước vào plan cải thiện agent hiện có; người dùng tự eval giọng văn sau kiểm kỹ thuật.
