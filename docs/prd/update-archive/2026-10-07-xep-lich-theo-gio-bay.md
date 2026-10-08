# Xếp hoạt động của lịch trình theo giờ máy bay

- Ngày: 2026-10-07
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-07
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-02)
- Mã FR/NFR: FR-AGT-03, AC-AGT-02

## Lý do

Từ ngày 06/10/2026, lịch trình có chặng bay (AC-AGT-02). Nhưng lúc xếp hoạt động, hệ thống chưa biết giờ máy bay hạ cánh
và giờ bay về. Hoạt động đầu tiên của mỗi ngày luôn xếp vào buổi sáng.

Lỗi gặp khi chạy thật ngày 06/10/2026 với câu "Lên lịch trình 3 ngày ở Đà Nẵng từ ngày 8/10/2026, 2 người lớn, đi từ Hà
Nội":
- chặng đi VJ505 cất cánh 19:50 ngày 1;
- lịch vẫn xếp Bà Nà vào buổi sáng ngày 1, lúc khách còn ở Hà Nội.

Ngày về cũng có lỗi tương tự: hoạt động có thể nằm sau giờ phải ra sân bay.

FR-AGT-03 đã yêu cầu lịch trình chia buổi sáng – trưa – chiều – tối và có thời gian di chuyển ước tính. AC-AGT-02 chưa nói
các buổi này phải khớp với giờ bay.

## Nội dung đề xuất

### `requirements.md` §3 — AC-AGT-02

Hiện tại, sau câu "Giá vé × số khách tính vào tổng; vé không bị bỏ vì vượt ngân sách, khi đó lịch trình báo vượt ngân
sách." thì sang ngay phần "Không có chặng bay…".

Thêm vào giữa hai câu đó:

> Khi có chặng bay, hoạt động được xếp theo giờ bay:
> - **Ngày đến:** hoạt động chỉ nằm ở buổi bắt đầu từ **90 phút sau giờ hạ cánh**. Ngày này có dòng "Di chuyển từ sân bay,
>   nhận phòng" ở buổi hạ cánh.
> - **Ngày về:** hoạt động chỉ nằm ở buổi kết thúc trước **150 phút trước giờ cất cánh**. Ngày này có dòng "Ra sân bay"
>   ở buổi cất cánh.
> - **Hoạt động cả ngày** (từ 6 giờ trở lên) không xếp vào ngày đến hay ngày về bị giới hạn giờ.
> - **Không đủ buổi:** hoạt động được dời sang ngày khác của chuyến; không còn ngày trống thì không xếp, như luật hiện tại.
> - **Vé thiếu giờ bay:** ngày đó không bị giới hạn. Hệ thống không đoán giờ bay.
>
> Ví dụ: chặng đi hạ cánh 21:05 thì ngày 1 chỉ có dòng di chuyển, không có hoạt động. Chặng về cất cánh 19:45 thì ngày
> cuối vẫn có buổi sáng và buổi chiều.

Thứ tự chọn vé (bay thẳng → giá thấp → giờ hợp lý) **không đổi**.

## Thay đổi source sau khi chốt

- **Khung giờ của từng buổi:** sáng 08:00–12:00, trưa 12:00–13:30, chiều 13:30–17:00, tối 18:00–21:00.
  - Hoạt động vẫn chỉ xếp vào buổi sáng và chiều như hiện nay. Lý do: compose chưa đọc giờ mở cửa (`openingHours` có ở
    413/610 điểm tham quan trong snapshot 2026-09-30), nên chưa biết điểm nào còn mở buổi tối. Dùng giờ mở cửa là việc
    riêng, ngoài đề xuất này.
  - Ghi khung giờ vào `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7.
- **`src/backend/app/domain/itinerary/flights.py`:** thêm hàm thuần `day_windows`. Hàm đọc giờ hạ cánh và giờ cất cánh từ
  thuộc tính của vé:
  - vé một chiều: `arrivalTimeLocal`/`arrivalAt`, `departureTimeLocal`/`departureAt`;
  - vé khứ hồi: `returnFlight.departureAt`.
- **`src/backend/app/domain/itinerary/planning.py`:**
  - `compose_plan` nhận cửa sổ giờ của từng ngày và chọn buổi theo cửa sổ;
  - thêm slot `TRANSFER` không gắn sản phẩm;
  - `validate_plan` báo lỗi khi slot có sản phẩm nằm ngoài cửa sổ.
- **`src/backend/app/agents/steps/composition.py`:** chọn vé **trước** khi xếp lịch, rồi mới gắn vé vào lịch.
- **Contract:** không đổi. Dùng `SlotTime` và `ActivityType.TRANSFER` sẵn có.
- **Frontend:** không đổi. Widget đã hiển thị slot `TRANSFER`.
- **Test:** domain (`day_windows`, compose), runtime (`FlightTests`), widget.
- **Spec:** `docs/spec/agent/langgraph-nodes.md` (hàng `compose`).
