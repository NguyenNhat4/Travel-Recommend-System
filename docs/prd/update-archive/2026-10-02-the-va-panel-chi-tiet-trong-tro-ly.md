# Thẻ sản phẩm trong khung chat và panel chi tiết khi bấm (desktop)

- Ngày: 2026-10-02
- Người đề xuất: nhatnm / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: nhatnm, 2026-10-02
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §4.2 (Widget Trợ Lý Lịch Trình AI), §3.2 (bước "Render thẻ sản phẩm Grounded")
- Mã FR/NFR: FR-AGT-03, FR-AGT-04, AC-AGT-01, NFR-REL-01

## Lý do

Người dùng đưa ảnh tham chiếu (desktop) của một trợ lý du lịch khác:

- Lời kể đi theo ngày, và ngay sau mỗi địa điểm có một thẻ thật: ảnh, điểm đánh giá, địa chỉ.
- Bấm thẻ thì cột phải mở panel chi tiết: bộ ảnh, mô tả, địa chỉ với "Chỉ đường", giờ mở cửa, điểm đánh giá.

Widget hiện tại:

- Khung chat chỉ có chữ. Tên sản phẩm là link focus thẻ ở cột lịch trình.
- Thẻ, bản đồ và tổng tiền nằm ở cột phải.
- Muốn xem chi tiết một nơi thì phải mở tab mới sang trang sản phẩm.

PRD §4.2 chỉ vẽ thẻ ở cột lịch trình. Thêm thẻ vào khung chat và thêm panel chi tiết là đổi luồng người dùng, nên cần chốt.

## Nội dung đề xuất

### `user-flow.md` §3.2

Hiện tại: `F --> H[Stream phản hồi + Render thẻ sản phẩm Grounded]`

Thay bằng: `F --> H[Lời diễn giải kèm thẻ sản phẩm Grounded ngay sau lần nhắc đầu tiên; bấm thẻ mở panel chi tiết]`

### `user-flow.md` §4.2

Giữ đoạn mở đầu và form gợi ý. Thay wireframe "Toàn màn hình" bằng:

```
Toàn màn hình (desktop):
+------------------------------------+------------------------------------------------+
| [Lịch sử]  Trợ lý du lịch AI       | Mặc định: LỊCH TRÌNH THEO NGÀY + BẢN ĐỒ        |
|                                    |   thẻ, tổng chi phí, [Thêm vào giỏ] [Thanh toán] |
| [AI]: **Ngày 1**                   |                                                |
|   Sáng: tắm biển, dạo bãi cát...   | Bấm thẻ → PANEL CHI TIẾT thay chỗ ở trên:      |
|   [ảnh] Bãi biển Trần Phú  ★4.5 [›]|   [ảnh lớn][ảnh][ảnh][+n]                 [X]  |
|   Tối: xem show...                 |   Tên · mô tả                                  |
|   [ảnh] Combo Tata Show 620.000 ₫  |   Địa chỉ [Chỉ đường] · Giờ mở cửa             |
|                                    |   ★ 4.5 (2.046 đánh giá) · Giá                 |
| [ Mô tả chuyến đi...          [↑] ]|   [Thêm vào giỏ] [Xem trang chi tiết]          |
+------------------------------------+------------------------------------------------+
```

Thêm bốn quy tắc dưới wireframe:

1. **Thẻ trong khung chat.** Mỗi sản phẩm của lịch trình có một thẻ gọn **ngay sau lần nhắc đầu tiên** trong lời diễn
   giải. Phạm vi gồm khách sạn, hoạt động và gói nhiều ngày gợi ý riêng.
   - Thẻ có: ảnh nhỏ, tên, điểm đánh giá và số lượt (chỉ khi có), địa chỉ, giá hoặc "Tham quan tự do", và nút "Thêm".
   - Dữ liệu thẻ lấy từ `itinerary`/`searchResults` của response, không lấy từ chữ của LLM.
   - Mỗi sản phẩm chỉ có một thẻ. Id lạ thì bỏ qua.
2. **Bấm thẻ hoặc tên sản phẩm** trong lời diễn giải thì mở panel chi tiết ở cột phải.
   - Đang ở dạng thu gọn thì widget mở toàn màn hình trước.
   - X hoặc Esc quay về cột lịch trình và bản đồ.
3. **Panel chi tiết** lấy dữ liệu từ `GET /products/{productId}` và có:
   - bộ ảnh, tên, mô tả;
   - địa chỉ và "Chỉ đường" (mở Google Maps theo toạ độ; ẩn khi không có toạ độ);
   - giờ mở cửa (chỉ khi có);
   - điểm đánh giá và số lượt, không gắn logo nguồn;
   - giá, "Thêm vào giỏ", "Xem trang chi tiết".
4. **Ngoài phạm vi.** Danh sách bình luận, ảnh hay video của người đánh giá: catalog không có dữ liệu này, nên không hiển
   thị và không tạo giả. Giao diện mobile cũng nằm ngoài phạm vi.

## Thay đổi source sau khi chốt

- **PRD:** `docs/prd/user-flow.md` §3.2 và §4.2 như trên.
- **Spec:** `docs/spec/hop-dong-tich-hop-frontend.md`.
  - §4.8: thêm hàng "Xem chi tiết sản phẩm trong widget" gọi `GET /products/{productId}`.
  - §5: thẻ trong khung chat dùng `ProductCard` compact.
- **Frontend:**
  - `components/assistant/inlineBold.tsx`: tách lời diễn giải thành khối theo dòng.
  - `features/itinerary/widget/WidgetChat.tsx`: chèn thẻ sau khối nhắc đầu tiên.
  - `components/common/ProductCard.tsx`: bản compact thêm điểm đánh giá, địa chỉ, "Tham quan tự do".
  - Thêm mới `features/itinerary/widget/WidgetProductDetail.tsx`.
  - `useFloatingWidget.ts`: thêm `selectedProductId` và `openProductDetail`.
  - `FloatingWidget.tsx`: cột phải ưu tiên panel chi tiết.
- **Backend:** `application/search/use_cases.py` `hit` trả thêm `rating`, `reviewCount` để thẻ trong lịch trình có điểm
  đánh giá. Cả hai là trường tuỳ chọn đã có trong `ProductSummary`, nên contract không đổi.
- Không đổi prompt, contract hay DDL. Grounding giữ nguyên: thẻ và panel chỉ đọc dữ liệu sản phẩm thật.
