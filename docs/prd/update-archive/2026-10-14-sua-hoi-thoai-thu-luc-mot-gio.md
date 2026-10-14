# Sửa hội thoại thử lúc một giờ sáng

- Ngày: 2026-10-14
- Người đề xuất: Nguyễn Minh Nhật / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-14 — “sửa đi” sau phần đối chiếu năm nhóm lỗi và hành vi mong muốn trong chat.
- PRD bị ảnh hưởng: `docs/prd/requirements.md` AC-AGT-01/06/07; `docs/prd/user-flow.md` §4.2
- Mã FR/NFR: FR-AGT-01/02/04/06, NFR-REL-01

## Lý do

Hội thoại ngày 14/10: quên ngày đã nhận, đổi đối tượng khách sạn thành hoạt động ngoài trời, tìm trong nơi khách
đã loại, lặp tiêu đề sản phẩm và lời tư vấn thiên về bán vé. Khách yêu cầu ưu tiên điểm miễn phí khi hỏi chung và
chuyển sang nghỉ ngơi nhẹ nhàng khi không muốn đi chơi. Các lỗi giữ ngữ cảnh/đọc câu sửa/grounding là sửa theo PRD.

## Nội dung đề xuất

1. AC-AGT-06 hiện: có điểm đến thì giới thiệu điểm tham quan/khách sạn nổi bật. Bổ sung: hỏi chung chưa nêu sở thích
   trả phí thì ưu tiên điểm tham quan tự do, chọn tiêu biểu từ Catalog/Recommendation có nguồn; đây là ưu tiên mềm,
   không ghi thành ràng buộc chỉ miễn phí. Khách yêu cầu dịch vụ trả phí cụ thể vẫn được tìm đúng nhu cầu.
2. AC-AGT-01 hiện: mất hứng thì khơi tò mò một lần bằng tối đa một sản phẩm vừa tra. Bổ sung lựa chọn: với “không
   muốn đi chơi”, có thể công nhận mong muốn nghỉ ngơi, nêu vài hướng nhẹ nhàng ở mức ý tưởng và hỏi một câu về khu
   vực nếu chưa biết. Không bịa tên quán/spa, không hứa có dữ liệu ngoài danh mục, không mời lập lịch; dừng rõ/từ
   chối tiếp vẫn kết thúc. Khi giới thiệu cơ sở cụ thể vẫn phải tra, tối đa một thẻ/một nút trong lần khơi gợi.
3. AC-AGT-07 và user-flow §4.2: câu dẫn mô tả trải nghiệm có nguồn; không dùng thời hạn mở bán để nói “mở cửa quanh
   năm”. Không render dòng chỉ lặp tên sản phẩm ngay cạnh thẻ; giữ tên trong câu có nghĩa và thẻ mở chi tiết.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/orc_v2.py`: hướng dẫn giữ thông tin, đối tượng/phạm vi, giọng hướng dẫn, ưu tiên tự do,
  nghỉ ngơi; đọc lịch sử theo đúng người nói. Thông tin mới được phép gửi cùng final và vẫn kiểm evidence.
- `src/backend/app/application/itinerary/orc_contracts.py`, `orc_dispatch.py`: tham số nội bộ tìm đúng tên và loại
  điểm đến; kiểm bộ lọc do orc yêu cầu, không tự truy vấn/thay sản phẩm. Không đổi API giữa các team.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx`: bỏ tiêu đề tên trùng, giữ câu dẫn và thao tác.
- Test unit vòng orc, use case/store, lọc tool, widget; đặc tả v2 và lịch sử cùng task.
