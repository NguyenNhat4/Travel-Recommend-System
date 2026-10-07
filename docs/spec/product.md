# Product UX Spec — V-OTA Travel Recommendation Demo

**Đặc tả UX cho workstream Web** · Căn cứ: `spec/recsys-internship-handbook-v3-vi.md` (gọi tắt: *handbook*) và `spec/ux-research-brief.md`
Ngày nghiên cứu: 16/09/2026 · Nguồn pattern: MCP Mobbin (web + iOS)

> **Mốc đối chiếu frontend: 21/09/2026.** §1.5 ghi nhận trạng thái theo mã nguồn. Chưa xác minh runtime. §3–§7 mô tả UX mục tiêu, trừ phần được ghi rõ là hiện trạng.

---

## 0. Cách đọc tài liệu này

- **Mọi pattern tham chiếu** được đánh mã `[Rxx]`. Bảng đầy đủ (app, nền tảng, màn hình, link Mobbin) nằm ở **§8**. Trong thân bài, mỗi mã đi kèm tên app và màn hình để đọc được mà không cần tra bảng.
- **"Đề xuất"** = quyết định UX của tài liệu này. **"Phụ thuộc"** = điểm cần đối chiếu khi tích hợp; các câu hỏi tại thời điểm soạn spec nằm ở **§9**. Contract hiện hành theo OpenAPI.
- Tên trường dữ liệu (`because`, `strategy`, `unitPrice`…) lấy đúng theo handbook §6–§7. Tài liệu này **không** đề xuất đổi schema hay engine. Chỗ nào UI cần thêm dữ liệu thì ghi là phụ thuộc.
- Chuỗi hiển thị (copy) viết bằng tiếng Việt, đặt trong ngoặc kép, dùng được ngay.
- §1.5 phân biệt **đã có trong code** với **UX mục tiêu/chưa xác minh runtime**. Route, client wrapper hoặc API proxy không tự xác nhận luồng đã chạy với Backend.

---

## 1. Tổng quan & phạm vi

### 1.1 Sản phẩm phải chứng minh điều gì

Theo handbook §2 và §8, bản demo thắng hay thua ở ba khoảnh khắc. UX được thiết kế quanh ba khoảnh khắc này, không quanh "một OTA đầy đủ":

| # | Khoảnh khắc demo | Màn hình gánh | UX phải làm cho nó *nhìn thấy được* |
|---|---|---|---|
| K1 | **Vòng lặp phản hồi:** đặt khách sạn Nha Trang → gợi ý chuyển sang vé máy bay / vé tham quan | Checkout → Confirmation → Home | Ngay trên trang Confirmation đã có gợi ý mới. Home có section "Hoàn thiện chuyến Nha Trang" kèm lý do và một thông báo "trang chủ đã cập nhật" |
| K2 | **Cá nhân hóa theo người:** đăng nhập lần lượt 4 tài khoản seed → Home khác nhau | Login → Home | Đăng xuất rồi đăng nhập bằng email seed qua `/login` thật. Tiêu đề section và dòng lý do khác nhau rõ rệt giữa các persona |
| K3 | **Trợ lý không bịa:** hỏi lịch trình 3 ngày → kế hoạch toàn sản phẩm thật → bấm vào → đặt được | Chat → Detail/Cart | Mọi mục đặt được đều là thẻ sản phẩm có giá và nút. Mục không phải sản phẩm trông khác hẳn và không có nút đặt |

### 1.2 Trong phạm vi

8 màn hình theo handbook §4: Home (cá nhân hóa), Search, Product detail, Cart, Checkout, Confirmation, Login/Register và Chat assistant. Phạm vi assistant gồm nhập yêu cầu bằng giọng nói, thời tiết, lưu/chia sẻ lịch trình và chế độ bản đồ theo UX mục tiêu. Hiện trạng từng phần xem §1.5.

### 1.3 Ngoài phạm vi (theo handbook §2, §8 và brief §5)

- Thanh toán tiền thật, Stripe live mode, form thẻ tự dựng, ví điện tử và chuyển khoản. Checkout thu tiền qua **Stripe Checkout ở test mode** (trang nhập thẻ do Stripe host, V-OTA là Merchant of Record — FR-BKG-06); V-OTA không vẽ form thẻ.
- OAuth/đăng nhập mạng xã hội, xác minh email, **quên/đặt lại mật khẩu**, 2FA, phân quyền. UI **không hiển thị** link "Quên mật khẩu" hay nút "Đăng nhập với Google" dù mọi OTA tham chiếu đều có.
- Đánh giá chi tiết của người dùng (handbook §3 cấm thu review), wishlist và chat nhóm. Bản đồ, lưu và chia sẻ lịch trình thuộc UX scope; trạng thái code hiện tại xem §1.5.
- Thu thập phản hồi trên gợi ý kiểu "Không quan tâm" hay "Thêm như này" `[R107]`: không có API ghi, nên không đưa vào MVP. Có thể đưa vào đề xuất Tuần 6.

### 1.4 Nguyên tắc thiết kế xuyên suốt

1. **Lý do trước, điểm số sau.** Người dùng cuối thấy lý do bằng lời. `score` và `contribution` chỉ hiện ở chế độ demo/chẩn đoán (§5.6). Cosine 0,81 không phải "81% phù hợp", nên không được trình bày như xác suất (khác với `[R21]` Lovi "86% fit").
2. **Đặt được thì trông đặt được, không đặt được thì không.** Cả giao diện chỉ có một component thẻ sản phẩm có nút CTA, và nó chỉ render từ một `productId` thật (§6.4).
3. **Trung thực khi không cá nhân hóa được.** Cold start thì ghi "Phổ biến tại…", không giả vờ "Dành riêng cho bạn".
4. **Suy giảm êm ái.** LLM lỗi thì hiện kết quả tìm kiếm. Gợi ý lỗi thì hiện danh mục phổ biến. Không bao giờ để trang trắng.
5. **Một component, ba khuôn mặt.** "Một engine, ba khuôn mặt" của handbook §1 ứng với một bộ `ProductCard` + `BecauseLine` dùng chung ở Home, Search, Detail, Cart, Confirmation và Chat.

### 1.5 Tình trạng frontend hiện tại (21/09/2026)

Các trạng thái dưới đây được đối chiếu tĩnh với mã trong `src/frontend`; đây không phải kết quả chạy ứng dụng hay kiểm thử end-to-end.

| Khu vực | Hiện trạng trong code | Contract và giới hạn tích hợp |
|---|---|---|
| Home, Search, Product detail | Route hiện render trạng thái **API chưa khả dụng**. | Có client wrapper theo OpenAPI; các page chưa gọi operation catalog/search/recommendation. Không hiển thị dữ liệu nghiệp vụ giả. |
| Cart, Checkout, Confirmation | Route hiện render trạng thái **API chưa khả dụng**; form thao tác bị khóa. | Client wrapper khai báo operation cart/booking; page chưa gọi các operation này. Bật operation ở client không tự mở các route này. Chưa xác minh Backend runtime. |
| Login/Register | Route hiện render trạng thái **API chưa khả dụng**; form bị khóa. | Client wrapper khai báo operation auth; page chưa gọi operation đăng nhập/đăng ký. Persona demo không còn được dùng tại các route này. |
| Assistant | `/assistant` đọc trạng thái và gửi yêu cầu itinerary qua client contract; widget nổi gọi operation tạo itinerary. Kết quả render theo status của response. | Client dùng `/api/v1/assistant/status`, `/api/v1/assistant/itineraries/stream` và `/api/v1/assistant/itineraries`. Operation chỉ được gọi khi có trong `NEXT_PUBLIC_API_OPERATIONS`. Runtime/config chưa được xác minh. |
| Tiện ích Assistant | Có nhập giọng nói, thẻ thời tiết, lưu lịch trình trên thiết bị và tạo liên kết chia sẻ từ dữ liệu itinerary. | Giọng nói dùng Web Speech API; thời tiết gọi Open-Meteo; lưu dùng `localStorage`; query URL chứa dữ liệu itinerary dạng Base64URL. Không thấy chế độ bản đồ trong code hiện tại; bản đồ tại §4/§7 vẫn là UX mục tiêu. |

**Quy tắc đối chiếu:** `NEXT_PUBLIC_API_OPERATIONS` quyết định operation nào được bật ở client. Route proxy `/api/[...path]` chuyển tiếp `/api/v1/*` theo `BACKEND_BASE_URL`; sự hiện diện của proxy không xác nhận Backend đã cấu hình hoặc request thành công.

---

## 2. Personas / tài khoản seed

Đối chiếu handbook §8 ("một khách hay đi Nha Trang, một khách lần đầu, một người ngủ đông sáu tháng, một người hoàn toàn không có lịch sử") và §6 (lifecycle stage, cold start < 3 event, dormant).

| Persona | Tên hiển thị đề xuất | Lịch sử (dữ liệu seed) | Trạng thái engine dự kiến | Home phải thể hiện | Câu thoại demo |
|---|---|---|---|---|---|
| **P1 · Khách Nha Trang** | "Minh Anh · Khách thân thiết" | Nhiều chuyến Nha Trang; có một chuyến sắp tới đã đặt khách sạn | `coldStart: false`, `strategy: "cross_vertical"`, `nextVertical: "flight"` | Section "Hoàn thiện chuyến Nha Trang" + checklist danh mục + dòng `because` trỏ về khách sạn đã đặt | "Chị ấy đã có khách sạn, hệ thống gợi ý vé máy bay chứ không gợi ý thêm khách sạn" |
| **P2 · Khách lần đầu** | "Quốc Bảo · Mới tham gia" | 1–2 event (vài lượt xem) | `coldStart: true` (dưới 3 event) | "Vì bạn vừa xem …" nếu có `because`, còn lại "Phổ biến tại {điểm đến}" | "Mới xem hai lần, gợi ý đã bám theo thứ vừa xem" |
| **P3 · Khách ngủ đông** | "Thu Hà · Đã lâu không ghé" | Chuyến gần nhất cách đây khoảng 6 tháng | Chế độ dormant (handbook §11 Tuần 4) | Lời chào "Chào mừng quay lại" + gợi ý dựa trên chuyến cũ, dòng `because` ghi rõ "6 tháng trước" | "Hệ thống biết sở thích đã cũ và nói rõ điều đó" |
| **P4 · Không lịch sử** | "Khách mới" | 0 event | `coldStart: true`, `because` rỗng | Không có dòng lý do cá nhân. Chỉ có "Điểm đến được đặt nhiều", entry point Trợ lý và Tìm kiếm | "Không biết gì thì không bịa" |
| **Khách vãng lai** | — | Chưa đăng nhập | Không gọi `/recommendations` | Home công khai (phổ biến) + banner mời đăng nhập | — |

**Phụ thuộc:** handbook chỉ minh họa giá trị `strategy: "cross_vertical"`. Các giá trị cho P2/P3/P4 (ví dụ `popular`, `dormant`…) cần Backend chốt. UI map mọi `strategy` lạ về copy chung (§5.3).

Tài khoản seed đăng nhập qua `/login` như mọi user (email seed + mật khẩu demo chung); không có bộ chọn tài khoản trên giao diện (§4.7.3). Người trình bày chuẩn bị sẵn danh sách email.

---

## 3. Information architecture — sơ đồ luồng màn hình

### 3.1 Route và quyền truy cập

| Route | Màn hình | Cần đăng nhập | Ghi chú |
|---|---|---|---|
| `/` | Home | Không (khi đã đăng nhập mới có phần cá nhân hóa) | |
| `/search?q=&taxonomy=&destination=&sort=` | Kết quả tìm kiếm | Không | Route hiện hiển thị trạng thái API chưa khả dụng; page chưa gọi `searchProducts`, xem §1.5 |
| `/hotels`, `/flights`, `/experiences`, `/combos` | Trang danh mục dịch vụ (hero, tấm tìm kiếm, carousel phổ biến và giá tốt, điểm đến) | Không | Nhận `?destination=`; `/experiences` nhận thêm `?type=attraction\|golf`; `/flights` không có khối phổ biến và giá tốt: tìm tại chỗ, chuyến bay hiện dưới tấm tìm kiếm, chưa tìm thì nhắc nhập. Xem frontend §4.1a, §4.1b |
| `/product/:productId` | Chi tiết sản phẩm | Không | |
| `/cart` | Giỏ hàng | **Có** | Có thể bị cắt (handbook §2, mục 4) |
| `/checkout` | Checkout | **Có** | |
| `/booking/:referenceCode` | Xác nhận đặt chỗ | **Có** | |
| `/login`, `/register` | Đăng nhập / Đăng ký | — | Nhận `?redirect=` |

**Đề xuất quyền truy cập:** duyệt, tìm kiếm, xem chi tiết và chat đều mở cho khách vãng lai, vì đây là phần phô diễn search. Thêm giỏ, Đặt ngay và điền thông tin ở trang thanh toán cũng mở cho khách vãng lai (giỏ và đơn nháp của khách giữ 3 ngày, gộp vào tài khoản khi đăng nhập; FR-BKG-01, `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` §8). Chỉ **tạo đơn** mới yêu cầu đăng nhập, vì đơn và event đặt chỗ phải khóa theo `cdp_user_id` (handbook §10): khi khách vãng lai bấm "Thanh toán", UI mở **modal đăng nhập tại chỗ** rồi tự gửi tiếp sau khi đăng nhập, không chuyển trang và không mất thông tin đã nhập. Pattern: `[R77]` Tripadvisor web (modal "Welcome back." phủ lên trang, trang sau vẫn giữ nguyên ngữ cảnh).

### 3.2 Sơ đồ luồng chính

```
                         ┌──────────────── Header toàn cục ────────────────┐
                         │ Logo · [Ô tìm kiếm] · Trợ lý · Giỏ(n) · Tài khoản│
                         └──────────────────────────────────────────────────┘

   ┌─────────┐  gõ truy vấn   ┌──────────┐  bấm thẻ   ┌──────────────┐
   │  HOME   │ ─────────────▶ │  SEARCH  │ ─────────▶ │ PRODUCT      │
   │ (cá nhân│ ◀── logo ───── │ kết quả  │            │ DETAIL       │
   │  hóa)   │                └──────────┘            └──────┬───────┘
   └──┬──┬───┘                     ▲  "Hỏi trợ lý"          │ Thêm vào giỏ / Đặt ngay
      │  │ bấm thẻ gợi ý ──────────┼────────────────────────▶│
      │  │                         │                         ▼
      │  │  "Lên kế hoạch"   ┌─────┴──────┐ bấm thẻ SP  ┌──────────┐ Tiến hành ┌──────────┐
      │  └─────────────────▶ │ ASSISTANT  │ ──────────▶ │   CART   │ ────────▶ │ CHECKOUT │
      │                      │ (chat +    │ Thêm tất cả │ (≥1 mục) │           └────┬─────┘
      │                      │  kế hoạch) │ ──────────▶ └──────────┘                │ Xác nhận
      │                      └────────────┘                                         ▼
      │                            ▲                                        ┌──────────────┐
      │                            └──── "Lên lịch trình cho chuyến này" ── │ CONFIRMATION │
      │                                                                     │ mã tham chiếu│
      └──────────── "Xem trang chủ đã cập nhật" ◀─────────────────────────  │ + gợi ý mới  │
                    (K1: vòng lặp phản hồi)                                 └──────────────┘

   Bất kỳ hành động ghi nào khi chưa đăng nhập ──▶ [Modal Login] ──▶ quay lại đúng chỗ, tiếp tục hành động
```

**Trong code hiện tại:** các route storefront render màn hình API chưa khả dụng; page chưa nối client wrapper để tải dữ liệu. `AppShell` gắn widget trợ lý nổi. Sơ đồ trên đây mô tả UX mục tiêu; contract và giới hạn kết nối xem §1.5.

### 3.3 Điều hướng toàn cục

- **Desktop (≥ 1024 px):** header kính mờ nổi trên hero ở Home và bốn trang danh mục, chuyển nền trắng khi cuộn qua hero; ở route khác là header nền trắng thường. Từ trái sang phải: logo, bốn nhóm dịch vụ **Di chuyển · Lưu trú · Tour và trải nghiệm · Tiện ích khác** (mỗi nhóm mở menu con chỉ liệt kê dịch vụ, không có điểm đến), nút lưới "Tất cả dịch vụ" (từ 1280 px), ngôn ngữ, "Giỏ hàng" (biểu tượng giỏ kèm số mục; bấm mở danh sách tối đa 3 mục giỏ và nút "Xem giỏ hàng", không liệt kê đơn đã đặt), tài khoản (menu có "Chuyến đi & Đặt phòng của tôi" dẫn tới `/profile`). Không còn ô tìm kiếm giữa header (theo wireframe `docs/prd/user-flow.md` §4.1): tìm kiếm nằm ở hero của Home và các trang danh mục, và ở đầu `/search`. Menu là mẫu disclosure (`aria-expanded`, Esc đóng và trả focus, mở bằng rê chuột chỉ trên thiết bị có hover). Cấu hình ở `components/layout/nav/navConfig.ts`. Không có Trợ lý AI trên header (đề xuất `update-archive/2026-09-29-bo-nut-tro-ly-ai-tren-header.md`); trợ lý là widget nổi duy nhất (`update-archive/2026-09-29-gop-giao-dien-tro-ly-ve-widget.md`, không còn route `/assistant`). Điều khiển header cùng cao 40 px, bo tròn; chữ tiêu đề và điều hướng là Cal Sans, nội dung là Inter (`globals.css`). Không còn chuông thông báo và điểm thưởng cứng.
- **Checkout** dùng header rút gọn (logo + "Quay lại giỏ hàng"; thanh toán một đơn nháp của Đặt ngay thì là "Quay lại", về trang trước) để giảm rơi rụng. Pattern: `[R70]` KAYAK web checkout (header chỉ còn logo).
- **Mobile:** thanh tab dưới cùng, xem §7.2.
- **Menu tài khoản:** tên + persona, "Đăng xuất". Không có trang hồ sơ, vì handbook không yêu cầu.
- **Banner demo** mảnh, cố định dưới header: "Bản demo — không thu tiền và không gửi xác nhận thật." Người dùng đóng được, lựa chọn lưu theo phiên.

---

## 4. Đặc tả từng màn hình

### 4.0 Thành phần dùng chung

Mọi màn hình dưới đây đều tham chiếu tới các component này. Định nghĩa một lần để Home, Search, Chat trông thống nhất.

