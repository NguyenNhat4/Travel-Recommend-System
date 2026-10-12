# Đổi tên hiển thị trên giao diện từ V-OTA sang X-OTA

- Ngày: 2026-10-09
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã chốt (thu hẹp: chỉ frontend, chưa cập nhật PRD)
- Chốt bởi / ngày: mihhquan, 2026-10-09
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` (wireframe header `[LOGO] V-OTA`, §3); `docs/spec/product.md` (các câu chữ hiển thị chứa "V-OTA"); các tiêu đề và đoạn mở đầu `docs/prd/*.md` nếu chốt đổi cả tên tài liệu (phương án B)
- Mã FR/NFR: không đổi FR/NFR nào; chỉ đổi tên thương hiệu hiển thị. Liên quan FR-BKG-06, NFR-SEC-03 (câu "V-OTA không nhận dữ liệu thẻ") ở phần câu chữ.

## Quyết định của người dùng (2026-10-09)

Chỉ sửa giao diện frontend (`src/frontend`), vì đây chỉ là đổi tên logo/hiển thị. **Không** sửa backend, mock, PRD hay `docs/spec`.
Các mục "backend và mock" và "phương án tài liệu A/B" bên dưới không áp dụng. PRD vẫn ghi V-OTA theo ý người dùng.

## Lý do

Người dùng yêu cầu refactor mọi chỗ giao diện đang hiển thị tên **V-OTA** thành **X-OTA**. PRD và `docs/spec/product.md`
đang ghi tên sản phẩm là V-OTA (logo header, tiêu đề trang, câu thông báo, chân trang), nên đổi tên hiển thị là lệch PRD
và phải chốt trước khi sửa source (AGENTS.md mục 8).

## Nội dung đề xuất

Chỉ đổi **chữ người dùng nhìn thấy**. Giữ nguyên mọi định danh kỹ thuật.

**Đổi (phạm vi chính, `src/frontend/src`)**

- Header (logo chữ, `aria-label`), Footer (tên, bản quyền, "ứng dụng X-OTA Booking"), `LoginView`, `LoginModal`.
- Tiêu đề và mô tả trang (`layout.tsx`, `hotels`, `flights`, `experiences`, `combos`), `metadata.json` của frontend.
- Câu chữ trong trang chi tiết, kết quả chuyến bay, tìm kiếm, giỏ hàng, thanh toán, xác nhận đơn, lịch sử đơn, WhyPopover,
  bản đồ lịch trình, widget Trợ lý ("Trợ lý du lịch X-OTA", "Lên kế hoạch cùng X-OTA"), `TravelContext`.
- Câu gợi ý và placeholder ở trang chủ (`HomeView`, `recentSearches`) ví dụ "Tìm resort V-OTA view biển…".
- `server/routes/trips.ts` (tên người gửi mặc định "Du khách V-OTA").
- Chuỗi giao diện trong test (`src/frontend/tests/`) cập nhật theo để test vẫn khớp.

**Đổi (câu chữ do backend trả ra, hiển thị nguyên văn trên UI)**

- `src/backend/app/api/errors.py` (`PRODUCT_NOT_FOUND`: "Sản phẩm này không còn trên X-OTA.") và các mock tương ứng trong
  `src/shared/mocks/` (`getProduct.404-not-found.json`, `trackEvent.404-product-not-found.json`,
  `createItinerary.422-unsupported-destination.json`). Đây chỉ là giá trị chuỗi `message`, không đổi field hay semantics
  của contract.
- Lời Trợ lý (prompt, narrate) trong `src/backend/app/agents` hiện **không** chứa "V-OTA" nên không phải sửa.

**Không đổi**

- Tên kỹ thuật: database `vota`, role `vota_app`, `db/vota_schema.sql`, khoá localStorage/cookie, tên package, biến môi trường,
  tên container, đường dẫn repo, tên collection Weaviate, log nội bộ.
- Dữ liệu sản phẩm thật trong catalog (tên khách sạn do nguồn đặt) và snapshot dữ liệu; mock seed persona
  (`src/frontend/src/data/personas.ts`) chỉ đổi nếu chốt là hiển thị tên khách sạn mẫu (xem câu hỏi dưới).
- Bình luận mã, README, tài liệu `docs/` ngoài hai file đã nêu ở phương án A.

**Hai phương án cho tài liệu**

- **A (khuyến nghị):** chỉ sửa PRD ở chỗ mô tả giao diện (`user-flow.md` wireframe, `docs/spec/product.md` câu chữ hiển thị),
  ghi chú "tên hiển thị: X-OTA; V-OTA là tên mã dự án". Tên tài liệu và tên kỹ thuật giữ V-OTA.
- **B:** đổi toàn bộ chữ V-OTA trong `docs/prd/` và `docs/spec/` thành X-OTA (đồng bộ hoàn toàn, nhưng chạm nhiều file và
  bản ghi lịch sử, báo cáo eval).

**Câu hỏi cần người dùng trả lời khi chốt**

1. Chọn phương án tài liệu A hay B?
2. Có đổi cả tên khách sạn mẫu "V-OTA Resort Nha Trang…" trong `personas.ts` và câu gợi ý "Resort V-OTA Nha Trang" không?
   (đây là tên sản phẩm mẫu, không phải tên thương hiệu; đề xuất giữ tên sản phẩm mẫu như dữ liệu và chỉ đổi câu gợi ý nếu
   trong catalog thật không có sản phẩm tên đó).
3. Có đổi cả `© 2026 V-OTA Joint Stock Company` thành tên pháp nhân X-OTA không, hay chỉ đổi chữ V thành X?

## Thay đổi source sau khi chốt

- `src/frontend/src/**` và `src/frontend/server/routes/trips.ts`, `src/frontend/metadata.json` (danh sách file ở mục trên,
  đối chiếu bằng `grep -rn "V-OTA" src/frontend`).
- `src/frontend/tests/**` — cập nhật chuỗi mong đợi.
- `src/backend/app/api/errors.py`, `src/shared/mocks/{catalog,events,assistant}/*.json` — chuỗi `message`; chạy
  `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`.
- `docs/prd/user-flow.md`, `docs/spec/product.md` (và phần còn lại nếu chọn B).
- Test: unit frontend (`homeView`, `productDetailView`, `confirmationView`, `searchView`…), e2e `routes.spec.ts`,
  test backend chạm `errors.py`.
