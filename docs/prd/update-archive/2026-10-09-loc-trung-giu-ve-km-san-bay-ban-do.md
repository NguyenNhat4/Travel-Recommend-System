# Lọc trùng giữ vé có phí, km tính cả sân bay, bản đồ theo thẻ khách sạn

- Ngày: 2026-10-09
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-09 (chốt trong phiên, kèm điều chỉnh: điểm tham quan tự do không tách khỏi lịch;
  cặp trùng giữa điểm tự do và vé có phí thì giữ vé)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-03, FR-AGT-04, NFR-REL-01, AC-AGT-04

## Lý do

Hội thoại thật ngày 09/10/2026: "Lên lịch trình 3 ngày tại Phú Quốc, bắt đầu từ ngày 2026-10-10, đi từ Sai gon", trả lời
thêm "đi 1 mình" (LangSmith `nhat-10-7`, trace `01a11e8e-1f8a-7d70-b7fc-3f9b42e7d370`). Câu trả lời chỉ có một khách sạn,
không có mục "Phương án khác".

1. **Không có phương án khác vì không có gì để đánh đổi.** Chạy lại bước xếp lịch bằng dữ liệu của trace: Venus Hotel vừa
   gần nhất (84,6 km cả chuyến) vừa rẻ nhất (1.918.000 đ). Sáu khách sạn còn lại đem ra so đều xa hơn và đắt hơn (An Phu
   85,8 km / 2.482.000 đ, Leono Coast 105,3 km / 2.009.900 đ, …). Luật đang đúng như PRD ghi.
2. **Bước lọc trùng bỏ vé bán được để giữ điểm tự do.** Lịch giữ "hòn Thơm" (tự do, 0 đ) và bỏ vé "Cáp Treo Hòn Thơm" vì
   luật chọn mã rẻ hơn. Người dùng mất một trải nghiệm đặt được mà không có lợi gì.
3. **Km chưa phản ánh đường đi thật.** Ngày đầu tính từ điểm tham quan đầu tiên, ngày cuối dừng ở điểm cuối. Đường từ sân
   bay về khách sạn và ra sân bay không được tính, nên khách sạn sát sân bay hay cách sân bay 30 km đều được chấm như nhau.
4. **Số km là ước tính đường chim bay nhưng hiện như số đo chính xác.** Người xem không biết con số đó gồm những gì.
5. **Bản đồ chưa giúp so khách sạn.** Bấm một thẻ khách sạn thì bản đồ đổi lịch nhưng chỉ vẽ đường của một ngày, không cho
   thấy khách sạn đó nằm ở đâu so với các điểm cả chuyến và sân bay.

Điểm tham quan tự do vẫn ở trong lịch và tính 0 đ như hiện nay. Không đổi thành "chưa rõ giá", vì một khoản chưa rõ giá
làm cả lịch không có phương án khách sạn nào.

## Nội dung đề xuất

### 1. AC-AGT-04 — lọc trùng giữ vé có phí

Hiện tại:

> Mỗi cặp giữ một mã theo thứ tự ưu tiên đang có (Search trước Recommendation, rồi rẻ hơn, rồi mã nhỏ hơn)

Thay bằng:

> Mỗi cặp giữ một mã theo thứ tự: vé có phí trước điểm tham quan tự do (ví dụ giữ "Cáp Treo Hòn Thơm", bỏ "hòn Thơm"), rồi
> Search trước Recommendation, rồi rẻ hơn, rồi mã nhỏ hơn

### 2. AC-AGT-04 — quãng đường tính cả sân bay

Hiện tại:

> Quãng đường mỗi ngày tính từ khách sạn đêm trước (ngày 1: từ điểm đầu tiên) qua các điểm theo thứ tự buổi, tới khách sạn
> đêm đó (ngày cuối: dừng ở điểm cuối)

Thay bằng:

> Quãng đường mỗi ngày tính từ khách sạn đêm trước qua các điểm theo thứ tự buổi, tới khách sạn đêm đó. Ngày 1 bắt đầu ở sân
> bay đến rồi về khách sạn trước khi đi các điểm (sân bay → khách sạn → các điểm → khách sạn); ngày cuối đi từ khách sạn qua
> các điểm rồi ra sân bay. Toạ độ sân bay lấy từ chặng bay đã chọn; chỉ có một chiều thì dùng sân bay của chiều đó cho cả
> hai đầu; không có chặng bay nào (hoặc chặng bay không có toạ độ) thì ngày 1 tính từ điểm đầu tiên và ngày cuối dừng ở
> điểm cuối như trước. Phần sân bay được tính khi chọn khách sạn và khi tính chênh km của phương án khác