| Component | Dữ liệu | Quy tắc |
|---|---|---|
| **`ProductCard`** (biến thể `grid` / `row` / `compact`) | `imageUrl`, `name`, `taxonomy`, `destination`, `attributes.starRating`, `unitPrice` hoặc `priceString`, `available` | `grid` cho carousel/lưới, `row` cho danh sách kết quả desktop, `compact` cho chat và giỏ. Cả thẻ là một link tới `/product/:id`. Nút phụ (nếu có) không được làm thẻ mất khả năng bấm. `available: false` thì ảnh xám, nhãn "Tạm hết chỗ", ẩn nút đặt |
| **`TaxonomyBadge`** | `taxonomy` | `hotel` "Khách sạn" · `flight` "Vé máy bay" · `attraction` "Vé tham quan" · `combo` "Combo" · `golf` "Golf". Mỗi loại có icon + màu riêng, chỉ dùng ở giỏ hàng và checkout (nơi trộn nhiều loại); thẻ sản phẩm và trang chi tiết không hiện vì đã có danh mục/tab theo loại |
| **`PriceTag`** | `unitPrice`, `currency` | Định dạng `vi-VN`: "1.890.000 ₫". Tiền tố "Từ" khi giá phụ thuộc lựa chọn. Hậu tố đơn vị: "/ đêm" (hotel), "/ khách" (flight, attraction), "/ gói" (combo). Pattern hậu tố + ghi chú thuế: `[R31]` Klook web ("incl. taxes per night") |
| **`BecauseLine`** | `because[0]` | Một dòng dưới tên sản phẩm, xem §5.2 |
| **`WhyPopover`** | toàn bộ `because[]`, `strategy`, `destination` | Nút "Vì sao?" mở popover (desktop) hoặc bottom sheet (mobile), xem §5.4 |
| **`SectionHeader`** | tiêu đề + phụ đề lý do + "Xem tất cả" | Phụ đề là câu lý do cấp section. Pattern: `[R13]` Booking.com iOS "Stays in Tokyo / Suggestions based on your recent search", `[R03]` Tripadvisor web "We think you'd enjoy these homes…" |
| **`Skeleton`** | — | Giữ đúng khung hình của nội dung thật (ảnh + 3 dòng + ô giá). Pattern: `[R42]` Navan web (skeleton thẻ khách sạn), `[R44]` Airbnb web (lưới skeleton), `[R45]` Klook web (skeleton trang chủ theo section) |
| **`EmptyState`** | icon + tiêu đề + 1 câu + 1–2 CTA + (tùy chọn) nội dung thay thế | Luôn đưa ra bước tiếp theo, không bao giờ chỉ ghi "Không có dữ liệu" |
| **`ErrorState`** | thông điệp + "Thử lại" | Lỗi cục bộ theo section không làm hỏng cả trang. Pattern: `[R114]` Typeform web ("Oops! Something went wrong" + Retry / Start over) |
| **`Toast`** | chuỗi ngắn + hành động (tùy chọn) | Góc dưới, tự ẩn sau 5 giây. Dùng cho "Đã thêm vào giỏ", "Trang chủ đã cập nhật…" |

---

### 4.1 Home (cá nhân hóa)

**Mục đích:** gánh K1 và K2. Đây là màn hình được mở lại nhiều nhất trong buổi demo.

#### 4.1.1 Bố cục desktop (đã đăng nhập, P1)

```
┌ Header ─────────────────────────────────────────────────────────────────────────┐
├─────────────────────────────────────────────────────────────────────────────────┤
│ Chào Minh Anh 👋                                                                  │
│ ┌ Ô tìm kiếm lớn ──────────────────────────────────────────────┐ [Tìm]            │
│ │ Thử: "nghỉ dưỡng biển cho gia đình"                           │                  │
│ └───────────────────────────────────────────────────────────────┘                  │
│ Chip gợi ý: [Nha Trang] [Phú Quốc] [Vé VinWonders] [Combo gia đình]               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ① HOÀN THIỆN CHUYẾN NHA TRANG CỦA BẠN                          [Vì sao?]          │
│   Bạn đã đặt khách sạn — còn thiếu vé máy bay và vé tham quan                     │
│   Checklist: [✓ Khách sạn] [○ Vé máy bay] [○ Vé tham quan]                         │
│   ┌card┐ ┌card┐ ┌card┐                                                             │
│   │img │ │img │ │img │   mỗi card: Badge · Tên · Giá · BecauseLine                 │
│   └────┘ └────┘ └────┘                                                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ② Tiếp tục khám phá   (sản phẩm đã xem gần đây — tùy chọn, xem 4.1.3)             │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ③ [Thẻ Trợ lý] Cần lên lịch trình Nha Trang? "Lên kế hoạch 3 ngày" →              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ④ Phổ biến tại các điểm đến Việt Nam  (catalog công khai — luôn có)               │
│   Tabs danh mục: Tất cả · Khách sạn · Vé máy bay · Vé tham quan · Combo           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 4.1.2 Thành phần và dữ liệu

| Khu vực | Nội dung | Nguồn dữ liệu | Pattern tham chiếu |
|---|---|---|---|
| Lời chào + tìm kiếm | "Chào {tên}", ô tìm kiếm có placeholder ví dụ bằng ngôn ngữ tự nhiên, 4 chip gợi ý truy vấn | tên từ phiên đăng nhập, chip là danh sách tĩnh | `[R16]` Nike iOS ("Good Morning, Alex" trên "Top Picks for You"); `[R35]` Booking.com iOS AI search ("Try these out:" + thẻ câu mẫu) |
| **① Section cá nhân hóa chính** | Tiêu đề và phụ đề sinh theo `strategy` (bảng §5.3). Checklist danh mục của chuyến. 3–5 `ProductCard` kèm `BecauseLine`. Nút "Vì sao?" ở cấp section | `GET /recommendations?k=5` → `strategy`, `nextVertical`, `destination`, `recommendations[]`, `diagnostics.excludedVerticals` (danh mục đã có ✓) | Cross-sell theo chuyến: `[R09]` Booking.com iOS ("Getting to your stay" / "Add more to your trip"), `[R10]` Agoda iOS ("Missing anything for your trip?"), `[R11]` Qantas iOS ("Consider for your trip: Book a hotel / Hire a car"). Checklist tiến độ: `[R12]` Trip.com iOS ("Plan Your Entire Trip to Ho Chi Minh City — Book 1/6") |
| ② Tiếp tục khám phá | Tối đa 6 sản phẩm đã xem gần nhất | **Phụ thuộc:** chưa có endpoint. Nếu không có thì bỏ section | `[R08]` Airbnb iOS ("Continue searching for experiences in Miami" + "Recently viewed homes"); `[R02]` KAYAK web ("Your recent searches") |
| ③ Thẻ Trợ lý | "Cần lên lịch trình {destination}?" + nút "Lên kế hoạch cùng trợ lý". Bấm vào mở `/assistant` với prompt điền sẵn | `destination` từ `/recommendations`. Khi không có thì dùng "Lên kế hoạch chuyến đi tiếp theo" | `[R14]` Booking.com iOS ("Need help planning your next trip? — Build me an itinerary"); `[R05]` Mindtrip web (trang chủ lấy chat làm trung tâm) |
| ④ Phổ biến | Carousel theo danh mục (tab). **Luôn render**, kể cả khi ① lỗi, để trang không bao giờ trống | **Phụ thuộc:** endpoint phổ biến / baseline most-popular (có sẵn ở Evaluation) | `[R01]` Klook web ("Best on Klook" chia 3 cột xếp hạng 1-2-3); `[R04]` Kiwi.com web ("Our top deals for tonight" + chip lọc thành phố); `[R06]` Airbnb web (các hàng "Popular homes in Paris") |

#### 4.1.3 Biến thể theo persona / trạng thái

| Trạng thái | Section ① hiển thị | Ghi chú |
|---|---|---|
| P1 · `cross_vertical` | "Hoàn thiện chuyến {destination} của bạn" + checklist + `BecauseLine` | Khoảnh khắc K1 |
| P2 · cold start, có `because` | "Gợi ý từ những gì bạn vừa xem" + `BecauseLine` "Vì bạn đã xem …" | |
| P2/P4 · cold start, `because` rỗng | "Phổ biến tại {destination}" hoặc "Được đặt nhiều trên V-OTA". **Không** có `BecauseLine` cá nhân. Nhãn trên thẻ: "Được đặt nhiều" | Nguyên tắc 1.4-3 |
| P3 · dormant | Lời chào đổi thành "Chào mừng quay lại, {tên}". Phụ đề: "Dựa trên chuyến {destination} của bạn cách đây {n} tháng" | `daysAgo` lớn hiển thị theo tháng (§5.2) |
| Khách vãng lai | Không có ①. Thay bằng banner: "Đăng nhập để nhận gợi ý theo chuyến đi của bạn" + [Đăng nhập] [Đăng ký] | `[R82]` Skyscanner iOS ("Get the full experience — Track prices, make trip planning easier"); `[R81]` Best Buy iOS (danh sách lợi ích trước khi đăng nhập) |

#### 4.1.4 Khoảnh khắc "trang chủ đã cập nhật" (K1)

Khi người dùng quay về Home từ Confirmation (bấm "Xem gợi ý mới trên trang chủ"):

1. Home **luôn gọi lại** `/recommendations`, bỏ qua cache phía client. Điều kiện kích hoạt: có cờ `justBooked` trong state điều hướng.
2. Section ① có viền nhấn và nhãn "Mới cập nhật" trong 10 giây.
3. Toast: "Trang chủ đã cập nhật theo chuyến {destination} của bạn". Pattern: `[R15]` Best Buy iOS (toast "Got it! Your home page is updating based on your interests." hiện ngay trên các section "Related to your top categories") và `[R23]` Instagram iOS (toast xác nhận thay đổi thuật toán "We'll show you more reels on Art").
4. Nếu `strategy` sau khi đặt chưa đổi (engine chưa cập nhật kịp) thì **không** hiện toast. UI không được tuyên bố một thay đổi không có thật.

#### 4.1.5 Trạng thái

| Trạng thái | Hành vi |
|---|---|
| Đang tải | Lời chào + ô tìm kiếm render ngay. Section ① hiện skeleton 4 thẻ + skeleton tiêu đề. Section ④ tải song song và độc lập. Pattern: `[R45]` Klook web |
| Lỗi `/recommendations` (5xx, timeout > 3 giây) | Ẩn section ①, không hiện lỗi to. Hiện một dòng nhỏ "Chưa tải được gợi ý cho bạn · [Thử lại]" phía trên ④ |
| 401 (JWT hết hạn) | Modal "Phiên đăng nhập đã hết hạn" → đăng nhập lại → ở nguyên Home (§4.7.5) |
| `recommendations: []` | Xử lý như cold start không `because` (4.1.3) |
| Sản phẩm trong gợi ý có `available: false` | Không render thẻ. Nếu còn dưới 3 thẻ thì ẩn carousel và chỉ giữ tiêu đề + CTA "Tìm {nextVertical} đi {destination}" → `/search` |

---

### 4.2 Search / kết quả tìm kiếm

**Mục đích:** phô diễn semantic search ("nghỉ dưỡng biển cho gia đình" vẫn ra kết quả dù không trùng từ, handbook §1 và §11 Tuần 2).

#### 4.2.0 Kết quả vé máy bay (`/flights?origin&destination`)

Bố cục theo bản mẫu đã duyệt, ngay trên `/flights` (tìm không chuyển trang; chưa nhập thì bên dưới chỉ có lời nhắc nhập): hero và tấm tìm kiếm ở trên, bên dưới là ba cột. Trái: **Bộ lọc** (thời gian khởi hành theo buổi Sáng · Trưa · Chiều · Tối · Khuya, hãng hàng không, điểm dừng, "Đặt lại"). Giữa: tiêu đề "Chọn vé chiều đi" / "Chọn vé chiều về", popup sắp xếp, **dải ngày có chuyến kèm giá thấp nhất mỗi ngày**, danh sách thẻ chuyến bay (giờ đi, giờ đến, hãng, thời lượng, hạng vé, giá "/ khách", nút Chọn, mũi tên mở hành trình và hạng vé). Phải: **Vé của tôi** (chiều đi, chiều về, tổng ước tính, nút Đặt vé). Dưới 1280 px cột phải lên trên cùng; dưới 768 px bộ lọc gập lại. Chi tiết dữ liệu và quy tắc: frontend §4.1b.

#### 4.2.1 Ô tìm kiếm (header + Home)

- Ở Home, `/search` và header trang chi tiết chỉ có **một ô nhập tự do**, không tách thành Điểm đến / Ngày / Khách, vì engine nhận `q` tự do. Ngoại lệ: **tấm tìm kiếm ở hero trang danh mục** (`/hotels`, `/flights`, `/experiences`, `/combos`) tách Địa điểm / Ngày / Số khách theo FR-SRC-03; ngày và số khách là ngữ cảnh chuyến đi điền sẵn hộp đặt, không lọc phòng trống (frontend §4.1a). Placeholder xoay vòng giữa các câu mẫu: "nghỉ dưỡng biển cho gia đình", "vé tham quan cho trẻ nhỏ ở Phú Quốc", "khách sạn 5 sao gần biển Đà Nẵng".
  Pattern: `[R35]` Booking.com iOS (tab "AI search": "Search in your own words ⓘ" + thẻ ví dụ "Try these out"). `[R37]` cho thấy chính Booking.com đặt tab "AI search" song song tab "Destination".
- **Khi focus (ô rỗng):** dropdown gồm "Tìm kiếm gần đây" (lưu `localStorage` khoá `vota_recent_searches`, tối đa 5, có nút Xóa) và "Từ khoá phổ biến" (danh sách cố định `POPULAR_KEYWORDS` ở `features/search/instant/recentSearches.ts`). Không gọi API. Pattern: `[R38]` Skyscanner iOS ("Recent searches" + "Popular destinations").
- **Khi đang gõ (FR-SRC-05, đề xuất `update-archive/2026-10-05-goi-y-tuc-thi-o-tim-kiem.md`):** gợi ý tức thì, không cần Enter, ở ô hero Home và ô đầu `/search`. Chia theo loại (điểm đến · khách sạn · vé tham quan · sân golf · combo; **không có vé máy bay**), mỗi dòng có icon, tên loại và phần chữ khớp in đậm (khớp đầu từ, không phân biệt dấu và hoa thường), tối đa 8 dòng, cuối là nút "Xem tất cả kết quả cho "…"" → `/search?q=…`. Chọn điểm đến hoặc từ khoá → `/search?q=<nhãn>`; chọn sản phẩm → `/product/{id}`. Gợi ý lấy từ `GET /search/suggestions` (khớp chữ trên catalog, không embed, không ghi event), không phải từ `POST /search`.
  - Kiểm soát lượt gọi (`features/search/instant/useInstantSearch.ts`): chỉ gọi khi có ≥ 2 ký tự chữ/số; chờ 200 ms sau phím cuối; phím mới huỷ lượt đang bay; bộ nhớ đệm theo khoá đã bỏ dấu (tối đa 50 khoá, 5 phút); lỗi thì hiện "Chưa tải được gợi ý" và vẫn giữ nút "Xem tất cả".
  - Bàn phím: ↑ ↓ chọn, Enter trên dòng đang chọn thì đi tới dòng đó, Enter khi chưa chọn thì tìm như cũ, Esc đóng. ARIA combobox/listbox.
- Nhấn Enter → `/search?q=…`. Truy vấn giữ lại trong ô ở trang kết quả. Tìm bằng Enter, nút "Xem tất cả", chip, giọng nói hoặc chọn điểm đến đều được ghi vào "Tìm kiếm gần đây"; mở một sản phẩm thì không.

#### 4.2.2 Bố cục desktop

```
┌ Header (ô tìm kiếm chứa truy vấn hiện tại) ───────────────────────────────────┐
├───────────────────────────────────────────────────────────────────────────────┤
│ Kết quả cho "nghỉ dưỡng biển cho gia đình"                     48 sản phẩm   │
│ Tabs: [Tất cả 188] [Lưu trú 128] [Tour và trải nghiệm 49] [Tiện ích khác 11] │
├──────────────┬────────────────────────────────────────────────────────────────┤
│ (chỉ tab     │ Đang lọc: (Lưu trú) (Nha Trang ×) (4★+ ×)   [Sắp xếp: Phù hợp ▾]│
│  Lưu trú)    │ ┌ row card ────────────────────────────────────────────────┐   │
│ BỘ LỌC       │ │ [ảnh]  Badge · ★★★★★                          3.400.000 ₫│   │
│ Hạng sao     │ │        Vinpearl Resort Nha Trang - Deluxe Ocean  / đêm   │   │
│ ☐ 5★ ☐ 4★    │ │        📍 Nha Trang                                      │   │
│ Khoảng giá   │ │        [Hướng biển] [Phù hợp gia đình] [Hồ bơi]  [Xem →] │   │
│ [──●────●─]  │ └──────────────────────────────────────────────────────────┘   │
│              │ … 20 kết quả / trang · [Xem thêm]                              │
│              │ ┌ Thẻ trợ lý ─────────────────────────────────────────────┐    │
│              │ │ Muốn ghép thành lịch trình? [Hỏi trợ lý với truy vấn này]│    │
└──────────────┴────────────────────────────────────────────────────────────────┘
```

Tab **Tất cả** không có thanh bên và không có sắp xếp: ba hàng theo nhóm (Lưu trú, Tour và trải nghiệm, Tiện ích khác), mỗi hàng cuộn ngang 6 mục đầu, nút trái/phải ở giữa hai bên hàng (ẩn ở đầu/cuối), thẻ cuối hàng "Còn N kết quả · Xem tất cả". Xem frontend §4.2.

#### 4.2.3 Thành phần và dữ liệu

| Thành phần | Chi tiết | Nguồn | Pattern |
|---|---|---|---|
| Dòng truy vấn | "Kết quả cho "{q}"" + tổng số | `GET /search?q=` | `[R29]` Tripadvisor web ("8,423 properties in Rome") |
| Tab nhóm | Tất cả · Lưu trú · Tour và trải nghiệm · Tiện ích khác, đếm theo `facets.taxonomy` (không tính vé máy bay). Tab 0 kết quả vẫn hiện | một request `limit: 1` không lọc taxonomy | `[R31]` Klook web (bộ lọc dạng chip + tab sắp xếp) |
| Bộ lọc | Chỉ ở tab Lưu trú: Khoảng giá (slider), Hạng sao. **Không** có bộ lọc điểm đến (điểm đến do câu truy vấn quyết định) và không có bộ lọc ngày trong MVP | **Phụ thuộc:** biến thể search theo điểm đến/ngân sách (handbook §11 Tuần 4). Trước khi có thì lọc client-side | `[R33]` KAYAK web (panel lọc trái: hạng sao, điểm review); `[R31]` Klook web (chip bộ lọc đang áp dụng có × và "Clear") |
| Sắp xếp | Popup "Sắp xếp: Phù hợp nhất ▾" (Phù hợp nhất · Giá thấp → cao · Giá cao → thấp) ở mọi tab trừ Tất cả. Mặc định "Phù hợp nhất", có giải thích khi hover/bấm: "Kết quả được xếp theo mức độ **gần nghĩa** với câu bạn gõ, không chỉ trùng từ khóa. Vì vậy bạn có thể mô tả chuyến đi bằng lời thường." | — | `[R30]` Kiwi.com web ("Best match" + link "Why results appear this way ⓘ"); `[R34]` TravelPerk web ("Relevance ⓘ"); `[R24]` Vinted iOS (sheet "How do search results work?" liệt kê tiêu chí) |
| Thẻ kết quả `row` | Ảnh, hạng sao, tên, điểm đến, tối đa 3 tag từ `attributes` (key boolean true → nhãn tiếng Việt), `PriceTag`, nút "Xem" | `/search` | `[R31]` Klook web (tag "Pet friendly · In downtown · Close to subway"); `[R29]` Tripadvisor web (dòng "Mentions: Classic · Quaint · Family" có dấu ✓) |
| Thẻ Trợ lý trong danh sách | Chèn sau kết quả thứ 6: "Muốn ghép thành lịch trình? Hỏi trợ lý với "{q}"" | — | `[R29]` Tripadvisor web (khối "Powered by AI — Get a personalized itinerary in Rome — Build your trip" đặt ngay trên trang kết quả) |
| Phân trang | "Xem thêm" (20/lần), không phân trang số | — | — |

**Không** hiện `BecauseLine` trên kết quả tìm kiếm, vì `/search` không trả `because`. Lý do ở đây là truy vấn của người dùng, và tag thuộc tính đã đảm nhận vai trò giải thích "vì sao khớp".

#### 4.2.4 Trạng thái

| Trạng thái | Hành vi | Pattern |
|---|---|---|
| Đang tải | Giữ header + dòng truy vấn. 5 skeleton `row` + skeleton tab | `[R42]` Navan web; `[R43]` KAYAK web (tab sắp xếp hiện ngay, thẻ còn là skeleton) |
| **Kết quả yếu** (đặc thù vector search: engine luôn trả top-K, nên "0 kết quả" hiếm khi xảy ra) | Nếu Search trả được ngưỡng điểm (**phụ thuộc**) và toàn bộ kết quả dưới ngưỡng thì hiện băng nhẹ phía trên: "Chưa tìm thấy kết quả thật sát với "{q}". Đây là những lựa chọn gần nhất." | — (không có pattern Mobbin tương ứng, đây là đề xuất riêng cho semantic search) |
| Rỗng do bộ lọc | "Không có kết quả với bộ lọc hiện tại" + nút bỏ từng bộ lọc: [Bỏ "Nha Trang"] [Bỏ "5★"] + [Xóa tất cả bộ lọc] | `[R40]` Pinterest web ("Tweak your search" + các nút "Remove price / Remove brands / Clear all filters") |
| Rỗng thật (0 kết quả) | "Chưa tìm thấy gì cho "{q}"" + "Thử mô tả khác, ví dụ:" 3 câu mẫu + [Hỏi trợ lý] + carousel "Phổ biến trên V-OTA" | `[R39]` Codecademy web ("We couldn't find a match… or see what our members are learning"); `[R41]` DoorDash web ("No Results" + "Reset Search" + danh sách trending) |
| Truy vấn rỗng (`/search` không có `q`) | Chuyển về Home và focus ô tìm kiếm | — |
| Lỗi API | `ErrorState`: "Không tải được kết quả. [Thử lại]". Giữ truy vấn trong ô | `[R114]` Typeform web |

---

### 4.3 Product detail

**Mục đích:** chuyển từ "quan tâm" sang "cho vào giỏ", và là nơi thứ hai hiển thị gợi ý (`/similar` + gợi ý theo chuyến).

#### 4.3.1 Bố cục desktop

```
┌ Header ───────────────────────────────────────────────────────────────────────┐
│ Trang chủ › Nha Trang › Khách sạn                                              │
│ Vinpearl Resort Nha Trang - Deluxe Ocean View                                   │
│ [Khách sạn] ★★★★★ · 📍 Nha Trang · 4,6/5 (1.293 đánh giá tổng hợp)              │
│ ┌──────────────── ảnh lớn ─────────────┐┌──ảnh──┐                               │
│ │                                      │├──ảnh──┤   (1 ảnh thì chiếm hết chiều   │
│ └──────────────────────────────────────┘└──ảnh──┘    ngang, không để ô trống)    │
├─ Tabs dính: Tổng quan · Tiện ích · Chọn ngày & số lượng · Tương tự ───────────┤
│ CỘT TRÁI (2/3)                              │ CỘT PHẢI (1/3, dính khi cuộn)    │
│ ▸ Mô tả (4 dòng + "Xem thêm")               │ ┌ Hộp đặt ─────────────────────┐ │
│ ▸ Điểm nổi bật: tag từ attributes          │ │ Từ 3.400.000 ₫ / đêm          │ │
│ ▸ Tiện ích (lưới 2 cột, icon + nhãn,        │ │ Nhận phòng  [15/10/2026]      │ │
│   "Xem tất cả n tiện ích")                  │ │ Trả phòng   [18/10/2026]      │ │
│ ▸ Chọn ngày & số lượng (inline cho vé)      │ │ Số phòng    [–] 1 [+]         │ │
│ ▸ Thông tin thêm: có hiệu lực từ–đến        │ │ ─────────────────────────────  │ │
│                                             │ │ 3 đêm × 3.400.000 = 10.200.000│ │
│                                             │ │ [ Đặt ngay ]      (chính)     │ │
│                                             │ │ Khách sạn được đặt trực tiếp, │ │
│                                             │ │ không thêm vào giỏ hàng       │ │
│                                             │ │ Bạn chưa bị trừ tiền — bản demo│ │
│                                             │ └───────────────────────────────┘ │
├─────────────────────────────────────────────┴──────────────────────────────────┤
│ TƯƠNG TỰ VINPEARL RESORT NHA TRANG           (GET /similar/{id})               │
│ ┌card┐ ┌card┐ ┌card┐ ┌card┐   nhãn "Tương tự"                                   │
├────────────────────────────────────────────────────────────────────────────────┤
│ HOÀN THIỆN CHUYẾN NHA TRANG  (chỉ khi đăng nhập & strategy = cross_vertical)   │
│ ┌card+because┐ …                                                               │
└────────────────────────────────────────────────────────────────────────────────┘
```

#### 4.3.2 Thành phần và dữ liệu

| Thành phần | Chi tiết | Nguồn | Pattern |
|---|---|---|---|
| Đầu trang | Breadcrumb, tên, badge, hạng sao, điểm đến, điểm đánh giá tổng hợp + số lượng (được phép theo handbook §3; ẩn nếu không có) | `Product` | `[R49]` Tripadvisor web (tên + rating + "#14 of 467 small hotels" + gallery 1 lớn 3 nhỏ) |
| Gallery | 1 ảnh lớn + tối đa 4 ảnh nhỏ. Schema chỉ có một `imageUrl` → MVP hiện 1 ảnh full-width, tỷ lệ 16:7. Ảnh lỗi → placeholder theo `taxonomy` | `imageUrl` (**phụ thuộc:** nhiều ảnh) | `[R49]` Tripadvisor web |
| Tabs dính | Cuộn tới anchor, đánh dấu tab đang xem | — | `[R46]` Expedia web (Overview · Amenities · Rooms · Policies dính trên cùng); `[R47]` Klook web |
| Mô tả | Mô tả tiếng Việt từ vinpearl.com, cắt 4 dòng | `description` | — |
| Tiện ích / thuộc tính | Map các key `attributes` sang icon + nhãn tiếng Việt. Key lạ thì bỏ qua, không hiện tên key thô | `attributes` | `[R48]` Airbnb web ("What this place offers": lưới 2 cột + "Show all 34 amenities") |
| **Hộp đặt** | Các trường thay đổi theo `taxonomy` (bảng 4.3.3). Ngày bị giới hạn trong `availableFrom`–`availableTo`. Tổng tiền tính lại ngay khi đổi lựa chọn. Dòng trấn an: "Bạn chưa bị trừ tiền — đây là bản demo" | `unitPrice`, `available*` | `[R48]` Airbnb web (hộp đặt dính bên phải + "You won't be charged yet"); `[R51]` Klook web (lịch chọn ngày + chọn giờ + stepper số lượng + "Add to cart" / "Book now") |
| CTA theo loại | **Khách sạn, vé máy bay:** chỉ có "Đặt ngay" kèm dòng "được đặt trực tiếp, không thêm vào giỏ hàng" (giá và chỗ đổi liên tục nên không gom vào giỏ). **Tour, trải nghiệm, golf, combo:** "Thêm vào giỏ" (chính) → toast "Đã thêm vào giỏ · [Xem giỏ]", ở lại trang; và "Đặt ngay" (phụ). "Đặt ngay" ở mọi loại mở thẳng trang thanh toán với **đúng mục này**, không kèm mục nào đang có trong giỏ (`docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`) | — | `[R51]` Klook web (hai nút cạnh nhau) |
| Tương tự | "Tương tự {tên rút gọn}", 4–8 thẻ có nhãn "Tương tự". Không có `BecauseLine`, vì lý do đã nằm ở tiêu đề (nguồn là chính sản phẩm đang xem) | `GET /similar/{productId}` | `[R54]` KAYAK web ("You might also like — Similar hotels" + badge "Similar"); `[R55]` Turo web ("Similar cars for your dates"); `[R56]` Tripadvisor web ("Popular Nearby ⓘ") |
| Hoàn thiện chuyến | Chỉ khi đã đăng nhập **và** `destination` của gợi ý trùng với điểm đến sản phẩm. Dùng lại section ① của Home | `/recommendations` | `[R09]` Booking.com iOS |
| Lối vào Trợ lý | Link nhỏ dưới hộp đặt: "Lên lịch trình quanh {tên}" → `/assistant` điền sẵn "Gợi ý lịch trình 3 ngày ở {destination}, tôi ở {tên}" | — | `[R88]` Booking.com iOS (người dùng mở chat bằng "I've booked: Wolf Inn Hotel…") |

#### 4.3.3 Hộp đặt theo `taxonomy`

| `taxonomy` | Trường chọn | Công thức tổng | Ghi chú |
|---|---|---|---|
| `hotel` | **Hạng phòng** (danh sách từ `GET /products?parentProductId=`), nhận phòng, trả phòng, số phòng | `unitPrice của hạng phòng × số đêm × số phòng` | Khách sạn (property) không đặt trực tiếp: chọn một hạng phòng, mặc định hạng rẻ nhất còn đặt được. Ngày mặc định: ngày mai (giờ Việt Nam) trong cửa sổ mở bán, 1 đêm. Khách sạn không có hạng phòng thì chỉ để xem |
| `flight` | **Chuyến bay** của tuyến (danh sách như trên), số hành khách | `unitPrice × số khách` | Mỗi chuyến bay có một ngày cố định (`availableFrom = availableTo`), hiện ở dạng chỉ đọc |
| `attraction` / `golf` | Ngày sử dụng (chip nhanh "Hôm nay · Ngày mai · Chọn ngày"), số khách | `unitPrice × số khách` | `[R53]` Klook web (chip "Today / Tomorrow / 27 Jan / All dates"); `[R52]` Klook web (panel "What's included") |
| `combo` | Ngày bắt đầu, số khách | `unitPrice × số khách` | — |

Mọi lựa chọn được lưu thành một mục giỏ (tour, trải nghiệm, tiện ích) hoặc một mục của đơn nháp Đặt ngay, với `usingDate` và `quantity`, khớp trường của `UserEvent` (handbook §6).

#### 4.3.4 Trạng thái

| Trạng thái | Hành vi |
|---|---|
| Đang tải | Skeleton ảnh lớn + 3 dòng tiêu đề + khung hộp đặt. Section Tương tự tải riêng. Pattern: `[R46]` Expedia web (skeleton khối phòng trong lúc tải) |
| `available: false` | Hộp đặt thay bằng: "Sản phẩm này hiện đã hết chỗ" + [Xem lựa chọn tương tự] (cuộn tới section Tương tự). Hai CTA bị ẩn |
| Ngày chọn ngoài `availableFrom`–`availableTo` | Ngày bị disable trên lịch. Nếu dữ liệu cũ khiến toàn bộ khoảng ngày đã qua thì xử lý như hết chỗ |
| 404 (sản phẩm bị xóa, handbook §6 "event trỏ tới sản phẩm đã bị xóa") | Trang "Sản phẩm này không còn trên V-OTA" + carousel phổ biến + [Về trang chủ] |
| `/similar` lỗi hoặc rỗng | Ẩn section, không báo lỗi |
| Thêm vào giỏ thất bại | Nút trở lại bình thường. Toast lỗi "Chưa thêm được vào giỏ. [Thử lại]" |
| Khách vãng lai bấm CTA | Modal đăng nhập (§4.7). Thành công thì tự thực hiện hành động đã bấm |

**Phụ thuộc:** event `product_view` do Backend ghi khi `GET /product/:id` hay Web phải gọi riêng? Việc này ảnh hưởng tới P2 (khách lần đầu có gợi ý "Vì bạn đã xem").

---

### 4.4 Cart

Giỏ **chỉ giữ tour, trải nghiệm và tiện ích khác** (`attraction`, `golf`, `combo`); khách sạn và vé máy bay không bao giờ nằm trong giỏ (FR-BKG-01, `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`). Khách chưa đăng nhập cũng có giỏ. Trang có một dòng ghi chú: khách sạn và vé máy bay được đặt ngay ở trang sản phẩm.

#### 4.4.1 Bố cục desktop

```
┌ Header ───────────────────────────────────────────────────────────────────────┐
│ Giỏ hàng (3)                                                                   │
├──────────────────────────────────────────────────┬────────────────────────────┤
│ CHUYẾN NHA TRANG                                 │ TÓM TẮT                    │
│ ┌ compact card ─────────────────────────────────┐│ 3 dịch vụ                  │
│ │[ảnh] [Vé tham quan] VinWonders Nha Trang      ││ Tạm tính        8.740.000 ₫│
│ │      16/10/2026 · 3 người lớn                 ││ ─────────────────────────  │
│ │      [Sửa] [Xóa]                   2.640.000 ₫││ Tổng            8.740.000 ₫│
│ └───────────────────────────────────────────────┘│ [ Tiến hành đặt chỗ ]      │
│ ┌ compact card ─────────────────────────────────┐│                            │
│ │[ảnh] [Vé tham quan] Vinpearl Safari mini ...  ││                            │
│ └───────────────────────────────────────────────┘│                            │
│ CHUYẾN PHÚ QUỐC                                  │                            │
│ ┌ compact card: [Golf] ... ─────────────────────┐│                            │
│ Khách sạn và vé máy bay không nằm trong giỏ:     │                            │
│ được đặt ngay ở trang sản phẩm.                  │                            │
└──────────────────────────────────────────────────┴────────────────────────────┘
```

#### 4.4.2 Thành phần và dữ liệu

| Thành phần | Chi tiết | Pattern |
|---|---|---|
| Nhóm theo điểm đến | Các mục được gom theo `destination`, tiêu đề "Chuyến {destination}". Việc gom nhóm này giúp người dùng *thấy* khái niệm chuyến đi ở cả UI lẫn engine (`eventGroupId`). **Phụ thuộc:** Backend gán `eventGroupId` theo nhóm nào lúc checkout | — (không có OTA nào trên Mobbin gom giỏ theo chuyến; `[R12]` Trip.com iOS có khái niệm "Plan Your Entire Trip" gần nhất) |
| Mục giỏ (`compact`) | Ảnh, badge, tên, ngày + số lượng + đơn vị, thành tiền, [Sửa] (mở lại hộp chọn dạng popover), [Xóa] | `[R58]` Klook web (mục giỏ có ngày, stepper, Manage/Remove); `[R60]` lululemon web (Edit / Remove) |
| Tóm tắt dính bên phải | Số dịch vụ, tạm tính, tổng, CTA "Tiến hành đặt chỗ", dòng "Bản demo — không thu tiền". Không có thuế/phí/mã giảm giá | `[R59]` adidas web ("Order summary" dính phải + CTA to); `[R58]` Klook web (Subtotal + "Book now") |
| ~~Thường được đặt cùng~~ | **Đã bỏ (2026-10-01).** Trang giỏ không còn khối gợi ý và không gọi `/recommendations`; gợi ý trong luồng đặt còn ở trang chi tiết và trang đơn | — |

#### 4.4.3 Trạng thái

| Trạng thái | Hành vi | Pattern |
|---|---|---|
| Rỗng | Icon + "Giỏ hàng của bạn đang trống" + [Khám phá gợi ý cho bạn] (→ Home) + [Hỏi trợ lý lên kế hoạch]. Dòng mô tả nói rõ giỏ giữ tour, trải nghiệm và tiện ích khác; khách sạn và vé máy bay đặt ngay ở trang sản phẩm | `[R64]` Faire web ("Your cart is empty" + "Shop bestsellers" + "Recently viewed"); `[R65]` Etsy web ("Related items you may like" ngay dưới trạng thái rỗng) |
| Đang cập nhật một mục (sửa/xóa) | Mục đó mờ đi + spinner nhỏ tại chỗ. Các mục khác vẫn thao tác được. Tổng tiền hiện skeleton | `[R62]` Urban Outfitters web (spinner phủ đúng mục đang cập nhật) |
| Mục hết chỗ (`available` đổi thành false) | Viền đỏ + "Dịch vụ này đã hết chỗ — hãy xóa để tiếp tục". CTA checkout disabled tới khi xóa | — |
| Xóa mục | Xóa ngay + toast "Đã xóa {tên} · [Hoàn tác]" | `[R23]` Instagram iOS (toast có "Undo") |
| Lỗi tải giỏ | `ErrorState` + [Thử lại] |  |

**Đã chốt:** giỏ lưu phía server. Người đã đăng nhập: database, khoá theo `cdp_user_id`. Khách chưa đăng nhập: Redis, khoá theo mã khách do BFF phát, giữ 3 ngày; khi đăng nhập thì mục chưa có được chép vào giỏ tài khoản, mục trùng giữ một bản, rồi dữ liệu của khách bị xoá (`docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` §8, §9).

---

### 4.5 Checkout

#### 4.5.1 Bố cục desktop

Checkout gồm **ba bước** trên cùng route `/checkout` (`?step=travelers|services|review`), thay cho một trang ba khối. Wireframe, hành vi và luật kiểm từng bước nằm ở `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (FR-BKG-08): §6.4 (bước ① Hành khách), §6.6 (bước ② Dịch vụ), §6.7 (bước ③ Xem lại và thanh toán). Khung chung:

