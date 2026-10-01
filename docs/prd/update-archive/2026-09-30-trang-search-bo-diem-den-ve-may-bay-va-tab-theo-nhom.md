# Trang /search: bỏ lọc điểm đến, bỏ vé máy bay, tab theo nhóm dịch vụ, chỉ sắp xếp giá trong cùng loại

- Ngày: 2026-09-30
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-30 (chốt cả hai mặc định ở "Cần bạn quyết định")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.2 (FR-SRC-03); `docs/prd/user-flow.md` §2 (dòng `/search`); `docs/spec/product.md` §4.2 (wireframe, bảng thành phần); `docs/spec/hop-dong-tich-hop-frontend.md` §4.2
- Mã FR/NFR: FR-SRC-01, FR-SRC-03 (AC-SRC-01 không đổi)

## Lý do

`/search` là tìm kiếm **ngữ nghĩa**: câu người dùng gõ có thể là sân golf, resort, vé vui chơi… nên không biết trước điểm đến, và checkbox "Điểm đến" cố định 5 thành phố làm sai logic (gõ "sân golf" mà tick "Nha Trang" là lọc ngược ý). Ngoài ra:

- Vé máy bay có rất nhiều chuyến mà dữ liệu chưa đủ để xếp hạng ngữ nghĩa, nên không đưa vào trang này.
- Ba nhóm ở header (Lưu trú · Tour và trải nghiệm · Tiện ích khác) đã là cách người dùng hình dung danh mục; tab hiện tại (Khách sạn, Vé máy bay, Vé tham quan, Combo, Golf) lệch với header.
- Sắp xếp "giá thấp → cao" chỉ có nghĩa khi cùng một loại (khách sạn theo đêm, vé theo khách, combo theo gói); trộn nhiều loại thì thứ tự vô nghĩa.

## Nội dung đề xuất

1. **Bỏ bộ lọc "Điểm đến"** trên `/search` (checkbox ở thanh bên và chip "Đang lọc"). `requirements.md` FR-SRC-03 mục "Địa điểm": *"Địa điểm (Điểm đến, thành phố, khu vực)"* → *"Địa điểm: áp dụng ở API `/search` và tấm tìm kiếm của trang danh mục; trang `/search` không có bộ lọc điểm đến, điểm đến do câu truy vấn ngữ nghĩa quyết định."*
2. **Bỏ vé máy bay khỏi `/search`:** không có tab "Vé máy bay", "Tất cả" không gồm vé máy bay. Vé máy bay chỉ duyệt/tìm ở `/flights`.
3. **Tab theo nhóm header:** *Tất cả · Khách sạn · Vé máy bay · Vé tham quan · Combo · Golf* → *Tất cả · Lưu trú (hotel) · Tour và trải nghiệm (attraction + golf) · Tiện ích khác (combo)*. Tab hiện số kết quả; tab 0 kết quả vẫn hiện (không ẩn) để bố cục ổn định — nếu muốn giữ luật cũ "tab rỗng thì ẩn" thì nói lại.
4. **Tab "Tất cả":** không phải danh sách phẳng mà là các hàng theo nhóm (Lưu trú, Tour và trải nghiệm, Tiện ích khác), mỗi hàng cuộn ngang, cuối hàng có thẻ "Xem tất cả" chuyển sang tab của nhóm. Không có sắp xếp.
   - Nút trái/phải nằm giữa chiều cao hàng, sát hai bên; nút trái ẩn khi đang ở đầu hàng, nút phải ẩn khi đã tới cuối hoặc hàng không tràn.
   - Chỉ tải vài mục đầu mỗi nhóm (đề xuất 6) để trang nhanh; kết quả được cache theo khóa (truy vấn + nhóm + giới hạn) trong phiên. Danh sách đầy đủ chỉ tải khi người dùng mở "Xem tất cả" hoặc tab của nhóm, và cũng được cache để quay lại không tải lại.
5. **Sắp xếp** là một popup (nút "Sắp xếp: Phù hợp nhất ▾" mở menu Phù hợp nhất · Giá thấp → cao · Giá cao → thấp) ở **mọi tab trừ "Tất cả"**. Bộ lọc hạng sao và mức giá tối đa vẫn chỉ ở tab Lưu trú.
6. Không đổi contract: "Tất cả" gọi `POST /search` riêng cho từng loại (hotel, attraction, golf, combo) với `limit` nhỏ; tab nhóm gọi với `limit` đầy đủ; không gọi `taxonomy=flight`.

### Cần bạn quyết định

- **Đường vào từ `/flights`:** tấm tìm kiếm ở trang Vé máy bay hiện điều hướng sang `/search?type=flight`. Đề xuất mặc định: giữ nguyên đường này như một ngoại lệ (chỉ khi `type=flight`, không hiện thanh tab, một danh sách phẳng), vì bỏ hẳn sẽ làm `/flights` mất đường tìm. Nếu bạn muốn `/flights` không gọi `/search` nữa thì cần một đề xuất riêng cho trang kết quả chuyến bay.
- **`?destination=` trong URL:** tấm tìm kiếm ở `/hotels`, `/experiences`, `/combos` vẫn gửi điểm đến khi người dùng chọn. Đề xuất mặc định: vẫn truyền cho API, hiện thành một chip có ✕ ở "Đang lọc" nhưng không có checkbox điểm đến. Nếu muốn bỏ hẳn thì tấm tìm kiếm chỉ đưa vào `q`.

## Thay đổi source sau khi chốt

- `src/frontend/src/components/search/SearchView.tsx` — tab mới, bỏ checkbox điểm đến, hàng cuộn ngang ở "Tất cả", điều kiện hiện sắp xếp/lọc sao/giá.
- `src/frontend/src/services/search.ts` — bỏ `flight` khỏi `categoryCounts` và `DEFAULT_QUERY` dùng cho tab; hàm gom kết quả theo nhóm.
- `src/frontend/src/components/common/SearchBox.tsx` — bỏ gợi ý "Vé máy bay Hà Nội - Đà Nẵng" ở `/search`.
- `src/frontend/tests/unit/` — test cho tab, nhóm, điều kiện sắp xếp.
- Cập nhật `docs/prd/requirements.md`, `docs/prd/user-flow.md`, `docs/spec/product.md`, `docs/spec/hop-dong-tich-hop-frontend.md` theo nội dung đã chốt; entry `history/`.
