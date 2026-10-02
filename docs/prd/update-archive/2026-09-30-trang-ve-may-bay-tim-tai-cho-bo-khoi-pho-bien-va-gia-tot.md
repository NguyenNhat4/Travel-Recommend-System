# Trang /flights: tìm và hiện chuyến bay ngay tại chỗ, bỏ hai khối phổ biến và giá tốt

- Ngày: 2026-09-30
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-30 (yêu cầu trực tiếp trong chat: "bỏ phần chặng bay phổ biến và vé giá tốt"; trước đó: "làm phần ở dưới, tìm kiếm không ra trang khác, chưa có thì hiển thị cho người dùng phải nhập")
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §2 (bảng route, dòng `/flights`)
- Mã FR/NFR: FR-SRC-03 ("vé máy bay chỉ duyệt và tìm ở `/flights`"), FR-BKG-10; không đổi FR/NFR/AC

## Lý do

Trang `/flights` hiện là trang danh mục như `/hotels`: hero, tấm tìm kiếm, hai khối sản phẩm ("Chặng bay phổ biến", "Vé giá tốt nhất") và điểm đến. Tấm tìm kiếm chuyển người dùng sang `/search?type=flight`, một danh sách phẳng các tuyến. Người dùng muốn vé máy bay tìm và chọn ngay trên `/flights`: chuyến bay của lần tìm hiện bên dưới tấm tìm kiếm (bộ lọc, dải ngày, "Vé của tôi"), không sang trang khác; chưa tìm hoặc còn thiếu thông tin thì chỉ nhắc nhập; hai khối phổ biến và giá tốt bỏ đi.

## Nội dung đề xuất

`docs/prd/user-flow.md` §2, dòng `/flights`:

- Hiện tại: "Duyệt chặng bay và bắt đầu tìm vé theo điểm đi, điểm đến, ngày, hành khách" | "Hero, Search Sheet, Product Shelves, Destination Tiles"
- Thay bằng: "Tìm vé theo điểm đi, điểm đến, ngày, hành khách và chọn chuyến bay ngay tại trang; chưa nhập đủ thì trang nhắc nhập" | "Hero, Search Sheet, Kết quả chuyến bay (Filter Sidebar, Date Strip, Sort popup, Flight Cards, Vé của tôi) hoặc lời nhắc nhập, Destination Tiles"

Không đổi: các dòng `/hotels`, `/experiences`, `/combos`; FR-SRC-03 (vẫn "chỉ duyệt và tìm ở `/flights`"); AC. `/search?type=flight` vẫn mở được bằng URL trực tiếp nhưng tấm tìm kiếm không dẫn tới đó nữa.

## Thay đổi source sau khi chốt

- `src/frontend/src/app/(storefront)/flights/page.tsx`, `src/features/flights/FlightsPage.tsx`: bỏ hai khối `CatalogShelf` ở `/flights`, giữ Destination Tiles và banner trợ lý.
- `docs/spec/hop-dong-tich-hop-frontend.md` §4.1a, §4.1b; `docs/spec/product.md` §4.2.0; `src/frontend/README.md`.