```
┌ Header rút gọn: Logo · ← Quay lại giỏ hàng ────────────────────────────────────┐
│  ① Hành khách ──── ② Dịch vụ ──── ③ Xem lại và thanh toán                       │
├──────────────────────────────────────────────────┬────────────────────────────┤
│ Nội dung của bước hiện tại                       │ ĐƠN CỦA BẠN (dính khi cuộn) │
│  ① Số người lớn, trẻ em; họ, tên đệm và tên,     │ 2 người lớn · 1 trẻ em      │
│    ngày sinh trẻ em; người liên hệ               │ Từng dịch vụ: ngày + thành  │
│  ② Chọn ai dùng từng dịch vụ; khách sạn xếp      │ tiền (theo dòng giá của      │
│    khách vào phòng; giá cập nhật theo loại khách │ Backend)                    │
│  ③ Hành khách, dịch vụ, phương thức Stripe,      │ ─────────────────────────── │
│    điều khoản, [Thanh toán {tổng}]               │ Tổng   [Sửa giỏ hàng]       │
│ [← Quay lại]                        [Tiếp tục →] │                            │
└──────────────────────────────────────────────────┴────────────────────────────┘
```

#### 4.5.2 Quy tắc

| Quy tắc | Chi tiết | Pattern |
|---|---|---|
| Ba bước | ① Hành khách → ② Dịch vụ → ③ Xem lại và thanh toán. Thanh bước có ✓ ở bước đã xong, bấm được để quay lại; nút Back của trình duyệt về bước trước mà không mất dữ liệu. Chỉ sửa giỏ ở hai bước đầu, chưa giữ chỗ, chưa tạo đơn | Spec checkout-nhieu-buoc §6.2 |
| Điền sẵn | Họ tên Người lớn 1 và người liên hệ lấy từ tài khoản (bỏ trống nếu tên tài khoản không dùng được làm họ tên trên giấy tờ). Email khóa (đổi email ngoài phạm vi). Số người lớn, trẻ em lấy từ giỏ | `[R67]` Tripadvisor web (email khóa, trường hợp lệ có ✓ xanh) |
| Kiểm tra hợp lệ | Kiểm tra khi rời trường (blur), không kiểm tra theo từng phím. Lỗi hiện ngay dưới trường. Nút **Tiếp tục** luôn bấm được: còn lỗi thì ở lại bước, hiện hộp "Còn n thông tin cần sửa" (mỗi dòng là link tới trường) và đưa con trỏ về trường lỗi đầu tiên. Backend kiểm lại toàn bộ; lỗi từ Backend đưa về đúng bước chứa trường lỗi | `[R67]` Tripadvisor web; spec checkout-nhieu-buoc §5, §6.7 |
| Đoàn khách và phân bổ | Khai đoàn một lần (người lớn từ 12 tuổi, trẻ em dưới 12 tuổi kèm ngày sinh, mỗi người họ và tên đệm và tên). Ở từng dịch vụ chọn ai dùng; khách sạn xếp người vào phòng (mỗi phòng ≥ 1 người lớn, không vượt sức chứa, có người đại diện). Vé máy bay, vé tham quan, golf, combo mặc định gán cả đoàn | Spec checkout-nhieu-buoc §6.5, §6.6 |
| Giá theo loại khách | Vé có giá trẻ em hợp lệ thì trẻ em trả giá đó; còn lại trả giá người lớn. Mọi số tiền hiển thị lấy từ `CartResponse` (`fares`, `lineTotal`, `total`); Web không tự cộng | Spec checkout-nhieu-buoc §4 |
| **Khối phương thức thanh toán** | Ở bước ③. Chỉ Stripe (chọn sẵn); ví điện tử, chuyển khoản hiển thị vô hiệu hoá, nhãn "Sắp có" (`docs/prd/user-flow.md` §3.3). Không vẽ form thẻ: khách nhập thẻ trên trang do Stripe host | `[R68]` Airbnb web ("Add a payment method") |
| Tóm tắt dính phải | Đoàn khách ("2 người lớn · 1 trẻ em"), tên + ngày + số lượng + thành tiền từng mục, tổng, link "Sửa giỏ hàng". Khi một `PATCH` giỏ đang chạy, thành tiền của mục và tổng hiện khung chờ. Trên mobile là thanh cố định ở đáy kèm bottom sheet | `[R66]` Klook web; `[R57]` Navan web ("In this booking") |
| CTA | Bước ①, ②: "Tiếp tục". Bước ③: "Thanh toán ({tổng})", disabled cho tới khi đã chọn phương thức và tick điều khoản (gồm xác nhận họ tên và chính sách huỷ). Dưới nút: "Giữ chỗ 30 phút sau khi bấm Thanh toán. Bạn sẽ được chuyển sang Stripe." | `[R70]` KAYAK web (nút "Confirm booking" disabled + đoạn điều khoản ngay trên) |

