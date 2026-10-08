# Tối ưu tổng quãng đường của chuyến, cho phép đổi khách sạn giữa chuyến

- Ngày: 2026-10-07
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-07 (dùng tham số đề xuất; sửa chuyến tối thiểu thành 5 ngày, xem dưới)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-03, NFR-REL-01, AC-AGT-04

## Sửa khi áp dụng (người dùng chốt 2026-10-07)

Bản đề xuất ghi "chuyến từ 4 ngày" cùng lúc với "mỗi khách sạn ít nhất 2 đêm". Chuyến 4 ngày chỉ có 3 đêm nên không chia
được 2 + 2. Người dùng chốt giữ "ít nhất 2 đêm", nên chuyến tối thiểu được đổi khách sạn là **5 ngày** (4 đêm). AC-AGT-04
trong `requirements.md` ghi theo bản đã sửa này; các chỗ "4 ngày" bên dưới chỉ còn giá trị lịch sử.

## Lý do

AC-AGT-04 (chốt sáng 07/10/2026) giảm việc đi lại bằng luật kinh nghiệm:
- gom các điểm gần nhau vào cùng ngày;
- chọn một khách sạn gần các điểm cho cả chuyến.

Luật này không tính trực tiếp quãng đường người dùng thật sự phải đi. Có hai hạn chế:

1. **Kết quả chưa chắc là ít km nhất.** Ghép cặp theo cặp gần nhau nhất có thể bỏ lỡ cách ghép tốt hơn, vì nó không xét
   khoảng cách tới khách sạn.
2. **Một khách sạn cho cả chuyến.** Khi điểm tham quan nằm ở hai đầu xa nhau, khách sạn bị đặt ở giữa. Ví dụ Bắc và Nam
   Phú Quốc cách nhau khoảng 40 km: ngày nào khách cũng đi khoảng 20 km mỗi chiều. Chuyến dài ngày nên cho phép đổi khách
   sạn.

Đề xuất thay luật kinh nghiệm bằng một **hàm mục tiêu rõ ràng** và tìm lịch có giá trị nhỏ nhất. Kích thước bài toán nhỏ:
- tối đa 7 ngày;
- tối đa 2 điểm mỗi ngày;
- khoảng 10 ứng viên mỗi loại.

Vì vậy tìm được lời giải tối ưu trong vài mili giây, không cần dịch vụ ngoài.

## Nội dung đề xuất

### Hàm mục tiêu: quãng đường của chuyến

Ngày 1 bắt đầu ở điểm tham quan đầu tiên, ngày cuối kết thúc ở điểm tham quan cuối cùng. Chặng sân bay chưa tính, vì
catalog chưa có toạ độ sân bay. Gọi `Hd` là khách sạn của đêm thứ d.

| Ngày | Quãng đường |
|---|---|
| Ngày 1 | A₁ → B₁ → H₁ |
| Ngày d (giữa chuyến) | H(d−1) → A_d → B_d → H_d |
| Ngày cuối n | H(n−1) → A_n → B_n |

Tổng quãng đường của chuyến = tổng các dòng trên. Ngày có một điểm thì bỏ chặng A → B. Ngày không có điểm nào thì tính
chặng thẳng từ H(d−1) đến H_d, bằng 0 khi không đổi khách sạn.

Chi phí để so sánh các lịch = tổng quãng đường + **phạt đổi khách sạn** × số lần đổi.

### `requirements.md` §3 — sửa AC-AGT-04

Câu hiện tại:

> Lịch trình giảm việc đi lại. Các điểm gần nhau nằm cùng một ngày; không ghép hai điểm xa nhau vào một ngày khi còn cách
> ghép gần hơn. Khi có nhiều điểm hơn số chỗ trong lịch, ưu tiên điểm gần cụm chính; điểm ở xa bị bỏ trước. Một khách sạn
> cho cả chuyến, nằm gần các điểm đã chọn. Gần trước, rẻ sau: hai lựa chọn chênh nhau dưới 2 km coi như gần ngang nhau,
> khi đó chọn cái rẻ hơn.

Thay bằng:

> Lịch trình có tổng quãng đường nhỏ nhất. Quãng đường mỗi ngày tính từ khách sạn đêm trước (ngày 1: từ điểm đầu tiên)
> qua các điểm theo thứ tự buổi, tới khách sạn đêm đó (ngày cuối: dừng ở điểm cuối). Hệ thống chọn điểm nào được xếp,
> điểm nào đi cùng ngày, thứ tự các ngày và khách sạn từng đêm để tổng này nhỏ nhất.
> - **Số điểm cố định:** lịch luôn xếp đủ số điểm mà các ngày chứa được (như hiện nay). Không bỏ bớt điểm để giảm quãng
>   đường. Khi có nhiều điểm hơn số chỗ, ưu tiên điểm gần cụm chính (như hiện nay).
> - **Đổi khách sạn:** chỉ với chuyến từ 4 ngày; tối đa 1 lần đổi; mỗi khách sạn ít nhất 2 đêm; mỗi lần đổi tính thêm
>   15 km vào chi phí. Ngày đổi khách sạn có dòng "Trả phòng, chuyển sang khách sạn mới". Chuyến dưới 4 ngày, hoặc khi đổi
>   không tiết kiệm hơn 15 km, vẫn một khách sạn.
> - **Gần trước, rẻ sau:** hai lịch có chi phí chênh nhau dưới 2 km coi như ngang nhau, khi đó chọn lịch có tổng tiền
>   thấp hơn.

