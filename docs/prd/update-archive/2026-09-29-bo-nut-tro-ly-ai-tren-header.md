# Gỡ viên "Trợ lý AI" khỏi thanh điều hướng của header

- Ngày: 2026-09-29
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29 (trả lời "Đã chốt: gỡ khỏi header" cho câu hỏi chốt đề xuất này trong phiên làm việc)
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §4.1 (wireframe Trang chủ, dòng thanh điều hướng)
- Mã FR/NFR: FR-AGT-01 (lối vào trợ lý). Không đổi yêu cầu và không đổi AC-AGT-01; chỉ bớt một trong nhiều lối vào.

## Lý do

Người dùng kiểm tay trang `/flights` ngày 29/09/2026 và nêu hai điểm về viên "Trợ lý AI" trên header:

1. Viên này dẫn tới trang `/assistant`, tức giao diện trợ lý cũ. Giao diện trợ lý hiện hành là widget nổi (linh vật ở góc dưới phải), đã có mặt ở mọi trang trừ `/checkout` và `/assistant` (`AppShell.tsx`).
2. Header đang có quá nhiều thành phần cùng cạnh tranh sự chú ý (bốn nhóm dịch vụ, nút lưới, Trợ lý AI, ngôn ngữ, giỏ, tài khoản); người dùng quyết định không hiển thị Trợ lý AI trên header.

Đề xuất này đảo lại một điều đã chốt trong cùng ngày: wireframe `user-flow.md` §4.1 có `[Trợ lý AI]` (đề xuất đã lưu trữ `update-archive/2026-09-29-route-trang-danh-muc-dich-vu.md`, giả định A3 của `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md`).

## Nội dung đề xuất

**`docs/prd/user-flow.md` §4.1, wireframe Trang chủ, dòng thanh điều hướng**

- Hiện tại: `| [LOGO] V-OTA  Di chuyển v  Lưu trú v  Tour và trải nghiệm v  Tiện ích khác v  [Trợ lý AI] [VN] [Tài khoản v] |`
- Thay bằng: `| [LOGO] V-OTA  Di chuyển v  Lưu trú v  Tour và trải nghiệm v  Tiện ích khác v  [VN] [Tài khoản v] |`

Không đổi: route `/assistant` (§2), luồng §3.2, FR-AGT-01, AC-AGT-01. Trợ lý vẫn có các lối vào còn lại: widget nổi ở mọi trang (trừ checkout và `/assistant`), ô tìm kiếm AI ở hero Home, thẻ trợ lý ở Home, Search, Chi tiết sản phẩm và Xác nhận đơn, tab "Trợ lý" của thanh tab dưới trên mobile.

Kèm theo ở cấp spec (không thuộc PRD, ghi để người duyệt thấy đủ phạm vi): mục "Trợ lý lịch trình AI" trong menu "Tiện ích khác" cũng bị bỏ, vì cùng là lối vào trợ lý trên header và cùng dẫn tới `/assistant`. Nhóm này còn một mục "Combo du lịch".

## Ảnh hưởng và rủi ro

- Desktop mất một lối vào trợ lý ở header; widget nổi luôn hiện ở góc dưới phải nên trợ lý vẫn mở được từ mọi trang.
- Không đổi contract, DB, backend, mock.
- Mobile không đổi: header mobile vốn chỉ có logo, ngôn ngữ, tài khoản; tab bar dưới giữ tab "Trợ lý" (`product.md` §7.2).
- Các nút khác dẫn tới `/assistant` (tab bar mobile, giỏ hàng, Search) không thuộc đề xuất này và giữ nguyên.

## Thay đổi source sau khi chốt

- `src/frontend/src/components/common/Header.tsx`: bỏ viên "Trợ lý AI".
- `src/frontend/src/components/layout/nav/navConfig.ts`: bỏ mục `assistant` khỏi `NAV_ITEMS` và khỏi nhóm `more`; bỏ icon `sparkles` nếu không còn nơi dùng.
- Test: `src/frontend/tests/unit/navConfig.test.ts`, `navMenu.test.tsx`.
- Tài liệu: `docs/prd/user-flow.md` §4.1; `docs/spec/product.md` §3.3, §4.8.2; `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md` (A1, A3).