#### 4.5.3 Trạng thái

| Trạng thái | Hành vi |
|---|---|
| Đang gửi | Nút đổi thành spinner + "Đang giữ chỗ và mở trang thanh toán…", disabled để **chống bấm hai lần** (Backend cũng chỉ cho một đơn giữ chỗ mỗi người). Pattern: `[R86]` Uvodo web (spinner nằm trong nút chính) |
| Thành công (`201 PENDING_PAYMENT`) | Chuyển trình duyệt sang `payment.checkoutUrl` (trang Stripe). Stripe đưa về `/booking/:referenceCode?payment=return` hoặc `?payment=cancelled` |
| Đang có đơn giữ chỗ (`409 BOOKING_PENDING_PAYMENT`) | Hộp thoại: "Tiếp tục thanh toán đơn đó" hoặc "Huỷ đơn đó và đặt lại từ giỏ" (đơn nháp: "Huỷ đơn đó và đặt lại") |
| Dữ liệu chưa hợp lệ (`400 VALIDATION_ERROR`) | Về bước chứa trường lỗi (① hoặc ②), gắn lỗi vào từng trường và hiện hộp "Còn n thông tin cần sửa"; dữ liệu đã nhập giữ nguyên |
| Giá đổi (`409 PRICE_CHANGED`) | Banner giá cũ → giá mới (giá vé trẻ em đổi thì ghi "Giá vé trẻ em của …") + [Cập nhật và tiếp tục] (xác nhận giá mới vào giỏ), khách bấm Thanh toán lần nữa |
| Một mục hết chỗ (4xx) | Banner trên cùng: "{tên} vừa hết chỗ." + [Quay lại giỏ]. Dữ liệu đã nhập được giữ nguyên |
| Stripe không phản hồi (`503`) / lỗi mạng / 5xx | Banner "Cổng thanh toán tạm thời không phản hồi" (hoặc thông điệp lỗi) + [Thử lại]. Không xóa form, không tạo đơn |
| 401 giữa chừng | Modal đăng nhập lại, giữ dữ liệu form trong bộ nhớ, sau đó gửi lại |
| Giỏ rỗng khi vào `/checkout` | Chuyển về `/cart` |
| Thanh toán một đơn nháp (`/checkout?draft=…`) | Chỉ các mục của lần Đặt ngay; đồng hồ "Phiên thanh toán còn mm:ss" (30 phút); không có "Sửa giỏ hàng" |
| Đơn nháp hết hạn (`410 BOOKING_DRAFT_EXPIRED`) | "Phiên thanh toán đã hết hạn": khách sạn, vé máy bay phải chọn lại ([Chọn lại phòng], [Tìm lại chuyến bay]); tour và tiện ích của lần đặt vẫn nằm trong giỏ ([Về giỏ hàng]) |
| Khách chưa đăng nhập bấm Thanh toán | Modal đăng nhập tại chỗ; đăng nhập xong tự gửi tiếp, thông tin đã nhập còn nguyên |

---

### 4.6 Confirmation

**Mục đích:** chốt đơn **và** là nơi vòng lặp phản hồi (K1) xuất hiện đầu tiên.

#### 4.6.1 Bố cục desktop

```
┌ Header ───────────────────────────────────────────────────────────────────────┐
│ ✅ Đặt chỗ thành công!                                                          │
│ Mã tham chiếu:  VOTA-20261015-8K3F   [Sao chép]                                │
│ Đặt lúc 14:22, 16/09/2026 · Bản demo: không có email xác nhận được gửi đi       │
├───────────────────────────────────────────────────────────────────────────────┤
│ CHI TIẾT ĐƠN                                                                    │
│ [ảnh] Vinpearl Resort Nha Trang · 15/10–18/10/2026 · 1 phòng · 10.200.000 ₫    │
│ [ảnh] Vé máy bay Hà Nội – Cam Ranh · 15/10/2026 · 2 khách · 3.780.000 ₫        │
│ Tổng: 14.180.000 ₫ · Liên hệ: Nguyễn Minh Anh · 0912 345 678                   │
│ [ Xem gợi ý mới trên trang chủ ]   [ Lên lịch trình cho chuyến Nha Trang ]     │
├───────────────────────────────────────────────────────────────────────────────┤
│ TIẾP THEO CHO CHUYẾN NHA TRANG                                     [Vì sao?]   │
│ Vì bạn vừa đặt Vinpearl Resort Nha Trang — đây là những thứ bạn còn thiếu     │
│ ┌card+because┐ ┌card+because┐ ┌card+because┐                                  │
└───────────────────────────────────────────────────────────────────────────────┘
```

#### 4.6.2 Thành phần

| Thành phần | Chi tiết | Pattern |
|---|---|---|
| Tiêu đề thành công | Icon ✓ + "Đặt chỗ thành công!". Không dùng minh họa lớn, vì cần chừa không gian màn hình đầu tiên cho gợi ý | `[R73]` Klook web ("Booking confirmed" + Booking reference ID + ngày đặt); `[R72]` Tripadvisor web (mã xác nhận chữ lớn) |
| Mã tham chiếu | Font mono, cỡ lớn, có nút sao chép (toast "Đã sao chép") | `[R72]` Tripadvisor web ("Confirmation number: 1625480075") |
| Chi tiết đơn | Danh sách mục + tổng + thông tin liên hệ | `[R75]` KAYAK web ("Your flight booking" + Summary); `[R76]` Time2book web (thẻ xác nhận gọn) |
| Hai CTA | "Xem gợi ý mới trên trang chủ" (→ `/` với cờ `justBooked`, xem §4.1.4) · "Lên lịch trình cho chuyến {destination}" (→ `/assistant` điền sẵn điểm đến + ngày của khách sạn vừa đặt) | `[R76]` Time2book web ("My schedule" / "Book more"); `[R09]` Booking.com iOS ("Want to keep planning your trip itinerary? — Continue planning") |
| **Tiếp theo cho chuyến** | Gọi `/recommendations` **chỉ khi** đơn đã `CONFIRMED`. Tiêu đề + phụ đề theo §5.3. Thẻ có `BecauseLine` "Vì bạn vừa đặt {tên} · hôm nay" | `[R26]` Expedia web (trang xác nhận có "People who bought "Jakarta Museum…" also viewed" nêu đích danh sản phẩm nguồn); `[R74]` Kiwi.com web (xác nhận vé máy bay kèm "Latest hotel deals in Las Vegas", tức gợi ý chéo danh mục ngay sau khi đặt) |

#### 4.6.3 Trạng thái

| Trạng thái | Hành vi |
|---|---|
| Tải lại trang / mở từ link | `GET /bookings/{referenceCode}`. Không có thì hiện "Không tìm thấy đơn đặt chỗ này" + [Về trang chủ] |
| Vừa quay về từ Stripe (`?payment=return`) | "Đang kiểm tra thanh toán…"; hỏi lại 2 giây/lần tối đa 15 lần tới khi đơn rời `PENDING_PAYMENT`. Đã thu tiền mà chưa xác nhận xong → "Đã nhận thanh toán, đang xác nhận đơn" |
| Đang giữ chỗ | "Đơn đang được giữ chỗ" + đồng hồ đếm ngược theo `holdExpiresAt` + [Tiếp tục thanh toán] [Huỷ đơn]. Hết giờ → "Hết thời gian giữ chỗ" + [Đặt lại] (đơn nháp mới từ các dịch vụ của đơn, theo giá hiện tại) |
| Thanh toán thất bại / hết hạn / đã huỷ | Theo `docs/spec/hop-dong-tich-hop-frontend.md` §4.6; không gọi gợi ý |
| Huỷ đơn đã xác nhận | Nút [Huỷ đơn] khi còn trước `cancellableUntil`; hộp thoại nêu số tiền hoàn, hạn huỷ, "không thể hoàn tác" |
| Gợi ý đang tải | Phần đơn hàng hiện ngay. Section gợi ý hiện skeleton |
| Gợi ý lỗi / rỗng | Ẩn section, giữ hai CTA. Không để lỗi gợi ý làm người dùng nghĩ đặt chỗ thất bại |
| Gợi ý vẫn cùng danh mục đã đặt (engine chưa loại trừ) | Vẫn hiển thị, nhưng dùng tiêu đề chung "Có thể bạn quan tâm" thay vì "Tiếp theo cho chuyến…", tránh lời hứa sai |

---

### 4.7 Login / Register

Theo handbook §8, xác thực tồn tại "để bản demo có thể cho những người khác nhau thấy những gợi ý khác nhau". Từ MVP, kiểm thử và trình diễn đi qua đúng luồng đăng ký/đăng nhập thật, không có đường tắt chọn tài khoản.

#### 4.7.1 Hai hình thức

| Hình thức | Khi nào | Pattern |
|---|---|---|
| **Modal** phủ lên trang hiện tại | Khi khách vãng lai bấm hành động cần đăng nhập (Thanh toán ở bước cuối của trang thanh toán, đặt lại đơn) hoặc khi JWT hết hạn | `[R77]` Tripadvisor web ("Welcome back." dạng modal, trang sau vẫn thấy); `[R80]` Klarna web (modal "Sign in / Or Create account") |
| **Trang** `/login`, `/register` | Bấm "Đăng nhập" trên header, hoặc truy cập thẳng route cần đăng nhập. Nhận `?redirect=` | `[R78]` Klook web (thẻ đăng nhập đặt giữa trên nền ảnh du lịch, có câu giá trị ngắn); `[R79]` Expedia web ("Sign in or create an account" 1 cột) |

#### 4.7.2 Đăng nhập

```
┌───────────────────────────────────────┐
│ Đăng nhập V-OTA                        │
│ Nhận gợi ý theo chuyến đi của bạn      │
│ Email       [                      ]   │
│ Mật khẩu    [                  👁 ]   │
│ [          Đăng nhập           ]       │
│ Chưa có tài khoản? Đăng ký             │
└───────────────────────────────────────┘
```

- Trường: email, mật khẩu (có nút hiện/ẩn). **Không có** "Quên mật khẩu", "Ghi nhớ đăng nhập" hay đăng nhập mạng xã hội (§1.3).
- Lỗi xác thực: một thông điệp chung phía trên nút, "Email hoặc mật khẩu không đúng", không chỉ ra trường nào sai.
- Đang gửi: spinner trong nút, form khóa.
- Thành công: đóng modal hoặc chuyển tới `redirect` (mặc định `/`), rồi thực hiện tiếp hành động đang chờ (nếu có). Toast "Xin chào, {tên}".
- Câu giá trị dưới tiêu đề: "Nhận gợi ý theo chuyến đi của bạn". Pattern: `[R82]` Skyscanner iOS và `[R81]` Best Buy iOS (nói lợi ích trước khi đòi đăng nhập).

#### 4.7.3 Bộ chọn tài khoản demo — đã gỡ

`DemoAccountSwitcher` đã bị gỡ ngày 2026-09-24 (`docs/prd/update-archive/2026-09-24-go-bo-chon-tai-khoan-demo.md`). Tài khoản seed đăng nhập qua form §4.7.2. Giữ số mục để không đổi các tham chiếu.

#### 4.7.4 Đăng ký

- Trường: họ và tên, email, mật khẩu (hiện/ẩn) + checklist quy tắc hiện trực tiếp khi gõ ("Ít nhất 8 ký tự" ✓…). Quy tắc chính xác do Backend quyết định. Không có ô "nhập lại mật khẩu", vì đã có nút hiện mật khẩu.
  Pattern: `[R85]` Sketch web (checklist "Your password must have" + thanh độ mạnh); `[R86]` Uvodo web (checklist ✓ xanh + spinner trong nút).
- Lỗi "Email này đã được đăng ký. [Đăng nhập]" hiện dưới trường email.
- Thành công: tự đăng nhập, chuyển về Home. Người dùng mới có `coldStart: true` (P4) và thấy băng chào: "Tài khoản mới chưa có lịch sử. Hãy tìm kiếm hoặc xem vài sản phẩm, gợi ý sẽ bắt đầu theo bạn."

#### 4.7.5 Hết phiên (JWT hạn ngắn, handbook §8)

Khi nhận 401: mở modal "Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục." với email điền sẵn. Không mất state của trang (form checkout, hội thoại chat). Người dùng hủy thì chuyển về chế độ khách vãng lai ở trang hiện tại.

---

### 4.8 Chat assistant (trợ lý lịch trình)

Phần này mô tả **màn hình**. Luồng từ tin nhắn tới kế hoạch, cách render sản phẩm và quy tắc grounding nằm ở **§6**.

**Hiện trạng code:** `AssistantView` dùng một form nhập yêu cầu và render response itinerary theo ngày; có nhập giọng nói, lưu/chia sẻ và thẻ thời tiết. Không có giao diện chat theo chuỗi tin nhắn hoặc chế độ bản đồ trong code hiện tại. Widget nổi mở luồng tạo itinerary riêng. Chưa xác minh runtime.

#### 4.8.1 Bố cục desktop: chia đôi màn hình

Bố cục dưới đây là UX mục tiêu. Frontend hiện render form và kết quả theo một cột; chưa có bố cục chat/kế hoạch chia đôi hoặc panel bản đồ.

```
┌ Header ───────────────────────────────────────────────────────────────────────┐
├──────────────── CỘT CHAT (40%) ─────────┬──────── PANEL KẾ HOẠCH (60%) ────────┤
│ Trợ lý lịch trình V-OTA  [Cuộc mới ↻]   │ (trống trước khi có kế hoạch:        │
│                                         │  minh họa + "Kế hoạch sẽ hiện ở đây")│
│ 🤖 Chào Minh Anh! Mình lên lịch trình   │                                      │
│    theo ngày với sản phẩm thật, đặt     │ Lịch trình 3 ngày ở Nha Trang        │
│    được ngay. Thử một câu:              │ [📍Nha Trang ✎][📅3 ngày ✎]          │
│    [3 ngày Nha Trang cho gia đình…]     │ [👨‍👩‍👧 Gia đình, trẻ nhỏ ✎][🎢 Vui chơi]│
│    [Cuối tuần Phú Quốc cho cặp đôi]     │ Chỗ ở cho cả chuyến ── card khách sạn │
│    [Đà Nẵng 2 ngày, ngân sách 5 triệu]  │ [Ngày 1] [Ngày 2] [Ngày 3]           │
│                                         │ Sáng ── card VinWonders               │
│ 👤 Gợi ý lịch trình 3 ngày ở Nha Trang  │ Trưa ── ghi chú tự do (không đặt)    │
│    cho gia đình có trẻ nhỏ              │ Chiều ─ card vé tham quan            │
│ 🤖 [Thẻ tóm tắt kế hoạch → panel phải]  │ Tối ── card nhà hàng/combo           │
│                                         │ ───────────────────────────────────  │
│ ┌──────────────────────────────────┐    │ 5 dịch vụ đặt được · 9.870.000 ₫    │
│ │ Nhập yêu cầu chuyến đi…      [➤] │    │ [ Thanh toán tất cả ]                │
│ └──────────────────────────────────┘    │                                      │
│ Trợ lý chỉ lên kế hoạch chuyến đi.      │                                      │
└─────────────────────────────────────────┴──────────────────────────────────────┘
```

| Quyết định | Lý do | Pattern |
|---|---|---|
| Chia đôi: chat trái, kế hoạch phải | Kế hoạch là một **đối tượng** (có ngày, có tổng tiền), không nên chìm trong luồng tin nhắn dài | `[R90]` Mindtrip web (chat trái + panel "Best trip ever!" có Day accordion + "Generate itinerary"); `[R91]` Mindtrip web (chat trái + bản đồ phải); `[R105]` Etsy web ("Gifting assistant": chat trái + lưới sản phẩm phải) |
| Tin nhắn của trợ lý có **thẻ gọn của từng sản phẩm** ngay sau lần nhắc đầu tiên; bấm thẻ mở panel chi tiết ở cột phải (PRD `user-flow.md` §4.2, chốt 2026-10-02, thay quyết định cũ "chỉ chứa thẻ tóm tắt") | Người đọc lời kể thấy ngay nơi được nhắc là gì, không phải dò sang cột phải; chi tiết mở tại chỗ thay vì sang tab mới | `[R104]` Klarna iOS (thẻ sản phẩm có giá ngay trong câu trả lời chat); `[R103]` Trip.com iOS (thẻ trong chat dẫn tới chi tiết) |
| Câu mẫu bằng tiếng Việt khi hội thoại rỗng | Hướng người dùng vào đúng phạm vi hẹp của trợ lý (handbook §9 "Giữ nó hẹp") | `[R87]` Booking.com iOS ("You can try asking about…" + 3 chip "Build an itinerary…"); `[R89]` Mindtrip web (thẻ ví dụ có tiêu đề nhóm); `[R124]` Trip.com iOS ("TripGenie is here to inspire" + thẻ câu hỏi) |
| Dòng phạm vi dưới ô nhập: "Trợ lý chỉ lên kế hoạch chuyến đi, sản phẩm lấy từ kho V-OTA." | Đặt kỳ vọng và nhắc về grounding | `[R101]` Wanderlog iOS (hộp "The AI Assistant is purely informational…" + "Asking questions about New York. Change") |
| Nút "Cuộc mới" | Handbook §9 "không duy trì hội thoại dài". Không có lịch sử nhiều cuộc | — (chủ động không làm danh sách lịch sử như `[R87]`) |