Các câu còn lại của AC-AGT-04 giữ nguyên: luật đang có, câu nêu tiêu chí, sản phẩm chưa rõ vị trí, khoảng cách đường chim
bay, chưa hiện số km. Câu nêu tiêu chí thêm vế khi có đổi khách sạn.

### Tham số cần chốt

| Tham số | Đề xuất | Vì sao |
|---|---|---|
| Chuyến tối thiểu được đổi khách sạn | 4 ngày (3 đêm) | Chuyến ngắn hơn mà đổi khách sạn thì phiền hơn lợi |
| Số lần đổi tối đa | 1 | Đủ cho chuyến 2 cụm; kéo vali nhiều lần thì phiền |
| Số đêm tối thiểu mỗi khách sạn | 2 | Tránh ở 1 đêm rồi đổi |
| Phạt mỗi lần đổi | 15 km | Chỉ đổi khi đỡ đi lại rõ rệt, khoảng 7–8 km mỗi ngày trên chuyến 4 ngày |
| Mức coi như ngang nhau | 2 km | Giữ như AC-AGT-04 |

### Thuật toán (tất định, không gọi LLM, không gọi mạng)

1. **Chọn điểm:** giữ luật hiện tại, gần mốc trước rồi rẻ hơn, lấy đủ số chỗ. Sau đó cải thiện: thử đổi một điểm đã chọn
   với một điểm bị bỏ có cùng mức ưu tiên nguồn; nếu chi phí giảm từ 2 km trở lên thì nhận phép đổi.
2. **Một khách sạn:** với mỗi khách sạn ứng viên, ghép các điểm thành từng ngày bằng ghép cặp chi phí nhỏ nhất. Giải
   chính xác bằng quy hoạch động trên tập con: tối đa 2¹⁴ trạng thái.
3. **Nhiều khách sạn** (khi được phép): với mỗi cách ghép ngày và mỗi thứ tự ngày, chọn chuỗi khách sạn bằng quy hoạch
   động theo ngày (đường ngắn nhất, có trạng thái "đã đổi chưa"). Lặp xen kẽ bước 2 và bước 3 tới khi không giảm nữa.
4. **Ràng buộc giữ nguyên:**
   - giờ bay (AC-AGT-02);
   - hoạt động cả ngày đứng riêng;
   - tối đa 2 điểm mỗi ngày;
   - nguồn Search trước Recommendation;
   - không chọn cả sản phẩm lẫn sản phẩm cha.
5. **Hoà:** phá bằng tổng tiền, rồi `productId`, để cùng ứng viên luôn ra cùng một lịch.

### Tiền và hiển thị

- Mỗi khách sạn tính `giá/đêm × số đêm ở khách sạn đó`. Tổng số đêm vẫn là `max(1, days − 1)`.
- Lịch hiện danh sách khách sạn theo đêm, ví dụ "Đêm 1–2: Khách sạn A · Đêm 3: …". Câu trả lời nói rõ vì sao đổi.

## Ngoài phạm vi

- Chặng sân bay ↔ khách sạn. Cần bảng toạ độ sân bay, sẽ có đề xuất riêng.
- Quãng đường đường bộ thật (OSRM) và hiện km/phút.
- Nâng hạng khách sạn theo ngân sách.

## Thay đổi source sau khi chốt

- **Contract**, cộng thêm và giữ tương thích ngược, `openapi.yaml` 1.18.0 → 1.19.0:
  - `ItineraryPlan.stays[]` (mới), mỗi mục gồm `product`, `fromNight`, `nights`, `note`, `source`, `because`;
  - `stay` giữ nguyên, bằng khách sạn đầu tiên, để client cũ vẫn chạy;
  - mock `src/shared/mocks/itinerary-agent/completed.json`.
- **Domain:**
  - `src/backend/app/domain/itinerary/geo.py`: hàm chi phí của chuyến;
  - file mới `src/backend/app/domain/itinerary/routing.py`: ghép cặp, quy hoạch động chọn khách sạn;
  - `planning.py`: `compose_plan`, `render_proposal`, `totals` và `validate_plan` hỗ trợ nhiều khách sạn. Thêm `NOTES` cho
    dòng đổi khách sạn.
- **Agent:**
  - `agents/steps/composition.py`, `narration.py`, `messages.py`, `prompts.py`: câu tiêu chí khi đổi khách sạn, mục nơi nghỉ
    theo đêm;
  - `missing_stay_note` không đổi.
- **Widget:**
  - `src/frontend/src/features/itinerary/widget/` (`widgetTypes.ts`, `widgetPlan.ts`, `WidgetPlanPanel.tsx`) hiện danh
    sách khách sạn theo đêm;
  - không có `stays` thì đọc `stay` như cũ.
- **Test:**
  - unit cho hàm chi phí, ghép cặp, chọn chuỗi khách sạn và các ràng buộc;
  - so sánh với lời giải vét cạn trên bộ nhỏ;
  - test tương thích client cũ (chỉ đọc `stay`);
  - `validate_contract.py`.
- **Spec:**
  - `docs/spec/agent/nghiep-vu/xep-lich.md`;
  - `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7 và §4.2;
  - `docs/spec/hop-dong-tich-hop-frontend.md` (hiển thị nhiều khách sạn).
- **Đo kiểm:** report trong `src/evaluation/reports/`, so luật AC-AGT-04 hiện tại với bản tối ưu trên snapshot catalog:
  - km/chuyến;
  - tiền;
  - tỉ lệ chuyến có đổi khách sạn.
