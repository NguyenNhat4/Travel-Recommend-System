# Khách sạn trùng tên đang bán: gộp 23 nhóm trên production và chặn tái diễn khi nạp DB

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: fix/full-refresh-stable → đẩy lên `test/newcrawl`
- Trạng thái: hoàn thành phần code; script production chờ người dùng chạy
- Phạm vi: data

## Mục tiêu

Rà 29 nhóm sản phẩm đang bán trùng tên + điểm đến trên production (sau khi đã sửa vé Vinpearl,
`history/2026-10-08-ve-thanh-vien-vinpearl-trung.md`). Phục vụ FR-CAT-01 (mỗi sản phẩm một dòng). Không lệch PRD.

## Phân loại (dữ liệu production 08/10 ~15:00, API monitor chỉ đọc)

- A. 20 nhóm cùng khách sạn ở hai nguồn (Booking + Agoda/Trip), cùng địa chỉ, cách 0–300 m (Blue Ocean lệch toạ độ 975 m, cùng
  số nhà). Nguyên nhân: dòng Booking của snapshot 23/09 không được cào lại, bước gộp trùng của chuẩn hoá chỉ ghép nguồn có mặt
  trong cùng lượt. Bằng chứng: lượt thử local làm mới cả catalog (Nha Trang) đã tự gộp 4/4 nhóm Nha Trang có trong bản sao
  (Daisy Flower, Havana, Nha Trang Lodge, Rembrandt): dòng Booking giữ + `sameAs`, dòng kia `mergedInto`, tắt bán.
- B. 3 nhóm cùng nguồn đăng hai lần: Behomestay (2 tin Booking cùng địa chỉ), Sadec Garden Boutique (2 tin Agoda cùng giá),
  Miếu Bà Chúa Xứ Núi Sam (2 điểm Trip cách 123 m). Chuẩn hoá không gộp cùng nguồn.
- C. 6 nhóm khác nhau thật, giữ: L'Azur Cửa Lò (3 nhóm, 7 căn hộ khác chủ), TMS Quy Nhơn View Biển (2 căn), 2 tour Mũi Né
  Booking khác nhà cung cấp / giá.

Người dùng chọn: A gộp ngay bằng script + sửa code để không gặp lại; B ẩn bản trùng bằng script.

## File thay đổi

- `src/data_collection/fresh_catalog_db.py` — sửa: `match_existing_hotels` (khách sạn mới không khớp ref nào → dòng khách sạn
  NGUỒN KHÁC trong DB cùng điểm đến, tên ≥ 97 theo `normalise.name_score`, ≤ 1 km hoặc thiếu toạ độ, dòng kia chưa có bản của
  nguồn này, không phải căn hộ/homestay/condotel, ứng viên duy nhất); `prepare_rows` ghi dòng mới đó ẩn `mergedInto` dòng có
  sẵn, chuyển phòng con sang dòng giữ, ref vào `sameAs` dòng giữ (`_link_db_matches`, `counts.dbMatched`); dòng đã `mergedInto`
  một dòng còn trong DB mà nguồn vẫn đăng riêng thì giữ ẩn, phòng cùng nguồn của nó ẩn theo (`counts.keptMerged`) — trước đây
  lượt cào bật lại.
- `src/data_collection/tests/test_db_hotel_match.py` — thêm: 4 test (gộp khách sạn mới vào dòng nguồn khác + lượt sau khớp
  thẳng; 7 trường hợp không được gộp: tên khác, > 1 km, dòng DB đã có bản Agoda khác, cùng nguồn, căn hộ, khác điểm đến, hai ứng
  viên; thiếu toạ độ một bên vẫn gộp khi tên trùng; tin trùng cùng nguồn đã gộp không sống lại).
- Ngoài git (thư mục `data/` bị ignore, repo chính): `src/data_collection/data/vm-repair-20261008/merge_hotel_dups.py` — danh
  sách 20 + 3 nhóm đã duyệt; A: giữ theo thứ tự nguồn của normalise (booking < agoda < trip), dòng kia `mergedInto` + tắt bán,
  phòng chuyển sang dòng giữ, ref vào `sameAs`; B: giữ dòng thấy gần nhất / nhiều phòng hơn, dòng kia và phòng của nó
  `mergedInto` + tắt bán; nhóm khác lúc rà thì bỏ qua; chạy thử + rollback mặc định, `--apply --expect N`, sao lưu, khoá job.

## Kiểm tra

- `pytest -q tests` (`src/data_collection`, vsf2): 582 passed, 27 skipped. Test Postgres thật (`STREAM_TEST_ADMIN_URL`,
  `SIMULATED_TEST_DATABASE_URL`): 15 passed, 2 failed — đúng 2 test đỏ có sẵn trên code gốc (ghi ở
  `history/2026-10-08-monitor-tien-do-va-buoc-con.md`).
- Script trên bản sao local `vota_prodcopy` (07/10, trước lượt 08/10 nên thiếu 8 dòng Agoda/Trip của nhóm A): chạy thử 15 dòng
  (A 12, B 3), bỏ qua 8 (đúng); `--apply --expect 15` trên bản sao tạm: chuyển 45 hạng phòng, ẩn 9, 0 hạng phòng đang bán dưới
  dòng đã gộp; chạy `maintain_catalog` của code đang trên VM (85cea82) rồi code mới lên bản sao đó: vẫn 0 dòng `mergedInto`
  đang bán, danh sách làm mới bỏ dòng đã ẩn. Bản sao tạm đã xoá.

## Còn lại / rủi ro

- Người dùng chạy script trên production: chạy thử phải ra 23 dòng (A 20, B 3), 0 bỏ qua, rồi `--apply --expect 23`; sau đó
  "còn N nhóm trùng tên" kỳ vọng 6 (nhóm C).
- Dòng giữ của nhóm A nhận ref Agoda/Trip trong `sameAs`: lượt nào chỉ cào được bản Agoda/Trip (Booking lỗi) thì bản đó làm mới
  dòng Booking (hành vi có sẵn với 192 dòng Booking đã gộp Agoda).
