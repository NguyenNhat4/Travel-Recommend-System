# Thêm bốn trang danh mục dịch vụ và thanh điều hướng theo nhóm

- Ngày: 2026-09-29
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-29 (tin nhắn "Tôi chốt với đề xuất hãy hoàn thành plan", sau khi xem plan `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md`)
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §2 (bảng route), §4.1 (wireframe Trang chủ, thanh điều hướng)
- Mã FR/NFR: FR-CAT-01, FR-SRC-01, FR-SRC-03 (không đổi yêu cầu; chỉ bổ sung route và điều hướng cho phạm vi "duyệt danh mục" đã có ở `project-brief.md` §4.1)

## Lý do

`project-brief.md` §4.1 đã đưa "duyệt danh mục" vào phạm vi, nhưng bảng route ở `user-flow.md` §2 chỉ có Trang chủ, `/search` và các màn khác; không có trang nào để duyệt theo từng loại dịch vụ. Hệ quả hiện tại: bốn nút "Di chuyển / Lưu trú / Tour và trải nghiệm / Tiện ích khác" trên header chỉ chuyển sang `/search?type=…`; Trang chủ phải gánh cả vai trò trang khách sạn nên tải mọi khối dữ liệu cùng lúc. Người dùng yêu cầu tách mỗi nhóm dịch vụ thành trang riêng theo bố cục trang khách sạn của VP-OTA.

## Nội dung đề xuất

**`docs/prd/user-flow.md` §2, bảng route — thêm bốn dòng sau dòng `/`:**

| Tuyến đường | Tên màn hình | Mục đích chính | Thành phần cốt lõi |
|---|---|---|---|
| `/hotels` | **Khách sạn & resort** | Duyệt và bắt đầu tìm khách sạn theo điểm đến, ngày, số phòng và số khách | Hero, Search Sheet, Product Shelves (phổ biến, giá tốt), Destination Tiles |
| `/flights` | **Vé máy bay** | Duyệt chặng bay và bắt đầu tìm vé theo điểm đi, điểm đến, ngày, hành khách | như trên |
| `/experiences` | **Tour và trải nghiệm** | Duyệt vé tham quan, vui chơi và sân golf (`?type=attraction\|golf`) | như trên, kèm tab loại |
| `/combos` | **Combo du lịch** | Duyệt gói kết hợp | như trên |

Bốn route công khai (không cần đăng nhập) và nhận tham số `destination`. Tấm tìm kiếm chuyển sang `/search` kèm ngày và số khách; ngày và số khách là ngữ cảnh chuyến đi để điền sẵn hộp đặt, không phải bộ lọc phòng trống.

**`docs/prd/user-flow.md` §4.1, wireframe Trang chủ, dòng thanh điều hướng:**

- Hiện tại: `[LOGO] V-OTA       Khách sạn   Vé máy bay   Tour   Trợ lý AI   [Tài khoản v]`
- Thay bằng: `[LOGO] V-OTA   Di chuyển v   Lưu trú v   Tour và trải nghiệm v   Tiện ích khác v   [Trợ lý AI] [VN] [Tài khoản v]`, mỗi nhóm mở menu con trỏ tới các route trên; "Trợ lý AI" giữ là lối vào riêng.

## Thay đổi source sau khi chốt

- `src/frontend/src/app/(storefront)/{hotels,flights,experiences,combos}/page.tsx` và `src/frontend/src/features/catalog/landing/*` (trang danh mục).
- `src/frontend/src/components/layout/nav/*`, `components/common/Header.tsx`, `components/layout/AppShell.tsx` (điều hướng nhóm).
- `src/frontend/src/components/home/HomeView.tsx` (Home tổng quan, tải lười).
- Spec: `docs/spec/hop-dong-tich-hop-frontend.md` §3, §4.1; `docs/spec/product.md` §3.1, §3.3, §4.1, §4.2.1, §7.2.
- Không đổi OpenAPI, DDL, backend.
