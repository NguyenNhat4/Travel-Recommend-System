# Mục 4 rà soát production: điểm đến, toạ độ, mở rộng Tuyên Quang; gộp dữ liệu của bàn giao "chùa ở HCM"

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở — job xong; production chưa sửa (115 dòng + nạp 41 điểm, sau khi merge vào `release-mvp-v2` + CD crawler deploy)
- Phạm vi: data

## Mục tiêu

Người dùng (13/10): "để mục 4 sửa toạ độ, làm mục 4 luôn" — mục 4 của `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md`
(toạ độ tâm điểm đến, thiếu toạ độ, Tuyên Quang chỉ 3 điểm). Giữa chừng người dùng hỏi bàn giao "chùa ở HCM"
(`docs/plan/2026-10-13-ban-giao-dieu-tra-agent-search-chua-hcm.md`, repo chính, nhánh `bench_search_recomSys`, chưa commit) có phải cùng
vấn đề không → không, nhưng phần data §11.2 trùng phạm vi; người dùng chốt gộp các mục đã liệt kê. FR-CAT-01, FR-CAT-02, FR-SRC-03,
NFR-REL-01. Không lệch PRD (dữ liệu soát tay theo cơ chế CSV đã có).

## File thay đổi

- `src/data_collection/collectors/destination_overrides.csv` — sửa: +16 (tổng 74): Hang Luồn, Hang Đầu Gỗ → Hạ Long; 12 sản phẩm đảo
  Cát Bà Hải Phòng → Cát Bà; Chùa Cầu, Chợ đêm Hội An Đà Nẵng → Hội An.
- `src/data_collection/collectors/excluded_products.csv` — sửa: +12 (tổng 66): Đảo chè Thanh Chương (toạ độ sai); 7 điểm tên chỉ là tên
  điểm đến; tour Booking "Hue City"; Núi Bà Nà, Cáp treo Bà Nà (trùng vé Sun World Bà Nà Hills); Hoàng Thành Huế (trùng Kinh thành Huế).
- `src/data_collection/tests/test_quality.py` — sửa: 2 test (hang vịnh Hạ Long; quyết định 13/10: Cát Bà, Hội An, các dòng ẩn, bản giữ không
  bị ẩn, 16 override của đợt không trỏ vào dòng bị ẩn).
- `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` — sửa: §4 kết quả mục 4, bản xem trước gộp 115 dòng.
- `history/2026-10-13-sua-diem-den-toa-do-va-mo-rong-tuyen-quang.md` — thêm.
- Ngoài repo (thư mục `data/` bị ignore của repo chính, `attractions-fill-20261012/`): `trip_bfs_tq/` (cào), `trip_poi_wave4tq/`,
  `trip_poi_load4tq/` (đợt 41 điểm), `tools/build_wave.py` thêm biến `HOTELS_SEEDS` (bản cũ `build_wave.py.bak-20261013`),
  `tools/drop_reviewed.txt` +6 tên rác (bản cũ `drop_reviewed.bak-20261013`).

## Quyết định

- Tour Booking ở tâm điểm đến (587): giữ. `meetingPoints` là chuỗi địa chỉ, geocode thử ra kết quả mơ hồ; backend lịch trình đã bỏ toạ
  độ tâm khi tính khoảng cách (`src/backend/app/domain/itinerary/geo.py` `located`).
- 84 khách sạn Trip không toạ độ: không cào trang chi tiết vì `vn.trip.com/robots.txt` (đọc 13/10) cấm `/hotels/detail/?hotelId=*` và
  `/hotels/list` cho mọi user-agent — collector `trip_hotels` hiện cào chính hai trang này: đã báo người dùng, chưa sửa job. Khớp tên với
  catalog: 1/84 (Cubicity, đã loại). OSM Nominatim (169 truy vấn tất cả, gồm 7 mẫu; 1 truy vấn/giây, chỉ gửi tên/địa chỉ công khai):
  70/83 không có kết quả, khớp chắc 3 → không thêm nguồn, để trống.
- 3 tour Haven Sunset: không có nguồn toạ độ → để trống. Đảo chè Thanh Chương: OSM, Wikipedia không có → ẩn (người dùng chốt).
- Cát Bà: alias `"hai phong"` khớp địa chỉ "Cát Hải, Hải Phòng" trước `"cat ba"`; 12 search unit trong bán kính 25 km của Cát Bà và gần
  tâm Cát Bà hơn tâm Hải Phòng → Cát Bà (người dùng chốt). Hai hang trong vịnh Hạ Long → Hạ Long (như Ti Tốp `trip:attraction:95477`).
- Hội An: chỉ chuyển 2 điểm cách tâm Hội An < 1 km; 3 điểm trên đường Trường Sa (Đà Nẵng) giữ.
- Tuyên Quang: `crawl_bfs_pois.py` với `ONLY_DESTS=["Tuyên Quang"]`, `EXTRA_SEEDS` = trang danh sách `tuyen-quang-province-1524609`
  (mã đã kiểm 12/10 trong `collectors/plan.py`). Luật tâm gần nhất kéo điểm tỉnh khác (Đền Hùng → Tam Đảo, TP Yên Bái/ATK Định Hóa →
  Tuyên Quang) → chỉ nhận địa chỉ thuộc tỉnh Tuyên Quang; rác/trùng theo tiền lệ production (giữ nhà thờ, quảng trường; bỏ bể bơi,
  hội trường, trụ sở). 0/41 có mô tả thật; người dùng chốt vẫn nạp.

## Kiểm tra

- CSV: `normalise.load_destination_overrides()` 74 dòng, áp đúng (`originalDestination`, `destinationSource`); không trùng ref.
- `test_quality.py`: 34 passed. Lần chạy đầu, test mới bắt 2 ref có override cũ (12/10) nay bị loại (Côn Đảo, Hacoconut) — vô hại vì loại
  chạy sau override; thu hẹp điều kiện về 16 override của đợt này.
- Xem trước production (read-only, `normalise` của worktree): đổi tên 35, ẩn 38 (11 hạng phòng), đổi điểm đến 16 + 26 hạng phòng con →
  115 dòng; 0 thành phần combo và 0 dòng đơn hàng trỏ vào dòng sắp ẩn. `load_attractions.py` đợt `4tq` xem trước: `{'new': 41}`,
  demo_data `changed=0`. Chưa ghi gì.
- Cả suite, bật mọi test DB thật trên DB nháp local (plan §6; DB nháp đã xoá): `python -m pytest -q -p no:cacheprovider
  data_collection/tests` → **709 passed** (0 failed, 0 skipped).

## Còn lại / rủi ro

- Sửa production 115 dòng + nạp 41 điểm Tuyên Quang sau merge + deploy; hỏi người dùng trước khi ghi; rồi "Bảo trì và index".
- robots.txt của Trip với collector `trip_hotels` (người dùng/team quyết).
- Phần data còn lại của bàn giao "chùa ở HCM": tên viết hoa toàn bộ, tên dính chữ, lỗi "Thành phố TP. Hồ Chí Minh" trong mô tả, làm giàu
  mô tả điểm tham quan (cả 41 điểm Tuyên Quang), bổ sung chùa TP.HCM.