#### 4.8.2 Lối vào trợ lý

| Từ | Nội dung điền sẵn |
|---|---|
| Nút "Trợ lý" của tab bar mobile | Rỗng (hiện câu mẫu) |
| Home, thẻ ③ | "Gợi ý lịch trình 3 ngày ở {destination}" |
| Search, thẻ trong danh sách | "{q}", ví dụ "nghỉ dưỡng biển cho gia đình" |
| Product detail | "Gợi ý lịch trình 3 ngày ở {destination}, tôi ở {tên khách sạn}" |
| Confirmation | "Lên lịch trình cho chuyến {destination} từ {ngày nhận}–{ngày trả}, tôi đã đặt {tên}" |

Prompt điền sẵn **chỉ được điền vào ô**, không tự gửi, để người dùng sửa được. Riêng lối vào từ Confirmation thì tự gửi (một click, phục vụ demo K3).

#### 4.8.3 Trạng thái màn hình (chi tiết ở §6.6)

Rỗng · Đang xử lý (3 bước) · Cần hỏi lại (thiếu ý định) · Có kế hoạch · Kế hoạch một phần (thiếu sản phẩm cho một số khung) · Ngoài phạm vi · LLM lỗi/timeout → fallback kết quả tìm kiếm · Lỗi mạng.

Đây là tập trạng thái UX mục tiêu. Code hiện tại hiển thị lỗi khi operation chưa bật hoặc request Backend thất bại; response `FALLBACK` chỉ được render khi Backend trả về status tương ứng. Không có planner cục bộ thay thế request.

---

## 5. Hiển thị cá nhân hóa & giải thích gợi ý (`because`)

Handbook §7: "Mảng `because` không phải đồ trang trí… Hãy hiển thị nó cả trên UI nữa." Phần này biến từng trường của response thành chữ và thành phần giao diện cụ thể.

### 5.1 Bốn cấp giải thích

| Cấp | Ở đâu | Trả lời câu hỏi | Dữ liệu | Pattern |
|---|---|---|---|---|
| **C1 · Tiêu đề section** | Home ①, Detail, Cart, Confirmation | "Nhóm gợi ý này để làm gì?" | `strategy`, `nextVertical`, `destination`, `diagnostics.excludedVerticals`, `coldStart` | `[R13]` Booking.com iOS ("Suggestions based on your recent search"); `[R09]` Booking.com iOS ("Add more to your trip"); `[R19]` Codecademy web ("Based on your benchmark score, here are your recommendations") |
| **C2 · Checklist chuyến** | Dưới tiêu đề section `cross_vertical` | "Chuyến của tôi đã có gì, còn thiếu gì?" | `excludedVerticals` (✓), `nextVertical` (đang gợi ý, in đậm) | `[R12]` Trip.com iOS ("Plan Your Entire Trip… Book 1/6 · Explore 1/6 · Pack 0/30"); `[R10]` Agoda iOS ("Missing anything for your trip?") |
| **C3 · `BecauseLine` trên thẻ** | Mỗi `ProductCard` gợi ý | "Vì sao lại là sản phẩm *này*?" | `because[0]` (mục có `contribution` lớn nhất) | `[R26]` Expedia web ("People who bought "Jakarta Museum…" also viewed", nêu đích danh sản phẩm nguồn); `[R20]` Apple Store iOS ("Recommended for your iPhone 15" + dấu ✓ "Compatible with iPhone" ở chân thẻ); `[R18]` Hulu web (nhãn lý do ngắn trên từng thẻ: "FOR SCI-FI FANS") |
| **C4 · Popover "Vì sao?"** | Bấm vào `BecauseLine` hoặc nút "Vì sao?" | "Chính xác hệ thống dựa vào những gì?" | toàn bộ `because[]` | `[R25]` Hypelist iOS ("More like this — If you like: [sản phẩm nguồn] — You might also like:"); `[R22]` Lovi iOS (sheet "What does this mean?" liệt kê lý do đánh số); `[R17]` Google Ads web (dòng "Recommended because you've added a conversion action…" + ⓘ) |

### 5.2 `BecauseLine`: quy tắc sinh chữ

**Cấu trúc:** `{icon sự kiện} Vì bạn {động từ} {tên sản phẩm nguồn} · {thời gian}`

| `event` | Động từ | Icon |
|---|---|---|
| `purchase` | "đã đặt" | vali |
| `add_to_cart` | "đã chọn để đặt" (thêm giỏ hoặc Đặt ngay đều ghi event này) | giỏ |
| `product_view` | "đã xem" | mắt |
| `search` | "đã tìm" (khi đó hiển thị truy vấn trong ngoặc kép thay cho tên sản phẩm, nếu Backend trả về) | kính lúp |
| giá trị lạ | "đã quan tâm tới" | chấm |

| `daysAgo` | Hiển thị |
|---|---|
| 0 | "hôm nay" |
| 1 | "hôm qua" |
| 2–6 | "{n} ngày trước" |
| 7–29 | "{⌊n/7⌋} tuần trước" |
| 30–364 | "{⌊n/30⌋} tháng trước" |
| ≥ 365 | "hơn 1 năm trước" |

**Ví dụ từ response mẫu handbook §7:**

> 🧳 Vì bạn đã đặt **Vinpearl Resort Nha Trang - Deluxe Ocean View** · 3 ngày trước

**Quy tắc hiển thị:**

1. Tối đa **1 dòng**. Tên sản phẩm nguồn cắt "…" ở 32 ký tự, toàn bộ tên nằm trong `title`/tooltip.
2. Nếu `because.length > 1` thì thêm hậu tố "và {n-1} lý do khác", và cả dòng là nút mở popover C4.
3. `because` rỗng hoặc `coldStart: true` thì **không** hiện `BecauseLine`. Thay bằng nhãn trung tính theo ngữ cảnh: "Được đặt nhiều" hoặc "Phổ biến tại {destination}" (nguyên tắc 1.4-3).
4. Sản phẩm nguồn không còn tồn tại (handbook §6 "những rìa lộn xộn") thì dùng "Vì bạn đã đặt một dịch vụ ở {destination}", không link.
5. Trong popover, tên sản phẩm nguồn là link tới `/product/:id` (**phụ thuộc:** `because[]` hiện chỉ có `productName`, cần thêm `productId` để link). Không có id thì hiển thị chữ thường.
6. Màu chữ phụ (không dùng màu nhấn), cỡ nhỏ hơn tên sản phẩm một bậc. Lý do là thông tin hỗ trợ, không cạnh tranh với giá.

### 5.3 Tiêu đề section (C1) theo `strategy`

| Điều kiện | Tiêu đề | Phụ đề |
|---|---|---|
| `strategy = "cross_vertical"`, có `destination`, `nextVertical` | "Hoàn thiện chuyến {destination} của bạn" | "Bạn đã có {excludedVerticals → "khách sạn"}, còn thiếu {nextVertical → "vé máy bay"}" |
| Như trên, trên trang Confirmation | "Tiếp theo cho chuyến {destination}" | "Vì bạn vừa đặt {because[0].productName}" |
| `coldStart: false`, không phải cross_vertical, có `because` | "Gợi ý dựa trên hoạt động của bạn" | "Từ những gì bạn đã xem và đặt gần đây" |
| Dormant (**phụ thuộc** giá trị `strategy`) | "Chào mừng quay lại, {tên}" | "Dựa trên chuyến {destination} của bạn {thời gian của because[0]}" |
| `coldStart: true`, có `destination` | "Phổ biến tại {destination}" | "Bạn mới bắt đầu. Xem thêm vài sản phẩm để gợi ý hợp với bạn hơn" |
| `coldStart: true`, không có gì | "Được đặt nhiều trên V-OTA" | — |
| `strategy` lạ | "Có thể bạn quan tâm" | — |

Map `taxonomy → danh từ`: hotel "khách sạn", flight "vé máy bay", attraction "vé tham quan", combo "combo", golf "sân golf". Nếu `excludedVerticals` có nhiều giá trị thì nối bằng "và".

**Pattern cho câu dẫn cá nhân hóa trên section:** `[R03]` Tripadvisor web (khối chữ "We think you'd enjoy these homes for a quick trip out of town." đứng cạnh carousel), `[R07]` Turo web ("Inspired by your recent searches"), `[R15]` Best Buy iOS ("Related to your top categories").

### 5.4 Popover "Vì sao tôi thấy gợi ý này?" (C4)

```
┌ Vì sao bạn thấy "Vé máy bay Hà Nội - Cam Ranh"? ─────── × ┐
│ Dựa trên những gì bạn đã làm trên V-OTA:                   │
│                                                            │
│ [ảnh] Vinpearl Resort Nha Trang - Deluxe Ocean View  →     │
│       🧳 Bạn đã đặt · 3 ngày trước                          │
│       Ảnh hưởng: ●●●○  Nhiều                               │
│                                                            │
│ [ảnh] VinWonders Nha Trang                            →     │
│       👁 Bạn đã xem · 5 ngày trước                          │
│       Ảnh hưởng: ●○○○  Ít                                  │
│ ────────────────────────────────────────────────────────── │
│ Chuyến Nha Trang của bạn đã có khách sạn, nên chúng tôi    │
│ ưu tiên vé máy bay thay vì gợi ý thêm khách sạn.           │
│ Gợi ý thay đổi khi bạn xem hoặc đặt thêm.                  │
└────────────────────────────────────────────────────────────┘
```

- Liệt kê **mọi** mục `because[]`, sắp giảm dần theo `contribution`, mỗi mục kèm ảnh thu nhỏ của sản phẩm nguồn (**phụ thuộc:** cần `productId` hoặc `imageUrl` trong `because`; không có thì bỏ ảnh). Pattern: `[R25]` Hypelist iOS (khối "If you like:" có ảnh sản phẩm nguồn đặt trên danh sách gợi ý).
- `contribution` được hiển thị **định tính**, 4 chấm: ≥ 0,5 "Nhiều" ●●●○ · 0,2–0,5 "Vừa" ●●○○ · < 0,2 "Ít" ●○○○. Không hiện số thập phân.
- Câu cuối giải thích chiến lược, sinh từ `strategy` + `excludedVerticals`. Đây là câu trả lời trực tiếp cho cái bẫy "chỉ gợi ý đúng danh mục đã đặt" (handbook §11 Tuần 3, §13).
- Desktop: popover neo vào nút, đóng khi click ra ngoài hoặc Esc, focus trap. Mobile: bottom sheet (`[R24]` Vinted iOS, sheet "How do search results work?").
- Không có nút "Ẩn gợi ý này" hay "Không quan tâm" (không có API, §1.3).

### 5.5 Cá nhân hóa ngoài Home

| Nơi | Hiển thị | Chiến lược chữ |
|---|---|---|
| Product detail | Section "Hoàn thiện chuyến {destination}" (khi điểm đến trùng) | C1 + C3 |
| Cart | "Thường được đặt cùng chuyến {destination}" | C1 + C3 |
| Confirmation | "Tiếp theo cho chuyến {destination}" | C1 + C3 + C4 |
| Chat | Mục trong kế hoạch lấy từ `/recommendations` có nhãn "Hợp với bạn" + `BecauseLine` | §6.4 |
| Search | **Không** cá nhân hóa thứ tự. Nhãn sắp xếp là "Phù hợp nhất" (theo truy vấn), không phải "Dành cho bạn" | Tránh nhầm với `[R122]` World of Hyatt iOS ("Sort By: For You"), vì `/search` không dùng user vector |

### 5.6 Chế độ chẩn đoán (cho stakeholder và debug)

Handbook §7: `because` là "ranh giới giữa một cuộc tranh cãi và một chẩn đoán". Chế độ này dành cho người trình bày và kỹ sư, **không** dành cho khách.

- **Bật:** thêm `?debug=1` vào URL, hoặc tổ hợp phím `Shift+D`. Trạng thái lưu theo phiên. Có huy hiệu "DEBUG" cố định góc màn hình.
- **Trên mỗi thẻ gợi ý:** `rank`, `score` (2 chữ số thập phân), `contribution` dạng số trong popover.
- **Trên mỗi section gợi ý:** khối gập được hiển thị `modelVersion`, `strategy`, `nextVertical`, `generatedAt`, `diagnostics.eventsUsed`, `coldStart`, `excludedVerticals`, `latencyMs`.
- **Trong chat:** ý định trích xuất dạng JSON, danh sách truy vấn search đã chạy, số sản phẩm mỗi truy vấn trả về, thời gian từng bước.
- Pattern: Mobbin không có màn hình debug của ứng dụng production (điều dễ hiểu). Cách trình bày "một dòng giải thích nhỏ + ⓘ" mượn từ `[R17]` Google Ads web. **Đây là đề xuất riêng, không có tham chiếu trực tiếp.**

---

## 6. Luồng trợ lý lịch trình: từ tin nhắn tới kế hoạch có thể đặt dịch vụ

> **Luồng trong code:** `AssistantView` gọi status và stream itinerary qua OpenAPI client; widget nổi gọi operation tạo itinerary. `ResponseView` render các status và dữ liệu trả về theo schema. Next.js proxy chuyển tiếp `/api/v1/*` tới `BACKEND_BASE_URL`. Runtime/config chưa được xác minh; pipeline bên dưới là UX mục tiêu.

### 6.1 Ánh xạ pipeline handbook §9 sang trải nghiệm

| Bước pipeline (handbook §9) | Người dùng thấy gì | Pattern |
|---|---|---|
| Tin nhắn của khách hàng | Bong bóng tin nhắn, ô nhập bị khóa, nút gửi đổi thành "Dừng" | `[R110]` Structured iOS ("Fine-tuning your itinerary…" + nút Stop) |
| LLM trích xuất ý định → `{destination, days, party, interests}` | Bước 1 "Đang hiểu yêu cầu…" chuyển thành ✓ → **chip ý định** hiện ngay trong panel kế hoạch (6.2) | `[R100]` Bard web (hộp "…check the following flight details: Round trip · SIN → TPE · Jan 22–28 · 1 adult" nhắc lại tham số đã hiểu); `[R89]` Mindtrip web (thanh chip "Where · When · 2 travelers · Budget" ở đầu cuộc chat) |
| Service chạy vài lượt tìm kiếm (lưu trú, tham quan, ăn uống) | Bước 2 "Đang tìm chỗ ở, vé tham quan, ăn uống ở {destination}…" | `[R109]` Wabi iOS (thẻ tiến độ nhiều bước: "Creating plan → Developing logic → Designing screens → Final touches") |
| Trộn `/recommendations` nếu đã đăng nhập | Bước 2 có thêm dòng phụ "…và ưu tiên những gì hợp với bạn" (chỉ khi đã đăng nhập) | — |
| LLM sắp xếp kết quả thật thành kế hoạch theo ngày | Bước 3 "Đang sắp xếp lịch trình…" → skeleton khung ngày trong panel | `[R111]` Instacart iOS ("Generating your shoppable recipe…" + skeleton) |
| Render kèm giá thật + link đặt | Panel kế hoạch đầy đủ (6.3) + thẻ tóm tắt trong chat | `[R96]` Agoda iOS; `[R95]` Tripadvisor iOS |

**Phụ thuộc: tiến độ thật hay giả lập.** Nếu chat backend trả một response duy nhất (không stream), UI **không được** tự đánh ✓ từng bước theo đồng hồ như thể đó là tiến độ thật. Khi đó hiển thị cả 3 bước dạng danh sách "Trợ lý sẽ: hiểu yêu cầu → tìm sản phẩm → sắp xếp lịch trình" với một spinner chung. Nếu Backend stream sự kiện theo bước (SSE) thì đánh ✓ theo sự kiện thật. Đề xuất Backend stream, vì mục tiêu p95 < 5 giây (handbook §12) vẫn đủ lâu để người dùng cần thấy tiến độ.

**Hiện trạng code:** client đọc stream SSE. Widget trợ lý đánh ✓ 3 bước theo `node.completed` thật (`features/itinerary/widget/widgetProgress.ts`); bước đang chạy hiện việc con khi có (thử lại, viết lời tư vấn).

### 6.2 Chip ý định: cho phép sửa mà không phải gõ lại

```
Lịch trình 3 ngày ở Nha Trang
[📍 Nha Trang ✎] [📅 3 ngày ✎] [👨‍👩‍👧 Gia đình · trẻ nhỏ ✎] [🎢 Vui chơi] [🏖 Biển] [+ sở thích]
```

- Mỗi chip ứng với một trường ý định. Bấm ✎ mở popover chỉnh: điểm đến (danh sách 10–15 điểm đến trong catalog, handbook §3), số ngày (stepper 1–7), đoàn khách (chip chọn: Một mình · Cặp đôi · Gia đình có trẻ nhỏ · Nhóm bạn), sở thích (chip bật/tắt).
- Sửa chip sẽ **tạo lại kế hoạch** với ý định đã sửa, bỏ qua bước trích xuất (**phụ thuộc:** API chat nhận ý định có cấu trúc). Trong chat thêm dòng hệ thống "Đã đổi: 3 ngày → 2 ngày".
- Pattern: `[R90]` Mindtrip web (modal "What's your travel vibe?" chọn chip sở thích + "Generate itinerary"); `[R92]` Mindtrip web (modal "Where" chỉnh điểm đến); `[R94]` Tripadvisor iOS flow "Creating a trip (using AI)" (các bước chọn ngày / trip length stepper / sở thích dạng chip "Must-see Attractions · Great Food · Hidden Gems").

**Thiếu trường bắt buộc** (ví dụ người dùng chỉ gõ "đi biển") → trợ lý **hỏi lại bằng thẻ lựa chọn**, không đoán:

```
🤖 Bạn muốn đi đâu và mấy ngày?
   Điểm đến: [Nha Trang] [Phú Quốc] [Đà Nẵng] [Khác…]
   Số ngày:  [2] [3] [4] [5+]
   [Tạo lịch trình]
```

Pattern: `[R108]` Shopify web (thẻ câu hỏi làm rõ: các lựa chọn đánh số 1–4 + "Other" + Dismiss/Next).
Nếu cắt về single-turn (handbook §2, mục 6) thì thẻ này là cách *duy nhất* để bổ sung thông tin. Ô nhập tự do khi đó bị ẩn sau khi có kế hoạch, thay bằng nút "Tạo kế hoạch mới".

### 6.3 Panel kế hoạch: cấu trúc render

