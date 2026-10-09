# Thanh "Ngân sách dự tính" trong câu trả lời lịch trình

- Ngày: 2026-10-09
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-09 (chốt trong phiên: ba nhóm lấy từ sản phẩm, không có "Ăn uống")
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §4.2
- Mã FR/NFR: FR-AGT-02 (tính toán chi phí dự kiến), FR-AGT-03, FR-AGT-04, NFR-REL-01

## Lý do

Người dùng muốn thấy tổng tiền của lịch trình được chia thành từng nhóm (mẫu tham khảo: thanh màu "Ngân sách dự tính" với
Di chuyển, Lưu trú, Ăn uống, Vui chơi). PRD hiện chỉ có tổng chi phí ở cột lịch trình, không có phần chia theo nhóm.

Mẫu tham khảo có khoản "Ăn uống". Catalog không có sản phẩm ăn uống, nên khoản này sẽ là con số không có nguồn. Điều đó
trái nguyên tắc grounding (FR-AGT-04, NFR-REL-01) và trái quy tắc "tổng chỉ gồm sản phẩm trong lịch" (`PRODUCT_COST_ONLY`).
Vì vậy đề xuất bỏ khoản này.

## Nội dung đề xuất

### `docs/prd/user-flow.md` §4.2 — thêm sau mục 1 "Thẻ trong khung chat"

> **Ngân sách dự tính:** câu trả lời có lịch trình và biết đủ giá thì có một khối "Ngân sách dự tính" ở cuối bong bóng
> chat: tổng tiền, số ngày và đêm, một thanh màu chia tổng theo ba nhóm và từng dòng số tiền. Ba nhóm là Vé máy bay, Lưu trú
> và Vui chơi (tour, điểm tham quan, golf; điểm tham quan tự do tính 0 đ). Số tiền mỗi nhóm do backend tính từ giá sản phẩm
> trong lịch, cộng lại đúng bằng tổng tiền. Nhóm bằng 0 vẫn có dòng nhưng không có đoạn trên thanh. Khi người dùng nêu ngân
> sách, khối ghi ngân sách và trạng thái "Trong ngân sách" hoặc "Vượt ngân sách". Khối ghi rõ tổng chưa gồm ăn uống và đi
> lại tại điểm đến; không có khoản ước tính nào ngoài sản phẩm. Giá chưa đủ (tổng chưa biết) thì không có khối. Đổi khách
> sạn bằng hàng thẻ thì khối cập nhật theo lịch mới.

## Thay đổi source sau khi chốt

- Contract `src/shared/contracts/schemas/itinerary-agent.yaml` (1.21.0, thêm vào, tương thích ngược): `ItineraryPlan`
  thêm trường tuỳ chọn `costBreakdown {flights, stays, activities}`; có khi `estimatedTotal` khác null, tổng ba nhóm bằng
  `estimatedTotal`. Sinh lại `src/frontend/src/types/api.gen.ts`.
- Backend `src/backend/app/domain/itinerary/planning.py`: tính `costBreakdown` cùng chỗ với tổng tiền; `validate_plan`
  kiểm tổng ba nhóm.
- Frontend `src/frontend/src/features/itinerary/widget/`: khối `WidgetBudget` ở cuối câu trả lời; `widgetPlan.ts` đọc
  `costBreakdown`.
- Spec: `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/agent/nghiep-vu/xep-lich.md` (mục Tiền).
- Test: unit domain (ba nhóm cộng đúng tổng, chưa biết giá thì không có), frontend (khối hiện đúng số, không có khi thiếu).
