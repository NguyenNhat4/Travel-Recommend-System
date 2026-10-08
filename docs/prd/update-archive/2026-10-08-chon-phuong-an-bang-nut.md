# Chọn "Phương án khác" bằng một lần bấm, đổi lịch tức thì

- Ngày: 2026-10-08
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-08
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-05, FR-AGT-04, NFR-REL-01, AC-AGT-04

## Lý do

1. **Chậm.** Trace LangSmith ngày 08/10/2026 (hội thoại "di hcm 3 ngay 2 dem 2 vo chong 1 dua" → "di ngay 15"): một lượt
   lập lịch mất 16,5 s — phân luồng 1,7 s, trích ý định 2,9 s, lập tool plan 4,1 s, xếp lịch 0,01 s, viết lời 7,4 s.
   Nhắn "lấy phương án 1" hiện đi lại gần đủ chừng ấy bước (trích ý định, lập tool plan, tìm lại, viết lại toàn bộ lịch),
   dù lịch của phương án đã được tính xong ở lượt trước.
2. **Không giữ lời.** Vì tìm lại từ đầu, lịch nhận được có thể khác lịch đã báo: chênh tiền, chênh km trong mục "Phương án
   khác" không còn đúng.
3. **Khó dùng.** Người dùng phải gõ đúng câu "lấy phương án 1". Một nút bấm cạnh từng phương án nhanh và rõ hơn.

## Nội dung đề xuất

### `docs/prd/requirements.md` §3, AC-AGT-04

Hiện tại:

> Người dùng chọn phương án bằng lượt nhắn tiếp theo.

Thay bằng:

> Mục "Phương án khác" hiện trong câu trả lời của trợ lý dưới dạng **một hàng thẻ khách sạn lướt ngang**, gồm 3–4 thẻ: thẻ
> đầu là khách sạn của lịch đang chọn (nhãn "Đang chọn", tổng km cả chuyến), các thẻ sau là phương án khác. Mỗi thẻ ghi
> đánh đổi so với lịch đang chọn: chênh tiền, chênh km, vượt ngân sách bao nhiêu (nếu có). Bấm vào một thẻ thì bảng lịch
> trình bên phải hiện ngay lịch của phương án đó kèm bản đồ (khách sạn và các điểm theo ngày), chưa đổi lịch đã lưu. Người
> dùng chọn phương án bằng nút "Dùng phương án này" trên thẻ hoặc trên bảng lịch, hoặc nhắn "lấy phương án N" / tên khách
> sạn. Khi chọn đúng một phương án đã hiện, lịch đổi đúng như
> phương án đã báo (cùng khách sạn, cùng chênh tiền và chênh km), không tìm lại sản phẩm; câu trả lời chỉ nêu ngắn phần
> thay đổi, kèm hàng thẻ mới, trong đó khách sạn vừa bỏ thành một thẻ để quay lại được. Mục tiêu thời gian phản hồi của
> lượt chọn: dưới 3 giây.

Phần còn lại của AC-AGT-04 giữ nguyên (tối đa 3 phương án, chỉ hiện phương án chênh từ 2 km trở lên). Khi không đủ phương
án chênh từ 2 km, hàng thẻ ít hơn 3 thẻ; không có phương án nào thì không hiện hàng thẻ. Nhắn đổi khách sạn bằng câu khác
(không phải chọn một phương án đã hiện) vẫn đi luồng lập lịch thường.

### Giao diện hàng thẻ (để review, không phải nội dung PRD; số trong mockup chỉ minh hoạ)

```
Phương án khác · lướt để so ──────────────────────────────────────────►
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐ ┌──────
│ [ảnh]  ĐANG CHỌN  │ │ [ảnh]             │ │ [ảnh]             │ │ [ảnh]
│ Hoang Long Son 2  │ │ Somerset HCMC     │ │ Hotel Sunny Saigon│ │ …
│ ★★★ · 341.000 ₫/đ │ │ ★★★★ · 3,01 tr/đ  │ │ ★★ · 152.000 ₫/đ  │ │
│ 33,1 km cả chuyến │ │ +5,3 tr · −6,2 km │ │ −0,4 tr · +9,2 km │ │
│                   │ │ ⚠ vượt NS 1,2 tr  │ │                   │ │
│   (đang dùng)     │ │   [ Chọn ]        │ │   [ Chọn ]        │ │
└───────────────────┘ └───────────────────┘ └───────────────────┘ └──────
```