```
┌ Lịch trình 3 ngày ở Nha Trang ────────────────────────────────────────────────┐
│ [chip ý định…]                                                                 │
│ ⓘ Mọi dịch vụ có nút đặt đều là sản phẩm thật trên V-OTA, giá tại thời điểm    │
│   tạo kế hoạch. Gợi ý hoạt động tự do chỉ để tham khảo.                        │
├───────────────────────────────────────────────────────────────────────────────┤
│ CHỖ Ở CHO CẢ CHUYẾN                                                            │
│ ┌ compact ProductCard ─────────────────────────────────────────────────────┐   │
│ │[ảnh][Khách sạn] Vinpearl Resort Nha Trang · ★★★★★   3.400.000 ₫ / đêm    │   │
│ │ 💬 "Có hồ bơi trẻ em và bãi biển riêng, gần VinWonders."  ← ghi chú LLM  │   │
│ │ ✨ Hợp với bạn · Vì bạn đã xem Vinpearl Nha Trang · hôm qua              │   │
│ │ [Xem chi tiết]  [Đặt ngay]            (khách sạn: không có Thêm vào giỏ)  │   │
│ └───────────────────────────────────────────────────────────────────────────┘   │
├─ [ Ngày 1 ] [ Ngày 2 ] [ Ngày 3 ]  (tab; desktop rộng thì hiện liền kề) ──────┤
│ NGÀY 1 · Vui chơi trọn ngày                                                   │
│ ☀ SÁNG    ┌ compact ProductCard: [Vé tham quan] VinWonders Nha Trang ─────┐  │
│           │ 880.000 ₫ / khách · 💬 "Đi sớm…" [Thêm vào giỏ] [Đặt ngay]    │  │
│           └────────────────────────────────────────────────────────────────┘  │
│ 🌤 TRƯA    ┌ ActivityNote (không phải sản phẩm) ─────────────────────────┐    │
│           │ 🍽 Ăn trưa trong khu vui chơi · Nghỉ ngơi                   │    │
│           └──────────────────────────────────────────────── (không nút) ┘    │
│ 🌙 TỐI    ┌ compact ProductCard: [Combo] Tata Show + buffet … ─────────────┐  │
│           └────────────────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────────────────────────┤
│ 5 dịch vụ đặt được · Tổng ước tính 9.870.000 ₫ (2 người lớn, 1 trẻ em)         │
│ [ Thanh toán tất cả ]                                                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

| Phần | Quy tắc | Pattern |
|---|---|---|
| Tiêu đề + chip ý định | Tiêu đề sinh từ ý định, không lấy nguyên văn LLM | `[R95]` Tripadvisor iOS ("Your trip to Island of Hawaii for 5 days for a family") |
| Băng grounding | Luôn hiện, một dòng, có ⓘ | `[R95]` Tripadvisor iOS (nhãn "This trip is powered by AI."); `[R101]` Wanderlog iOS |
| Chỗ ở cho cả chuyến | Khách sạn không lặp lại mỗi ngày mà ghim thành khối đầu | `[R95]` Tripadvisor iOS (khối "Places to stay — We've also recommended some places to stay during your trip") |
| Tab ngày | Mặc định mở Ngày 1. Tiêu đề phụ của ngày do LLM đặt, tối đa 6 từ | `[R94]` Tripadvisor iOS (chip "January 13 / January 14" + "Monday, Jan 13"); `[R97]` Vrbo iOS (timeline theo ngày) |
| Khung giờ Sáng / Trưa / Chiều / Tối | Mỗi khung chứa 0–2 mục. Khung trống thì ẩn | `[R115]` Microsoft Copilot iOS ("Morning / Afternoon / Evening" trong mỗi Day); `[R88]` Booking.com iOS (cùng cấu trúc, nhưng chỉ có chữ) |
| `ProductCard` compact | Xem 6.4 | `[R96]` Agoda iOS (trong itinerary có thẻ "Suggested — Need a flight" với chuyến bay thật "From SGD 513" + "See all"); `[R104]` Klarna iOS (carousel thẻ sản phẩm có giá ngay trong câu trả lời chat) |
| `ActivityNote` | Mục không phải sản phẩm: nền xám nhạt, icon, chữ nghiêng, **không có giá, không có nút, không có ảnh sản phẩm** | `[R97]` Vrbo iOS (phân biệt thẻ "Booked" có ảnh với mục "Visit the Grand Palace" chỉ có chữ); `[R98]` KAYAK web (mục trong ngày có nhãn "Booked" khác mục tự thêm) |
| Ghi chú LLM trên thẻ | 1–2 câu, icon 💬, trình bày như trích dẫn. Giải thích *vì sao nằm ở khung giờ này* | `[R105]` Etsy web (mỗi sản phẩm có một câu lý do ngắn do trợ lý viết: "Perfect for helping up your weekend breakfasts…") |
| Nhãn "Hợp với bạn" | Chỉ cho sản phẩm đến từ `/recommendations`, kèm `BecauseLine` (§5.2) | `[R97]` Vrbo iOS (công tắc "Showing AI recommendations" tách mục gợi ý khỏi mục đã đặt) |
| Tổng + CTA | Đếm **chỉ** các `ProductCard` còn `available`. **"Thanh toán tất cả"** gom mọi mục đặt được của kế hoạch (lưu trú và hoạt động) vào một đơn nháp với ngày suy từ ngày của kế hoạch rồi mở trang thanh toán; mục không đặt được bị bỏ và báo trong toast. Từng thẻ có nút riêng: khách sạn, vé máy bay có "Đặt ngay"; tour, golf, combo có "Thêm vào giỏ" và "Đặt ngay". Sản phẩm chưa đặt được (ví dụ khách sạn chưa có hạng phòng trong lịch trình) không có nút, thẻ mở trang chi tiết | `[R94]` Tripadvisor iOS (màn hình "Add to itinerary": checkbox từng mục + "Select all" + nút "Add") |

### 6.4 Quy tắc grounding mục tiêu trên UI ("LLM không tự bịa sản phẩm", handbook §9, §12, §13)

**Hiện trạng code:** `ResponseView` render `slot.product`, ghi chú, giá và cảnh báo trong response itinerary. Các quy tắc bên dưới là hợp đồng UX mục tiêu; việc có generated type không tự xác nhận mọi điều kiện đã được kiểm tra ở runtime.

Đây là **hợp đồng render**, Web phải tuân thủ bất kể LLM trả gì:

1. **Thẻ đặt được chỉ render từ `productId`.** Mỗi mục kế hoạch hoặc có `productId`, hoặc là `ActivityNote`. Không có trạng thái thứ ba.
2. **Tên, ảnh, giá, điểm đến, badge trên thẻ lấy từ dữ liệu sản phẩm** (catalog/search), **không lấy từ văn bản LLM**. LLM chỉ đóng góp: tiêu đề ngày, khung giờ, ghi chú 💬.
3. **Không tự động biến tên riêng trong văn bản LLM thành link.** Mindtrip `[R91]` link hóa địa danh trong văn bản; V-OTA **không** làm vậy, vì một cái tên LLM viết ra có thể không phải sản phẩm thật.
4. **`productId` không resolve được** (404, sai thành phố, `available: false`) thì mục đó **không** được render thành thẻ. Thay bằng dòng mờ "Mục này hiện không còn chỗ · [Tìm lựa chọn khác]" (→ `/search?q={destination} {taxonomy}`). Ở chế độ debug, ghi lý do loại.
5. **`destination` của sản phẩm khác `destination` của ý định** thì không render. Đây là kiểm tra "đúng thành phố" của handbook §11 Tuần 4, lặp lại ở client như lưới an toàn cuối.
6. **Nút "Xem chi tiết" dẫn tới `/product/:id` thật**; "Thêm vào giỏ", "Đặt ngay" và "Thanh toán tất cả" dùng đúng luồng giỏ và đơn nháp của trang thanh toán. Không có luồng đặt riêng trong chat (handbook §9: trợ lý "không xử lý việc đặt chỗ").
7. Ghi chú 💬 bị cắt ở 160 ký tự. Ghi chú chứa giá tiền (regex số + "đ/₫/VND") thì ẩn phần giá, vì giá chỉ được hiện từ `PriceTag`.

**Đề xuất hợp đồng dữ liệu tối thiểu cho UI** (Backend chốt tên trường; UI chỉ cần hình dạng này):

```json
{
  "intent": { "destination": "Nha Trang", "days": 3, "party": "family_with_kids",
              "interests": ["theme_park", "beach"], "startDate": null },
  "missing": [],                       // ví dụ ["destination","days"] → hiện thẻ hỏi lại (6.2)
  "title": "Lịch trình 3 ngày ở Nha Trang",
  "stay": { "productId": "382ae67c-…", "note": "Có hồ bơi trẻ em…", "source": "recommendation",
            "because": [ { "productName": "…", "event": "product_view", "daysAgo": 1, "contribution": 0.4 } ] },
  "days": [
    { "day": 1, "title": "Vui chơi trọn ngày",
      "slots": [
        { "time": "morning",   "productId": "7c2f…", "note": "Đi sớm tránh nắng", "source": "search" },
        { "time": "noon",      "productId": null,    "note": "Ăn trưa trong khu vui chơi" },
        { "time": "evening",   "productId": "91ab…", "note": "…", "source": "search" }
      ] }
  ],
  "fallback": false,                   // true → LLM lỗi, chỉ có searchResults (6.6)
  "searchResults": { "hotel": ["…"], "attraction": ["…"], "food": ["…"] }
}
```

`source: "recommendation"` quyết định nhãn "Hợp với bạn". `searchResults` luôn có (kể cả khi thành công) để dùng cho fallback và cho "Tìm lựa chọn khác".

### 6.5 Tin nhắn trong cột chat

| Loại | Hiển thị |
|---|---|
| Người dùng | Bong bóng phải |
| Trợ lý: văn bản | Bong bóng trái, markdown giới hạn (đậm, danh sách). Không render link ngoài |
| Trợ lý: **thẻ tóm tắt kế hoạch** | "📋 Lịch trình 3 ngày ở Nha Trang · 5 dịch vụ · ~9.870.000 ₫ · [Xem kế hoạch]". Bấm vào focus panel phải (mobile: mở sheet) |
| Trợ lý: **thẻ sản phẩm trong lời diễn giải** | `ProductCard` compact ngay sau dòng đầu tiên nhắc sản phẩm, dữ liệu từ response (tuân thủ §6.4). Bấm thẻ hoặc tên: panel chi tiết ở cột phải (PRD `user-flow.md` §4.2) |
| Trợ lý: thẻ hỏi lại | 6.2 |
| Trợ lý: gợi ý tiếp theo | 2–3 chip dưới tin nhắn cuối: "Đổi thành 2 ngày", "Thêm hoạt động buổi tối", "Rẻ hơn". Bấm là gửi. Pattern: `[R103]` Trip.com iOS ("You may also ask" + các câu hỏi gửi được); `[R104]` Klarna iOS (chip câu hỏi tiếp theo dưới carousel) |
| Hệ thống | Dòng chữ nhỏ căn giữa: "Đã đổi: 3 ngày → 2 ngày", "Đã thêm 5 dịch vụ vào giỏ · [Xem giỏ]" |

### 6.6 Trạng thái trợ lý

| Trạng thái | Hiển thị | Pattern |
|---|---|---|
| **Rỗng** | Lời chào có tên (nếu đã đăng nhập) + 3–4 câu mẫu dạng thẻ + dòng phạm vi. Khách vãng lai có thêm dòng "Đăng nhập để kế hoạch ưu tiên những gì hợp với bạn" | `[R87]` Booking.com iOS; `[R89]` Mindtrip web |
| **Đang xử lý** | Thẻ tiến độ 3 bước trong chat + skeleton panel. Nút "Dừng" hủy request và khôi phục ô nhập kèm nội dung vừa gửi | `[R109]` Wabi iOS; `[R110]` Structured iOS |
| **Chậm** (> 12 giây không có bước nào xong — thời gian dồn vào các node gọi LLM nên đo theo từng node, không theo cả lượt) | Thêm dòng "Đang lâu hơn thường lệ. Bạn có thể đợi thêm hoặc dừng." + link "Xem kết quả tìm kiếm trước" (mở fallback song song) | — |
| **Có kế hoạch** | 6.3 | — |
| **Kế hoạch một phần** | Khung giờ không có sản phẩm hợp lệ thì hiện `ActivityNote` do LLM viết. Nếu cả một ngày không có sản phẩm nào thì hiện "Chưa tìm thấy dịch vụ phù hợp cho ngày này · [Tìm ở {destination}]" | — |
| **Ngoài phạm vi** (hỏi thời tiết, visa, chuyện chung) | Tin nhắn: "Mình chỉ giúp lên lịch trình và gợi ý dịch vụ du lịch trên V-OTA. Thử: …" + 2 câu mẫu | `[R101]` Wanderlog iOS (giới hạn phạm vi được nói rõ) |
| **Điểm đến không có trong catalog** | "V-OTA chưa có dịch vụ ở {nơi}. Các điểm đến hiện có: [Nha Trang] [Phú Quốc] …" | — |
| **LLM lỗi / timeout → fallback** (handbook §9: "nếu LLM chậm hoặc không khả dụng, bạn vẫn có thể hiện kết quả tìm kiếm") | Chat: "Trợ lý đang bận nên chưa sắp được lịch trình. Đây là các dịch vụ phù hợp ở {destination} để bạn tự chọn. [Thử tạo lịch trình lại]". Panel: tiêu đề "Dịch vụ gợi ý ở {destination}", nhóm theo Chỗ ở / Tham quan / Ăn uống, dùng `ProductCard` compact (vẫn tuân thủ 6.4). Nếu cả bước trích xuất cũng lỗi thì chạy `/search?q={tin nhắn gốc}` | `[R113]` Google AI Studio web (lỗi hiện ngay trong luồng chat) |
| **Lỗi mạng khi gửi** | Dưới bong bóng người dùng: "⚠ Chưa gửi được · [Thử lại]". Nội dung không mất | `[R112]` X web ("Failed, Try Again" dưới tin nhắn) |
| **401** | Modal đăng nhập lại (§4.7.5), sau đó tự gửi lại |  |

### 6.7 Nhất quán với giỏ và vòng lặp

**Hiện trạng code:** client có wrapper cho cart, event và booking; route Cart, Checkout và Confirmation hiện render màn hình API chưa khả dụng, chưa gọi các wrapper này. Chưa xác minh luồng ghi booking/event hoặc cập nhật recommendation qua Backend.

- "Thêm vào giỏ", "Đặt ngay" và "Thanh toán tất cả" từ chat ghi `add_to_cart` như mọi nơi khác (không có đường tắt ghi `purchase`). Khách sạn và vé máy bay của kế hoạch không vào giỏ: chúng chỉ nằm trong đơn nháp của lần thanh toán đó.
- Sau khi đặt xong từ các mục của kế hoạch, Confirmation hiện CTA "Quay lại lịch trình" (giữ hội thoại trong phiên) bên cạnh "Xem gợi ý mới trên trang chủ".
- Kế hoạch **không** tự cập nhật giá sau khi tạo. Băng grounding ghi "giá tại thời điểm tạo kế hoạch". Giỏ và Checkout luôn dùng giá mới nhất và báo nếu giá đổi.

---

## 7. Mobile layout

### 7.1 Breakpoint

| Tên | Chiều rộng | Tóm tắt |
|---|---|---|
| Mobile | < 640 px | 1 cột, tab bar dưới, CTA dính đáy, popover chuyển thành bottom sheet |
| Tablet | 640–1023 px | 2 cột lưới thẻ; Detail/Cart/Checkout vẫn 1 cột + CTA dính đáy; Chat 1 cột |
| Desktop | ≥ 1024 px | Bố cục như §4 |

Quy tắc chung: vùng chạm ≥ 44 × 44 px, lề ngang 16 px, không cuộn ngang trang (carousel cuộn ngang *trong* khung, có scroll-snap và để lộ một phần thẻ kế tiếp). Hỗ trợ safe-area (tai thỏ, thanh home).

### 7.2 Điều hướng

- **Tab bar dưới 5 mục:** Trang chủ · Tìm kiếm · Trợ lý · Giỏ hàng (badge) · Tài khoản. Pattern: `[R123]` Airbnb iOS (Explore · Wishlists · Trips · Messages · Profile); `[R10]` Agoda iOS (Home · My Trips · Deals · Saved · More).
- Tab bar **ẩn** trong: Checkout, màn hình chat đang gõ (bàn phím mở), sheet toàn màn hình.
- Header mobile: logo + ngôn ngữ + đăng nhập/tài khoản (nhóm dịch vụ bị ẩn). Lối vào danh mục là hàng chip cuộn ngang (`VerticalChips`, cao 44 px) ở đầu Home và trang danh mục; tab bar dưới vẫn 5 mục. Trên Search/Detail thì thay bằng nút ← + **ô tìm kiếm dạng viên thuốc** chứa truy vấn/tên. Pattern: `[R117]` Agoda iOS (viên "SOCIAL on Outram · Jul 14 – Jul 15" trên đầu trang chi tiết).

### 7.3 Từng màn hình trên mobile

| Màn hình | Thay đổi so với desktop | Pattern |
|---|---|---|
| **Home** | Ô tìm kiếm to trên cùng. Section ① lên thứ hai, carousel ngang (thẻ rộng 72% màn hình). Checklist chuyến thành hàng chip cuộn ngang. `BecauseLine` giữ 1 dòng, cắt tên ở 24 ký tự. Toast "trang chủ đã cập nhật" hiện ngay trên tab bar | `[R08]` Airbnb iOS; `[R13]` Booking.com iOS; `[R15]` Best Buy iOS (toast ngay trên tab bar) |
| **Search (nhập)** | Bấm ô tìm kiếm mở màn hình toàn phần: ô nhập + "Tìm kiếm gần đây" + "Thử tìm" | `[R37]` Booking.com iOS; `[R38]` Skyscanner iOS |
| **Search (kết quả)** | Thẻ dọc (ảnh trên, nội dung dưới). Hàng chip dính dưới header: [Bộ lọc (n)] [Khách sạn] [Vé tham quan] [Sắp xếp ▾]. "Bộ lọc" mở bottom sheet toàn phần, nút dính đáy "Xem {n} kết quả" | `[R120]` Agoda iOS (chip "Filters 6" + khoảng giá + "Sort" dính trên cùng); `[R36]` Booking.com iOS (sheet lọc với nút dính đáy "925 matching properties · Show results"); `[R121]` Skyscanner iOS (nút nổi "Sort and filters") |
| **Product detail** | Ảnh full-width trên cùng. Tabs anchor thành hàng cuộn ngang dính. Hộp đặt chuyển thành **thanh dính đáy**: "Từ 3.400.000 ₫ / đêm" + [Chọn ngày] → mở bottom sheet chọn ngày/số lượng → [Thêm vào giỏ] (chỉ tour, trải nghiệm, tiện ích) [Đặt ngay]. Section Tương tự thành carousel | `[R117]` Agoda iOS (thanh đáy "Start at S$64 · Choose my room"); `[R118]` Agoda iOS (vé tham quan: thẻ ngày cuộn ngang + thanh đáy "Starts from · See options") |
| **Cart** | Danh sách 1 cột. Tóm tắt thành **thanh dính đáy**: "Tổng 14.180.000 ₫ ▴" (bấm để mở chi tiết) + [Đặt chỗ]. "Thường được đặt cùng" carousel dưới danh sách | `[R58]` Klook web (bản desktop; cấu trúc tương đương) |
| **Checkout** | 1 cột, ba bước. Thanh cố định ở đáy: "2 người lớn · 1 trẻ em", tổng tiền ⌃ (bấm mở bottom sheet tóm tắt đơn) và nút chính của bước (Tiếp tục / Thanh toán {tổng}). Bàn phím: email `type=email`, điện thoại `type=tel`, ngày sinh `inputMode=numeric`. Dòng "Giữ chỗ 30 phút sau khi bấm Thanh toán" dưới nút ở bước ③ | `[R119]` Agoda iOS (CTA dính đáy "NEXT: FINAL STEP") |
| **Confirmation** | Mã tham chiếu + nút sao chép trên cùng. Hai CTA xếp dọc full-width. Gợi ý thành carousel | — |
| **Login / Register** | Trang toàn màn hình (không dùng modal) | `[R82]` Skyscanner iOS (màn hình đăng nhập toàn phần) |
| **Popover "Vì sao?"** | Bottom sheet cao ≤ 70% màn hình, kéo xuống để đóng | `[R24]` Vinted iOS |
| **Chat** | Xem 7.4 | |

### 7.4 Trợ lý trên mobile

**Hiện trạng code:** Assistant dùng form và kết quả xếp một cột; nhập giọng nói là nút phụ trong form. Chưa có panel bản đồ hoặc giao diện sheet. Bố cục dưới đây là UX mục tiêu; chưa xác minh trực quan trên thiết bị hoặc browser mobile.

```
┌ ← Trợ lý lịch trình        [↻] ┐      ┌ ✕  Lịch trình 3 ngày Nha Trang ┐
│                                │      │ [📍Nha Trang✎][📅3 ngày✎][👨‍👩‍👧✎]→│
│ 🤖 Chào Minh Anh! …            │      │ Chỗ ở cho cả chuyến             │
│  [3 ngày Nha Trang cho gia…]   │      │ ┌ card khách sạn ─────────────┐ │
│                                │ ───▶ │ └─────────────────────────────┘ │
│ 👤 Gợi ý lịch trình 3 ngày …   │ bấm  │ [Ngày 1][Ngày 2][Ngày 3]  (dính)│
│ 🤖 ┌ 📋 Lịch trình 3 ngày ─────┐│ thẻ  │ ☀ Sáng  ┌ card ───────────┐    │
│    │ 5 dịch vụ · ~9.870.000 ₫  ││      │         └──────────────────┘    │
│    │ [Xem kế hoạch]            ││      │ 🌤 Trưa  ActivityNote           │
│    └───────────────────────────┘│      │ …                               │
│ [Đổi thành 2 ngày] [Rẻ hơn]  → │      ├─────────────────────────────────┤
├────────────────────────────────┤      │ 5 dịch vụ · 9.870.000 ₫          │
│ [Nhập yêu cầu chuyến đi…] [➤] │      │ [    Thanh toán tất cả    ]      │
└────────────────────────────────┘      └─────────────────────────────────┘
      Màn hình chat (toàn phần)              Sheet kế hoạch (toàn phần)