### 3. AC-AGT-04 — cách hiện số km

Hiện tại:

> Khoảng cách tính theo đường chim bay; lịch trình chưa hiện số km từng ngày; tổng km và chênh km chỉ xuất hiện trong mục
> Phương án khác.

Thay bằng:

> Khoảng cách tính theo đường chim bay; lịch trình chưa hiện số km từng ngày; tổng km và chênh km chỉ xuất hiện trong mục
> Phương án khác. Mọi số km có dấu "≈" phía trước, và hàng thẻ có một dòng lưu ý: "Số km là ước tính quãng đường di chuyển
> cả hành trình, gồm cả đường sân bay." (không có chặng bay thì bỏ vế "gồm cả đường sân bay").

### 4. AC-AGT-04 — bản đồ khi bấm thẻ khách sạn

Hiện tại:

> Bấm vào một thẻ thì thẻ đó nổi lên và bảng lịch trình bên phải, bản đồ, tổng tiền hiện lịch của phương án đó để xem trước

Thay bằng:

> Bấm vào một thẻ thì thẻ đó nổi lên và bảng lịch trình bên phải, bản đồ, tổng tiền hiện lịch của phương án đó để xem trước.
> Bản đồ chuyển sang xem cả chuyến: vẽ đường đi của mọi ngày trong lịch đó, gồm sân bay (sân bay → khách sạn → các điểm → …
> → sân bay), và chỉ hiện biểu tượng khách sạn của phương án đang xem. Các đoạn đường được vẽ dần lần lượt theo thứ tự đi;
> khi người dùng bật chế độ giảm chuyển động của hệ điều hành thì đường hiện ngay, không có hiệu ứng

### Không đổi

- Điểm tham quan tự do vẫn xếp vào lịch, tính 0 đ, hiển thị "tham quan tự do" (`architecture.md` §3 giữ nguyên).
- Grounding 100% (FR-AGT-04, NFR-REL-01): toạ độ sân bay lấy từ chặng bay thật của catalog; LLM không thấy số km.
- Luật chọn khách sạn (gần trước, rẻ hơn khi ngang nhau, trong ngân sách), phạt đổi khách sạn 15 km, tối đa 3 phương án và
  ngưỡng chênh 2 km giữ nguyên.
- Tình huống ở Lý do 1 (một khách sạn vừa gần nhất vừa rẻ nhất) vẫn không có phương án khác: đó là đúng luật.
- Contract không đổi: toạ độ sân bay đi (`originLatitude`/`originLongitude`) là khoá sẵn có trong `attributes` của chuyến
  bay, chỉ thêm vào danh sách khoá giữ lại khi tóm tắt sản phẩm.

## Thay đổi source sau khi chốt

- Backend:
  - `src/backend/app/domain/itinerary/planning.py`: `keep_rank` đặt vé có phí trước điểm tự do; giữ thêm
    `originLatitude`/`originLongitude` trong tóm tắt sản phẩm; `compose_plan` nhận toạ độ sân bay.
  - `src/backend/app/domain/itinerary/flights.py`: toạ độ sân bay đến/đi từ chặng bay đã chọn.
  - `src/backend/app/domain/itinerary/routing.py`: chặng sân bay trong chi phí, chọn khách sạn, phương án khác.
  - `src/backend/app/agents/steps/composition.py`, `messages.py`: truyền sân bay; "≈" trước số km.
- Frontend:
  - `src/frontend/src/services/routeGeometry.ts`: chặng sân bay.
  - `src/frontend/src/components/assistant/ItineraryMap.tsx`: biểu tượng sân bay, xem cả chuyến khi xem trước, vẽ dần.
  - `src/frontend/src/features/itinerary/widget/` (`WidgetStayOptions.tsx`, `WidgetPlanPanel.tsx`): "≈", dòng lưu ý,
    báo bản đồ đang xem trước.
- Spec: `docs/spec/agent/nghiep-vu/xep-lich.md`, `docs/spec/agent/nghiep-vu/glossary.md`,
  `docs/spec/hop-dong-tich-hop-frontend.md`.
- Test: unit domain (giữ vé có phí; km có chặng sân bay; không có vé thì như cũ), unit agent ("≈"), frontend
  (`routeGeometry`, hàng thẻ).