- Lướt ngang bằng tay trên điện thoại, mũi tên trái/phải trên máy tính; mỗi thẻ dừng gọn (scroll-snap).
- Chip tiền xanh khi rẻ hơn, cam khi đắt hơn; chip km xanh khi đi ít hơn; vượt ngân sách là nhãn đỏ.
- **Bấm thẻ = xem trước, tức thì, không gọi server.** Thẻ được viền nổi; bảng lịch bên phải đổi sang lịch của phương án
  đó (khách sạn từng đêm, các ngày, tổng tiền) và bản đồ hiện có (`ItineraryMap`) vẽ khách sạn mới cùng các điểm theo
  ngày. Đầu bảng có dải "Đang xem phương án N · +X ₫ · −Y km" với hai nút "Dùng phương án này" và "Quay lại lịch đang
  chọn". Bấm thẻ "Đang chọn" cũng quay lại.

```
┌─ Chat ───────────────────────────┐ ┌─ Lịch trình ─────────────────────────────────┐
│ … câu trả lời của trợ lý …       │ │ Đang xem phương án 1 · +5,3 tr · −6,2 km     │
│ [Đang chọn] [▣ Somerset] [Sunny] │ │ [ Dùng phương án này ]  [ Quay lại ]         │
│     ▲ thẻ đang xem viền nổi      │ │ ┌──────────── bản đồ ──────────────┐         │
│                                  │ │ │  🏨 Somerset   ①─②  ③─④  ⑤─⑥     │         │
│                                  │ │ └──────────────────────────────────┘         │
│                                  │ │ Ngày 1 · …   Ngày 2 · …   Ngày 3 · …        │
└──────────────────────────────────┘ └──────────────────────────────────────────────┘
```

- Bấm "Dùng phương án này": nút hiện đang áp dụng, các thẻ khác tạm khoá; tin nhắn người dùng hiện "Chọn phương án N ·
  <tên khách sạn>"; lịch đã lưu đổi sang phương án đó (giỏ hàng, nút đặt dùng lịch mới).
- Chỉ hàng thẻ của câu trả lời mới nhất bấm được; hàng thẻ ở các câu trả lời cũ chỉ để xem.
- Tên, ảnh, sao, giá lấy từ sản phẩm đã trả về (grounding); chênh tiền và km do code tính.

### Grounding (FR-AGT-04, NFR-REL-01) không đổi

Lịch của từng phương án vẫn do luật tất định dựng ở lượt trước, từ đúng các sản phẩm Search/Recommendation đã trả về, và
đã qua kiểm tra như lịch chính. Lượt chọn chỉ lấy lịch đó ra; LLM chỉ viết lời ngắn, không thêm sản phẩm hay con số.

## Thay đổi source sau khi chốt

- Contract (thêm field, không phá v1): `src/shared/contracts/schemas/itinerary-agent.yaml`
  - response lịch trình có thêm `stayOptions` (khách sạn theo đêm, chênh tiền, chênh km, vượt ngân sách, và lịch đầy đủ
    của phương án — cùng hình dạng `itinerary` — để bảng bên phải xem trước không cần gọi server);
  - request có thêm `selectStayOption: {index}` (cần `conversationId`, không cần `message`), như `intentOverride`.
- Backend: `src/backend/app/domain/itinerary/routing.py`, `planning.py` (giữ lịch đã giải của từng phương án);
  `src/backend/app/agents/` — node mới `apply_option` (intake → apply_option → narrate → finalize), narrate chế độ ngắn,
  lưu lịch từng phương án vào hội thoại.
- Frontend: `src/frontend/src/features/itinerary/widget/` — component hàng thẻ lướt ngang (`WidgetStayOptions.tsx`) trong
  tin nhắn của trợ lý, panel lịch cập nhật ngay khi chọn; câu chữ "Phương án khác … nhắn lấy phương án 1" trong lời trả
  lời được thay bằng hàng thẻ.
- Spec: `docs/spec/agent/langgraph-nodes.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Test: unit domain/agent, golden case cho lượt chọn phương án, vitest cho widget.