```

- Chat chiếm toàn màn hình, tab bar ẩn. Ô nhập dính đáy, đẩy lên theo bàn phím.
- Kế hoạch **không** chia đôi màn hình. Thẻ tóm tắt trong chat mở **sheet toàn màn hình** có tab ngày dính và CTA dính đáy. Pattern: `[R95]` Tripadvisor iOS (kế hoạch AI toàn màn hình + nút nổi "Save itinerary"); `[R124]` Trip.com iOS (TripGenie mở dạng sheet phủ lên trang chủ).
- Chip ý định trong sheet cuộn ngang. Chip gợi ý tiếp theo trong chat cũng cuộn ngang.
- `ProductCard` compact trên mobile: ảnh vuông 64 px trái, 2 dòng tên, giá, nút "+ Thêm" dạng icon + chữ. Ghi chú 💬 và `BecauseLine` bị gập vào "Chi tiết ▾" nếu vượt 3 dòng.
- Thẻ tiến độ 3 bước giữ nguyên trong luồng chat. Nút "Dừng" thay chỗ nút gửi.

---

## 8. Nguồn tham khảo Mobbin

### 8.1 Phương pháp

- Tra cứu qua MCP server `mobbin` (`search_screens`, `search_flows`) ngày 16/09/2026, trên cả nền tảng **web** (bố cục desktop) và **iOS** (bố cục mobile, luồng AI).
- Mỗi màn hình trong phạm vi được tra ít nhất 2–3 app. Mọi pattern trích dẫn trong tài liệu đều đã được xem ảnh chụp màn hình thật trên Mobbin, không suy từ metadata.
- Link dưới đây là link chuẩn của Mobbin (cần tài khoản Mobbin để mở).

### 8.2 Các truy vấn đã chạy

| # | Nền tảng | Truy vấn | Phục vụ |
|---|---|---|---|
| 1 | web | travel booking home page with personalized recommendations carousel based on recent searches | Home |
| 2 | iOS | Airbnb home screen with categories and listing cards | Home, mobile |
| 3 | web | recommendation section labeled "because you viewed" / "based on your booking" | `because` |
| 4 | iOS | upcoming trip card on home with suggestions to add flights, activities or car rental | Home cross-vertical |
| 5 | iOS | product carousel "Because you watched" / "Inspired by your purchase" | `because` |
| 6 | web | hotel search results list with filters sidebar, sort options, price and rating | Search |
| 7 | web | search results page with no results empty state | Search rỗng |
| 8 | iOS | search autocomplete dropdown with destinations and recent searches | Ô tìm kiếm |
| 9 | iOS | Booking.com AI search results for a natural language travel query | Semantic search, Chat |
| 10 | web | hotel detail page with gallery, amenities, room options, sticky reserve | Detail |
| 11 | web | Klook activity ticket detail with package options, date selection, book now | Detail (vé) |
| 12 | web | bottom of hotel detail page with similar properties carousel | `/similar` |
| 13 | web | travel booking checkout with guest contact form and order summary | Checkout |
| 14 | web | booking confirmation page with confirmation number and next steps | Confirmation |
| 15 | web | shopping cart page with items, quantity, remove, subtotal, checkout | Cart |
| 16 | web | empty shopping cart state with CTA | Cart rỗng |
| 17 | web | travel app sign in page with email and password | Login |
| 18 | iOS | sign in prompt explaining benefits like personalized recommendations | Login, Home khách vãng lai |
| 19 | web | choose profile screen with multiple user profile avatars | Tài khoản demo |
| 20 | web | registration form with password requirements | Register |
| 21 | web | AI travel assistant chat with day-by-day itinerary and bookable cards | Chat |
| 22 | iOS | AI trip planner chat with itinerary and inline hotel cards with price | Chat |
| 23 | iOS (flow) | Tripadvisor AI trip builder: destination, dates, companions, interests → itinerary | Chat, chip ý định |
| 24 | web | Mindtrip chat response with place cards, map, add to trip | Chat |
| 25 | iOS | AI generating itinerary loading screen with progress steps | Chat đang xử lý |
| 26 | web | shopping assistant chat reply with product cards and follow-up chips | Chat thẻ sản phẩm |
| 27 | web | chat message failed / AI response error with retry | Chat lỗi |
| 28 | web | loading skeleton placeholders for hotel listing cards | Trạng thái tải |
| 29 | iOS | Agoda/Traveloka hotel detail mobile with sticky bottom price bar | Mobile detail |
| 30 | iOS | mobile hotel search results with sort, filter, map bar | Mobile search |
| 31 | iOS | Traveloka home screen with categories and recommendations | Home (Traveloka) |
| 32 | iOS | Trip.com TripGenie AI chat recommending hotels with bookable cards | Chat |
| 33 | iOS | "Why you're seeing this" explanation sheet for a recommended item | `because` C4 |
| 34 | web | info tooltip explaining how search results are ranked | Search ⓘ |

### 8.3 Bảng tham chiếu

Các mã R27, R28, R32, R50, R63, R71, R93, R99, R102, R106, R116 là màn hình đã xem để đối chiếu nhưng không trở thành quyết định trong thân bài (ví dụ bản đồ kết quả `[R32]` bị loại vì ngoài phạm vi). Chúng được giữ lại để workstream Web tham khảo thêm.

#### Home & cá nhân hóa

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R01 | Klook · web | Trang chủ: ô tìm kiếm + menu danh mục; "Best on Klook" 3 cột xếp hạng | https://mobbin.com/screens/8e6a3075-ec93-4adf-baa9-6ed37b517dce |
| R02 | KAYAK · web | "Your recent searches": thẻ tìm kiếm gần đây kèm giá + "Start a new search" | https://mobbin.com/screens/84ecc10a-5df5-46cb-81cb-0ffd7a8f9cb6 |
| R03 | Tripadvisor · web | "Home Rentals Near You" + câu dẫn "We think you'd enjoy…" cạnh carousel | https://mobbin.com/screens/9fc736da-d712-4aa4-8880-e8fceebb2c2f |
| R04 | Kiwi.com · web | "Our top deals for tonight" + chip lọc thành phố | https://mobbin.com/screens/c144fa19-0d09-4b5b-80b1-7862d47e75ee |
| R05 | Mindtrip · web | Trang chủ lấy chat làm trung tâm + panel "For you in Civic Center" | https://mobbin.com/screens/ba8028f3-3b60-481a-a0f7-d6d69b9022a5 |
| R06 | Airbnb · web | Các hàng carousel "Stay near…", "Popular homes in Paris" | https://mobbin.com/screens/ef8fe96f-1fb9-4b17-97d3-625b20344e39 |
| R07 | Turo · web | "Inspired by your recent searches" | https://mobbin.com/screens/285a792c-4d17-4a67-ab05-9590b6ddc653 |
| R08 | Airbnb · iOS | "Continue searching for experiences in Miami" + "Recently viewed homes" | https://mobbin.com/screens/4f347fd4-5793-41df-a0d9-b29fe02131cc |
| R09 | Booking.com · iOS | "Getting to your stay" · "Add more to your trip" · "Continue planning" (AI) | https://mobbin.com/screens/416ac95c-8c42-4010-af8a-8ac3838ad3ac |
| R10 | Agoda · iOS | My trips: "Missing anything for your trip?" + tab bar | https://mobbin.com/screens/dcf4feee-9ea1-4c59-b25c-a18b020cbc08 |
| R11 | Qantas Airways · iOS | Trips: "Consider for your trip: Book a hotel / Hire a car" | https://mobbin.com/screens/8f6f9d0f-d3fb-448f-837b-4ff90ad8ef82 |
| R12 | Trip.com · iOS | "Plan Your Entire Trip to Ho Chi Minh City — Book 1/6 · Explore · Pack" | https://mobbin.com/screens/09001f60-bb23-4450-932a-69c30a6039e8 |
| R13 | Booking.com · iOS | "Stays in Tokyo — Suggestions based on your recent search" | https://mobbin.com/screens/99b38f71-dfb5-4f59-9620-59b925336151 |
| R14 | Booking.com · iOS | Thẻ "Need help planning your next trip? — Build me an itinerary" | https://mobbin.com/screens/fbbc0b89-c2c0-418a-9333-38e71d8131aa |
| R15 | Best Buy · iOS | "Related to your top categories" + toast "Your home page is updating based on your interests" | https://mobbin.com/screens/8ec18a0e-3056-4985-895c-35fababac79e |
| R16 | Nike · iOS | "Good Morning, Alex" + "Top Picks for You" | https://mobbin.com/screens/671efe4a-9d6c-4425-a302-1a36ab1c93fc |

#### Giải thích gợi ý

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R17 | Google Ads · web | Dòng "Recommended because you've added a conversion action…" + ⓘ | https://mobbin.com/screens/7f77aab3-3a8e-430d-8f9b-9c4b864c1f06 |
| R18 | Hulu · web | Nhãn lý do trên thẻ: "FOR SCI-FI FANS", "FOR COMEDY FANS" | https://mobbin.com/screens/85148469-0943-40b4-b352-868a36359be6 |
| R19 | Codecademy · web | "Based on your benchmark score, here are your recommendations" | https://mobbin.com/screens/eeb1b051-377d-49c0-9438-1d5154b81d71 |
| R20 | Apple Store · iOS | "Recommended for your iPhone 15" + "Compatible with iPhone" | https://mobbin.com/screens/7680ce89-e0b1-4d34-97ce-0c09e1445bd8 |
| R21 | Lovi · iOS | Badge "86% fit" + câu mô tả section (phản ví dụ: điểm như xác suất) | https://mobbin.com/screens/03409905-15d9-448e-ad3f-f795799ed3d9 |
| R22 | Lovi · iOS | Sheet "87% Fit for you — What does this mean?" + lý do đánh số | https://mobbin.com/screens/49f3e8d8-e3bc-472d-bade-24b21a18445f |
| R23 | Instagram · iOS | "Your algorithm — Based on your activity" + toast có "Undo" | https://mobbin.com/screens/c7c4cae7-defb-4f86-9468-5a11cd5fc55b |
| R24 | Vinted · iOS | Bottom sheet "How do search results work?" liệt kê tiêu chí xếp hạng | https://mobbin.com/screens/a5085690-9a3b-4bce-bc3a-dae3dc080702 |
| R25 | Hypelist · iOS | "More like this — If you like: [nguồn] — You might also like:" | https://mobbin.com/screens/d0bb8e4b-7f11-43e5-abd7-d638e26272a9 |
| R26 | Expedia · web | Xác nhận đặt chỗ + "People who bought "Jakarta Museum…" also viewed" | https://mobbin.com/screens/8bc4921e-2b85-4baa-8723-798030b28c47 |
| R27 | UNIQLO · iOS | "People also viewed" + "Recently Viewed" | https://mobbin.com/screens/4532c33a-ec94-446f-be03-1145dc85ded6 |
| R28 | eBay · iOS | "Visually similar items" + "Frequently bought together" | https://mobbin.com/screens/1a0e8ec1-a9e6-403f-81f2-5bbd775c79dd |

#### Search

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R29 | Tripadvisor · web | Kết quả Rome: "Mentions: Classic · Quaint · Family" + khối "Get a personalized itinerary — Build your trip" | https://mobbin.com/screens/282457b9-0132-4e90-9075-f642102e45dc |
| R30 | Kiwi.com · web | "Best match" + "Why results appear this way ⓘ" | https://mobbin.com/screens/614efc20-241e-43b8-865f-6d54dda5595d |
| R31 | Klook · web | Kết quả khách sạn: tab sắp xếp, chip lọc đang áp dụng, tag thuộc tính, giá "incl. taxes per night" | https://mobbin.com/screens/840ddb2e-bbfa-4883-a8ab-a82fddc6c0e2 |
| R32 | Airbnb · web | Lưới kết quả + bản đồ, "Prices include all fees" | https://mobbin.com/screens/4b9d614f-7f68-47bb-83e6-7fd35efca097 |
| R33 | KAYAK · web | Panel lọc (hạng sao, review score) + bản đồ | https://mobbin.com/screens/77e9a3d0-4b77-4a89-b1f8-6bbba8e22f89 |
| R34 | TravelPerk · web | Sắp xếp "Relevance ⓘ" | https://mobbin.com/screens/ba4331ed-3c86-4c7b-bd19-7153a30b5b8b |
| R35 | Booking.com · iOS | Tab "AI search": "Search in your own words ⓘ" + "Try these out" | https://mobbin.com/screens/179c6323-4397-4f7a-9fca-8fcaffae8076 |
| R36 | Booking.com · iOS | Sheet lọc "Smart filters" (mô tả tự do → bộ lọc) + "Show results" dính đáy | https://mobbin.com/screens/3fdd996d-1949-4dcc-b65a-9b0813696cef |
| R37 | Booking.com · iOS | Autocomplete điểm đến có nhãn loại (City/Landmark) + tab AI search | https://mobbin.com/screens/d4c9c008-bc41-4fcf-b8ac-c2529d84bc8c |
| R38 | Skyscanner · iOS | "Recent searches" + "Popular destinations" | https://mobbin.com/screens/82fa285e-d004-4f9c-8fa2-fce2c7f4c3cb |
| R39 | Codecademy · web | Không kết quả: "We couldn't find a match… see what our members are learning" | https://mobbin.com/screens/a70323a2-0f2f-4248-8fb4-92e3a3190967 |
| R40 | Pinterest · web | "Tweak your search" + nút bỏ từng bộ lọc | https://mobbin.com/screens/45560b08-b73e-4f7e-8a82-878c035ddd68 |
| R41 | DoorDash · web | "No Results" + "Reset Search" + danh sách trending | https://mobbin.com/screens/64b6bfdd-4e7c-47e1-a551-06f9f07cf45e |
| R42 | Navan · web | Skeleton thẻ khách sạn trong kết quả | https://mobbin.com/screens/2c395ab1-c8d1-4753-b1d3-7a79935aa2c6 |
| R43 | KAYAK · web | Tab "Cheapest · Best ⓘ · Quickest" hiện trước, thẻ còn là skeleton | https://mobbin.com/screens/3cdd59b9-5d6f-45b4-96df-6efaa42955f3 |
| R44 | Airbnb · web | Lưới skeleton + bản đồ | https://mobbin.com/screens/6f8a0b2c-4cb3-442b-b24b-4849c71b7bf6 |
| R45 | Klook · web | Skeleton trang chủ theo section | https://mobbin.com/screens/232f20e0-32cf-4e46-b40e-8b92ab0da9fc |

#### Product detail

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R46 | Expedia · web | Tabs dính, "Price is typical ⓘ", badge phòng "Often booked for long stays" | https://mobbin.com/screens/c9e7d646-73a8-4d0a-889c-c423fe4ba9b1 |
| R47 | Klook · web | Chọn phòng: cột "Recommended for you", "Only 2 room(s) left!" | https://mobbin.com/screens/fdc8f73e-ffcd-48ad-bfaa-94aa4df13258 |
| R48 | Airbnb · web | "What this place offers" 2 cột + hộp đặt dính + "You won't be charged yet" | https://mobbin.com/screens/7cbdb1f6-a5dd-4afa-a957-a30442256f6e |
| R49 | Tripadvisor · web | Đầu trang chi tiết: rating, xếp hạng, gallery 1 lớn + 3 nhỏ | https://mobbin.com/screens/453ee993-269b-4cc4-9abb-0c3df04b5be3 |
| R50 | Mindtrip · web | Drawer chi tiết khách sạn với "Book" + "Add to trip" | https://mobbin.com/screens/d4266353-8438-47a1-bc73-50fabf3bb896 |
| R51 | Klook · web | Vé: lịch chọn ngày, chọn giờ, stepper số lượng, "Add to cart" + "Book now" | https://mobbin.com/screens/d136df71-7cb1-4db2-a95f-b6d6eed1d00e |
| R52 | Klook · web | Package options + panel "What's included" | https://mobbin.com/screens/34b0d8d8-7715-4906-9b04-475ec45a38e2 |
| R53 | Klook · web | Danh sách gói + chip ngày nhanh "Today / Tomorrow / All dates" | https://mobbin.com/screens/0365db12-73d4-444a-8a8e-61dda2f28d1e |
| R54 | KAYAK · web | "You might also like — Similar hotels" + badge "Similar" | https://mobbin.com/screens/c3762950-abbc-4d5e-a357-813a624b2aa2 |
| R55 | Turo · web | "Similar cars for your dates" | https://mobbin.com/screens/562cf6da-c196-427f-990a-4854b358e09e |
| R56 | Tripadvisor · web | "You may also like — Popular Nearby ⓘ" | https://mobbin.com/screens/f5d5346e-3865-4338-bac7-339af1ca95f0 |
| R57 | Navan · web | Tóm tắt dính "In this booking" + timeline chính sách hủy | https://mobbin.com/screens/2fceec81-80fd-4976-820c-6a7166971db5 |

#### Cart / Checkout / Confirmation

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R58 | Klook · web | Giỏ: mục có ngày + stepper + Manage/Remove, Subtotal + "Book now", "Often booked together" | https://mobbin.com/screens/4c4d6ce8-b969-4584-953b-af03990dd496 |
| R59 | adidas · web | "Your bag" + "Order summary" dính + "Top picks for you" | https://mobbin.com/screens/669358ee-a750-4f11-87ad-0534c5aa0f6c |
| R60 | lululemon · web | Mục giỏ "Save for Later · Edit · Remove" | https://mobbin.com/screens/b1f5f9d8-0fd9-4262-abae-2e01ce1658f8 |
| R61 | Walmart · web | "Recommended with your order" | https://mobbin.com/screens/da785096-b092-45df-a96e-85daefda5036 |
| R62 | Urban Outfitters · web | Spinner phủ đúng mục giỏ đang cập nhật | https://mobbin.com/screens/0e9e2e50-c8b6-4189-bfde-e10e3fb0cac1 |
| R63 | Apple · web | Giỏ rỗng: "Sign in to see if you have any saved items. Or continue shopping." | https://mobbin.com/screens/11115292-ee4e-4a4a-8aa6-696bddef613f |
| R64 | Faire · web | Giỏ rỗng + "Shop bestsellers" + "Recently viewed" | https://mobbin.com/screens/4af927f5-a5a9-4f1b-8666-4c89f789e4bf |
| R65 | Etsy · web | Giỏ rỗng + "Related items you may like" | https://mobbin.com/screens/da6b79ed-14a9-426d-95a9-770a72a52c76 |
| R66 | Klook · web | Checkout: Contact details + tóm tắt phải + Total | https://mobbin.com/screens/e5257642-5203-42e4-9b9d-9236c2b91514 |
| R67 | Tripadvisor · web | Checkout: kiểm tra hợp lệ inline ✓, email khóa, "Book with confidence" | https://mobbin.com/screens/4ed3e550-6d08-4c77-8860-bbddd933ff15 |
| R68 | Airbnb · web | "Confirm and pay": 3 bước đánh số + thẻ tóm tắt | https://mobbin.com/screens/4b00d9f1-234d-413c-901a-0c26bd1def9a |
| R69 | Expedia · web | "Reserve now, pay later" + "Pay today $0.00 / Due at property" | https://mobbin.com/screens/3ab495ee-47d1-4be2-a775-c163f5ade274 |
| R70 | KAYAK · web | Checkout header tối giản, điều khoản ngay trên nút "Confirm booking" disabled | https://mobbin.com/screens/cf7d3f60-9535-495e-bc69-33f4b43e4421 |
| R71 | Navan · web | Checkout contact + "Time left to book" | https://mobbin.com/screens/1ff935f5-cbfb-4a4d-94b4-a150c1f69799 |
| R72 | Tripadvisor · web | "You've booked a good one." + mã xác nhận lớn + "My Bookings" | https://mobbin.com/screens/3af83c09-a051-48dc-8279-faec09d723a5 |
| R73 | Klook · web | "Booking confirmed" + Booking reference ID + chi tiết + chính sách hủy | https://mobbin.com/screens/10b8352a-863b-4fff-b1dd-cf5043d87c91 |
| R74 | Kiwi.com · web | "Payment received!" + "Latest hotel deals in Las Vegas" (gợi ý chéo danh mục) | https://mobbin.com/screens/ce1b3872-77b2-4eb6-a41b-f8491c130185 |
| R75 | KAYAK · web | Chi tiết booking + Summary + Options | https://mobbin.com/screens/b5afe65f-4575-4b4b-b40e-ae3415d11008 |
| R76 | Time2book · web | Thẻ xác nhận gọn + "My schedule" / "Book more" | https://mobbin.com/screens/9db418a8-b527-4c2f-9e24-57e482844c58 |

#### Login / Register

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R77 | Tripadvisor · web | Modal đăng nhập "Welcome back." phủ trang, hiện/ẩn mật khẩu | https://mobbin.com/screens/80a238ee-9dda-4b1a-8755-185caf191f46 |
| R78 | Klook · web | Thẻ "Log in or sign up" trên nền ảnh + câu giá trị | https://mobbin.com/screens/b112b04b-42d7-4687-a560-8256bb29ecd5 |
| R79 | Expedia · web | "Sign in or create an account" 1 cột | https://mobbin.com/screens/085cc190-6152-4b8e-9808-f57a6ceb9b6a |
| R80 | Klarna · web | Modal "Sign in / Or Create account" | https://mobbin.com/screens/8d703065-971f-4700-ac3f-ea5c35ba350b |
| R81 | Best Buy · iOS | Danh sách lợi ích + "Create your free account" + "Continue as guest" | https://mobbin.com/screens/18f1cb2e-a968-4e02-8b01-511229664247 |
| R82 | Skyscanner · iOS | "Get the full experience — Track prices, make trip planning easier" | https://mobbin.com/screens/6d5deedb-0dc0-4f7e-9387-b5c86f27559b |
| R83 | Netflix · web | "Who's watching?": chọn hồ sơ một chạm | https://mobbin.com/screens/9b0cfc61-f627-4691-b3a8-b4ea35110aad |
| R84 | Disney+ · web | "Who's watching?" | https://mobbin.com/screens/8ee39571-97be-42f2-a837-a2e09fed6024 |
| R85 | Sketch · web | "Your password must have" checklist + thanh độ mạnh | https://mobbin.com/screens/4451efbd-9cd8-42d7-bd61-20673e339e73 |
| R86 | Uvodo · web | Checklist mật khẩu ✓ + spinner trong nút | https://mobbin.com/screens/b4e5d7e5-a39f-4196-b41e-f859d737d3ab |

#### Trợ lý / chat AI

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R87 | Booking.com · iOS | "AI chat (beta)": lời chào + "You can try asking about…" chip | https://mobbin.com/screens/ee0f45bb-9e36-44e5-b1fa-f3daeefa05dd |
| R88 | Booking.com · iOS | Itinerary dạng văn bản Day 1 Morning/Afternoon/Evening, mở bằng "I've booked…" (không có thẻ đặt được) | https://mobbin.com/screens/f63db36f-1e69-416c-af58-be8597a82e6b |
| R89 | Mindtrip · web | Thẻ ví dụ có tiêu đề nhóm + thanh chip "Where · When · travelers · Budget" | https://mobbin.com/screens/9cafede9-a6cd-4ada-bae9-5cd82938996e |
| R90 | Mindtrip · web | Modal "What's your travel vibe?" + "Generate itinerary" + panel ngày | https://mobbin.com/screens/ead29c03-f48c-4b54-9bed-f490ffa2f1f7 |
| R91 | Mindtrip · web | Chat trái (địa danh được link hóa) + bản đồ phải | https://mobbin.com/screens/d636b1bc-2496-43c0-939f-99217d6210c2 |
| R92 | Mindtrip · web | Modal "Where": sửa điểm đến của chuyến | https://mobbin.com/screens/fbcc4ca9-213e-4031-a412-d019b031aca2 |
| R93 | Tripadvisor · web | Panel "Ask our AI assistant BETA" + chip câu hỏi gợi ý | https://mobbin.com/screens/8d14f24b-e4a4-4d0d-8e1f-cfeb13bf248b |
| R94 | Tripadvisor · iOS (flow, 16 màn hình) | "Creating a trip (using AI)": ngày/trip length → sở thích dạng chip → itinerary theo ngày → "Add to itinerary" có checkbox + Select all | https://mobbin.com/flows/6ebf5884-66b6-4877-b521-c8a8356c7036 |
| R95 | Tripadvisor · iOS | "This trip is powered by AI." + "Your trip to Island of Hawaii for 5 days for a family" + "Places to stay" | https://mobbin.com/screens/f36b45bd-80f5-4fd4-874a-ee6de4ad8536 |
| R96 | Agoda · iOS | Itinerary ngày 2: hàng "Suggested" có thẻ "Need a flight" với chuyến bay thật + giá | https://mobbin.com/screens/149e9d94-495f-426b-a75b-66224010cca0 |
| R97 | Vrbo · iOS | Itinerary: "Showing AI recommendations" + thẻ "Booked" khác mục hoạt động chữ | https://mobbin.com/screens/96302d51-071e-4786-acb6-a457a1192ac5 |
| R98 | KAYAK · web | Trips: timeline ngày, nhãn "Booked", "No scheduled activities yet" | https://mobbin.com/screens/eb745549-46aa-49e3-bd3b-6b5bde4265f8 |
| R99 | Airbnb · web | Trips: timeline + "Discover experiences for your trip" | https://mobbin.com/screens/78bcb64d-290d-45bf-9442-a03361754fcc |
| R100 | Bard · web | Hộp nhắc lại tham số đã hiểu "check the following flight details…" | https://mobbin.com/screens/8cdcf13b-b0f1-4951-aad2-42a9a2a5fe38 |
| R101 | Wanderlog · iOS | AI Assistant: hộp giới hạn phạm vi/độ chính xác + ví dụ + "Asking questions about New York. Change" | https://mobbin.com/screens/68c8eb0d-d089-4f90-a427-f6daf12aa384 |
| R102 | Trip.com · iOS | TripGenie: bảng so sánh khách sạn trong chat, nhãn "Recommended" | https://mobbin.com/screens/eaf6b7bf-dfb2-4947-ab45-ec0aeea80786 |
| R103 | Trip.com · iOS | TripGenie: thẻ điểm đến/vé có giá "From $29.39" + "You may also ask" | https://mobbin.com/screens/4a7cb8ed-b4ee-43ac-b044-d3d17ca7f775 |
| R104 | Klarna · iOS | Chat mua sắm: carousel thẻ sản phẩm có giá + chip câu hỏi tiếp theo | https://mobbin.com/screens/213a86a1-3bdd-4d7f-9b95-17785df22dc0 |
| R105 | Etsy · web | "Gifting assistant": chat trái + lưới sản phẩm phải, mỗi sản phẩm có câu lý do | https://mobbin.com/screens/ec21bbef-f1a9-49d0-889d-9cea484a1b96 |
| R106 | Amazon · web | Rufus: panel chat bên cạnh trang, thẻ sản phẩm có rating/giá | https://mobbin.com/screens/ace833cd-b503-42e6-a317-16c4a2d3a126 |
| R107 | ChatGPT · web | Thẻ sản phẩm trong chat + "Not interested / More like this" | https://mobbin.com/screens/740b0b9f-805d-46c6-86c1-de07d8b5907b |
| R108 | Shopify · web | Sidekick: thẻ câu hỏi làm rõ có lựa chọn đánh số + Dismiss/Next | https://mobbin.com/screens/6e86f9d6-9202-48ed-8a10-055911b2c0a9 |
| R109 | Wabi · iOS | Thẻ tiến độ nhiều bước khi AI đang tạo | https://mobbin.com/screens/74077ac9-bcc0-481b-88f1-0ddea0c52d11 |
| R110 | Structured · iOS | "Fine-tuning your itinerary…" + Stop | https://mobbin.com/screens/96ffbb47-3a8b-4e98-b2fa-2f7f4d5a87c0 |
| R111 | Instacart · iOS | "Generating your shoppable recipe…" + skeleton | https://mobbin.com/screens/d86eb9ee-13e3-4fc9-9e81-1bc81d9522c7 |
| R112 | X · web | "Failed, Try Again" dưới tin nhắn + toast | https://mobbin.com/screens/744d79ff-4e39-4676-8e2b-058ee762ed01 |
| R113 | Google AI Studio · web | Lỗi hiển thị ngay trong luồng chat + toast | https://mobbin.com/screens/bd6669d2-d3df-476e-b933-e44bb25e5259 |
| R114 | Typeform · web | "Oops! Something went wrong" + Retry / Start over | https://mobbin.com/screens/5794c9e8-ca65-40a4-b2d3-8ed618245921 |
| R115 | Microsoft Copilot · iOS | Itinerary cuối tuần: Day → Morning/Afternoon/Evening + trích dẫn | https://mobbin.com/screens/cde4d55d-c260-4124-b29d-8829c162e03f |
| R116 | PamPam · web | Chat thêm địa điểm vào danh sách với nút "Add" | https://mobbin.com/screens/59da9638-e251-49dc-bf72-6c90a263ecba |

#### Mobile

| Mã | App · Nền tảng | Màn hình / pattern lấy được | Link |
|---|---|---|---|
| R117 | Agoda · iOS | Chi tiết khách sạn: viên tìm kiếm trên đầu + thanh đáy "Start at S$64 · Choose my room" | https://mobbin.com/screens/0b5d9312-19e7-4616-8fed-25640efc54a3 |
| R118 | Agoda · iOS | Vé tham quan: thẻ ngày cuộn ngang + "Most booked" + thanh đáy "See options" | https://mobbin.com/screens/df7b8430-3655-407a-b186-e5663df5cc62 |
| R119 | Agoda · iOS | Checkout: "Special requests" + CTA dính "NEXT: FINAL STEP · You will pay SGD0 today" | https://mobbin.com/screens/b1a4b35a-a2e8-44d6-95ed-ba7d45080842 |
| R120 | Agoda · iOS | Kết quả: chip "Filters 6" / giá / Sort dính + nút nổi List/Gallery/Map | https://mobbin.com/screens/47677fd6-7742-49d4-b2b1-5d90b4600b39 |
| R121 | Skyscanner · iOS | Nút nổi "Sort and filters" | https://mobbin.com/screens/7251bbf3-c9a4-4812-af2a-826f48879ab4 |
| R122 | World of Hyatt · iOS | "Sort By: For You" (phản ví dụ cho Search không cá nhân hóa) | https://mobbin.com/screens/f29aac05-4b42-4fbd-ab70-4d8b5b755d79 |
| R123 | Airbnb · iOS | Danh sách trải nghiệm + tab bar 5 mục | https://mobbin.com/screens/b65a08a7-ad43-46ff-af89-3659df3eaecc |
| R124 | Trip.com · iOS | Trang chủ có khối TripGenie inline + thẻ câu hỏi mẫu | https://mobbin.com/screens/bef05996-a613-40a1-8fff-58569acd0e05 |

### 8.4 Khoảng trống: những gì Mobbin **không** có

Ghi rõ theo brief §3, không bịa nguồn:

1. **Traveloka:** truy vấn #31 ("Traveloka home screen…") không trả về màn hình Traveloka nào, chỉ ra app thương mại khác. Tài liệu không trích dẫn Traveloka.
2. **Vinpearl / V-OTA:** không tra được, và cũng không kỳ vọng có trên Mobbin.
3. **Dòng lý do trên từng thẻ gợi ý, có tên sản phẩm nguồn *và* thời gian** ("Vì bạn đã đặt X · 3 ngày trước"): không OTA nào trên Mobbin làm đúng như vậy. Thiết kế `BecauseLine` (§5.2) là **tổng hợp** từ: tiêu đề section có lý do `[R13]`, câu nêu đích danh sản phẩm nguồn `[R26]`, nhãn lý do trên thẻ `[R18]`, và khối "If you like" `[R25]`.
4. **Hiển thị mức đóng góp của từng lý do** (`contribution`): không tìm thấy pattern. Thang 4 chấm định tính (§5.4) là đề xuất riêng.
5. **Trợ lý lịch trình mà *mọi* mục đặt được đều là thẻ sản phẩm thật có giá + nút:** chưa thấy sản phẩm nào làm trọn vẹn. Gần nhất có Agoda `[R96]` (chèn thẻ chuyến bay thật vào itinerary), Tripadvisor `[R95]` (khối "Places to stay" trong kế hoạch AI), Trip.com `[R103]` (thẻ vé có giá trong chat). Booking.com `[R88]` vẫn trả itinerary **thuần văn bản**, Mindtrip `[R91]` link hóa địa danh trong văn bản. Quy tắc tách `ProductCard` / `ActivityNote` (§6.3–6.4) là đề xuất riêng để đáp ứng handbook §9.
6. **Tiến độ AI gắn với các bước pipeline tìm kiếm thật** (hiểu ý định → tìm → sắp xếp): chỉ có pattern tiến độ nhiều bước chung chung `[R109]`, không có ví dụ du lịch.
7. **Bộ chọn tài khoản demo:** không có trong app du lịch. Mượn từ app streaming `[R83]`, `[R84]`. (Đã gỡ khỏi sản phẩm ngày 2026-09-24, §4.7.3.)
8. **Màn hình chẩn đoán/debug gợi ý:** không có trên Mobbin (app production không công khai). §5.6 là đề xuất riêng.
9. **Trạng thái "kết quả yếu" của semantic search:** không có pattern, vì các OTA đều dùng tìm kiếm có cấu trúc. §4.2.4 là đề xuất riêng.

---

## 9. Câu hỏi thiết kế cần đối chiếu khi tích hợp

Danh sách dưới đây ghi lại các câu hỏi lúc soạn UX spec, không phải trạng thái hiện hành của API contract. Contract hiện tại lấy từ `src/shared/contracts/openapi.yaml` cùng các file liên quan. Một số mục có thể đã được contract trả lời nhưng frontend vẫn chưa nối tới; cần đối chiếu contract trước khi coi là phụ thuộc schema chưa chốt.

| # | Câu hỏi | Ảnh hưởng UI | Mặc định UI nếu chưa có câu trả lời |
|---|---|---|---|
| D1 | Các giá trị `strategy` ngoài `cross_vertical` (cold start, dormant…) | Tiêu đề section §5.3, persona P2–P4 | Map mọi giá trị lạ về "Có thể bạn quan tâm" |
| D2 | `because[]` có thể thêm `productId` (và/hoặc `imageUrl`) không? | Link + ảnh sản phẩm nguồn trong popover §5.4 | Chỉ hiện tên, không link, không ảnh |
| D3 | Ai ghi event `product_view`: Backend khi đọc sản phẩm, hay Web gọi riêng? | Gợi ý của P2 | Web gọi endpoint ghi event nếu có |
| D4 | `/search` hỗ trợ lọc `taxonomy`, `destination`, khoảng giá không? Có trả ngưỡng/điểm để xác định "kết quả yếu"? | Bộ lọc, trạng thái kết quả yếu §4.2 | Lọc client-side trên top-K; không hiện băng "kết quả yếu" |
| D5 | Endpoint "phổ biến" cho Home công khai / cold start | Section ④ Home | Dùng `/search` với vài truy vấn cố định theo điểm đến |
| D6 | Giỏ lưu server hay client? | Đăng nhập lần lượt nhiều tài khoản không lẫn giỏ §4.4 | Client, khóa theo `cdp_user_id` |
| D7 | Checkout gán `eventGroupId` thế nào khi giỏ có nhiều điểm đến? | Gom nhóm "Chuyến {destination}" §4.4 | Gom theo `destination` ở UI |
| D8 | Endpoint đọc booking theo `referenceCode` | Tải lại trang Confirmation §4.6 | Giữ dữ liệu trong state điều hướng; tải lại thì báo không tìm thấy |
| D9 | Event SSE itinerary gắn với bước pipeline nào? | Thẻ tiến độ §6.1 | Spinner chung, chỉ đánh ✓ theo event đã xác nhận |
| D10 | Chat: hình dạng response (§6.4) và việc nhận ý định có cấu trúc để tạo lại kế hoạch | Chip ý định sửa được §6.2 | Sửa chip = gửi tin nhắn văn bản "Đổi thành 2 ngày" |
| D11 | Sản phẩm có nhiều ảnh không? | Gallery §4.3 | 1 ảnh full-width |
| D12 | Ngữ nghĩa ngày của vé máy bay trong dữ liệu (cố định hay theo khoảng) | Hộp đặt vé máy bay §4.3.3 | Hiển thị `availableFrom` dạng chỉ đọc |
| D13 | Danh sách "sản phẩm đã xem gần đây" cho Home ② | Section ② | Bỏ section |

Các câu hỏi này phát sinh trong giai đoạn thiết kế. Đối chiếu từng luồng với trạng thái code tại §1.5 và OpenAPI hiện hành; các mặc định trong bảng không thay thế contract.
