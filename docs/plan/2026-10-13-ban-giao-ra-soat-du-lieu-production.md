# Bàn giao: rà soát dữ liệu production và sửa job cào (mục 1, 2, 4)

- Ngày: 2026-10-13 · Người giao: Phạm Nguyễn Đăng Khôi / Claude (agent, hết quota 5 giờ)
- Phục vụ: FR-CAT-02 (catalog/khả dụng), FR-CAT-03 (giá), FR-AGT (trợ lý gợi ý + lên lịch dùng catalog), NFR-REL-01 (chỉ dữ liệu thật)
- Nhánh: `test/newcrawl` (worktree `~/code/Travel-Recommendation-Product-newcrawl`). Người dùng chỉ muốn push lên nhánh này; PR do người dùng tự mở.

## 0. Yêu cầu gốc của người dùng (13/10)

"push lên nhánh test new crawl thôi, sửa job cào để không bị làm hỏng data đã bổ sung, xem lại toàn bộ data được đưa lên production,
có cái nào khó hiểu không? có cái nào hết vé… ảnh hưởng đến agent gợi ý và lên kế hoạch không, hỏi lại tôi nếu cần" → "ok sửa 1, 2, 4
trước" → "nhớ test đầy đủ".

## 1. Kết quả rà soát production (13/10, chỉ đọc)

| Nhóm | Phát hiện | Mục |
|---|---|---|
| Hết hạn / hết chỗ | không có dòng nào đang bán mà đã hết hạn, lịch toàn 0, hay khách sạn/tuyến bay không còn con đặt được | — |
| A | 82 điểm tham quan giống điểm thu phí nhưng không có giá → trợ lý tính 0 đ | **chưa quyết** |
| B | 17 sân golf đang bán không giá → trợ lý tính 0 đ | **chưa quyết** |
| C | 626 search unit dùng toạ độ tâm điểm đến (586 là tour Booking) | 4 |
| D | 87 search unit không có toạ độ (84 khách sạn Trip) | 4 |
| E | trùng lặp: L'azur 29 tin condotel, TMS ×2, Vinpearl VW00469/VW00613, Thác Bạc ×2 (cách ~5 km), 2 cặp tour Booking cùng tên, Cubicity (Trip + Booking) | 1 |
| F | phòng "Phòng Tổng Thống" PANAMA giá 111.111.111 | 1 |
| G | 2 khách sạn đảo Hòn Sơn gắn Rạch Giá (cách 55 km) | 1 |
| H | "Nguyễn Huệ", "Halong Bay Cruises" (thực ra Động Trung Trang); 121 điểm Trip tên chỉ tiếng Anh | 1, 2 |
| I | tuyến Cà Mau–Hà Nội không có chuyến | 1 |
| K | Tuyên Quang chỉ 3 điểm tham quan | 4 |

## 2. Mục 1 — đã xong phần job (code + test), CHƯA sửa production

Đã làm trên `test/newcrawl` (xem `history/2026-10-13-ten-soat-tay-va-loai-khach-san-kem-phong.md`):
- `normalise.py`: `excluded_reason` (loại khách sạn → loại luôn `<ref>:room:*`, lý do "khách sạn cha đã loại: …");
  `name_overrides.csv` + `load_name_overrides` / `apply_name_overrides` (áp cho mọi sản phẩm, cả tour Booking, trước bước loại).
- `collectors/name_overrides.csv`: `trip:attraction:30633439` → "Phố đi bộ Nguyễn Huệ"; `trip:attraction:55838986` → "Động Trung Trang".
- `collectors/excluded_products.csv` (+6, tổng 44): `trip:hotel:118233319:room:482483850` (PANAMA), `trip:route:cah-han`,
  `vinpearl:tour:VW00469` (giữ VW00613), `trip:hotel:135398727` (Cubicity bản Trip, giữ `booking:hotel:16986224`),
  `agoda:hotel:nha-nghi-gia-an:ha-tien-kien-giang`, `agoda:hotel:mango-house:ha-tien-kien-giang`.
- Lượt daily cũng qua `normalise_step` nên danh sách loại áp cho cả daily; `drop_orphans` cũ là lưới an toàn thứ hai.
- Job **không ghi đè `name`/`description`** của dòng không phải chuyến bay đã có trên DB → production phải sửa trực tiếp (bước dưới).

Cập nhật 13/10 chiều (xem `history/2026-10-13-kiem-lai-ra-soat-va-loai-tms-lee-xinh.md`):
- Người dùng chốt: L'azur Cửa Lò (29 tin) và căn hộ TMS Quy Nhơn **giữ hết** (căn hộ khác chủ cùng toà, ID và giá khác nhau);
  **loại** `trip:attraction:141833025` "TMS Quy Nhơn - Lee Xinh" (bản ghi Trip trộn: nameEn "Dieu Tri Market", giờ chợ, nhưng địa chỉ
  và toạ độ là toà TMS; không giá) → `excluded_products.csv` tổng 45 dòng.
- Người dùng chốt: **chỉ sửa production sau khi `test/newcrawl` được merge vào `release-mvp-v2` và CD crawler đã deploy**. VM chạy code
  cũ (daily 13/10 08:45 trên #188) không có 7 ref này trong danh sách loại → ẩn trước deploy có thể bị lượt daily bật lại.
- Bản xem trước (đọc production 13/10, read-only): 7 ref đang bán + 10 phòng con đang bán (Mango House 6, Gia An 2, Cubicity Trip 2)
  → **ẩn 17 dòng**; đổi tên 2 dòng → tổng 19 dòng. **Gộp mục 2 (13/10 chiều): ẩn 26 dòng (16 ref + 10 phòng con), đổi tên 35 dòng
  (34 dòng đổi luôn đầu mô tả) → tổng 61 dòng**, dựng bằng chính `normalise.load_name_overrides` / `apply_name_overrides` /
  `excluded_reason` trên dữ liệu production. Không dòng nào mang `windowClosed`; tuyến `cah-han` 0 chuyến. Bản giữ
  (`VW00613`, `booking:hotel:16986224`) đang bán bình thường.
- Đổi tên trên production: ghi cả `attributes.originalName`, `nameSource`, `nameEvidence` như `apply_name_overrides`.

Việc còn lại của mục 1:
1. Nếu commit chưa lên remote: `git -C ~/code/Travel-Recommendation-Product-newcrawl log origin/test/newcrawl..HEAD` rồi push
   (không thêm Co-Authored-By / "Generated with Claude Code").
2. Viết script sửa production `src/data_collection/data/vm-repair-20261013/fix_names_and_hide.py` (thư mục `data/` bị ignore, ở repo
   chính `~/code/Travel-Recommendation-Product`): mặc định **chỉ đọc** (transaction read-only) in đúng các dòng sẽ đổi; `--apply` chỉ chạy
   khi người dùng đồng ý **trong chat**.
   - Script đọc thẳng `collectors/name_overrides.csv` và `excluded_products.csv` qua các hàm của `normalise` (không liệt kê ref trong
     script), nên phủ cả mục 1, 2 và 4 (bản xem trước gộp ở §4: 115 dòng + nạp 41 điểm Tuyên Quang); đọc thêm
     `destination_overrides.csv` (chỉ dòng có "13/10/2026" trong bằng chứng) để đổi `destination` của khách sạn/điểm và hạng phòng con.
   - Đổi tên: `name` + đầu `description` nếu bắt đầu bằng tên cũ + ".".
   - Ẩn (`available = false`) 7 ref (6 ref trên + `trip:attraction:141833025`) + hạng phòng con của chúng (đếm lúc rà: Cubicity Trip 2 phòng, Gia An 2, Mango House 6 —
     kiểm lại bằng `catalog.product_meta.parent_product_id`).
   - Trước khi ghi: đọc `fresh_catalog_db.py` để chắc dòng **vắng khỏi catalog** không bị lượt sau bật lại (quy tắc FR-CAT-02 chỉ bật
     khách sạn còn phòng đặt được — phòng đã ẩn + ref đã loại thì không còn).
3. Người dùng bấm "Bảo trì và index" trên monitor → kiểm lại (chạy lại script rà, xem §6).
4. **Hỏi người dùng** các trùng lặp chưa rõ: ~~L'azur 29 tin condotel + TMS ×2~~ (đã chốt giữ hết, 13/10); 2 cặp tour Booking cùng
   tên (giữ cả hai?); Thác Bạc ×2 (khả năng là hai thác khác nhau → giữ).

## 3. Mục 2 — job xong 13/10 (người dùng đã duyệt), CHƯA sửa production

Xem `history/2026-10-13-ten-tieng-viet-cho-diem-ten-tieng-anh.md`. Rà 127 search unit `trip:attraction:*` đang bán có tên không chứa
chữ tiếng Việt (121 điểm tham quan + 6 sân golf), đối chiếu điểm có tên tiếng Việt trong 400 m. Người dùng duyệt 13/10:
- **33 tên tiếng Việt** → `collectors/name_overrides.csv` (tổng 35 dòng, evidence ghi tên nguồn, URL, địa chỉ).
- **9 bản trùng** bản tiếng Việt ngay cạnh → `collectors/excluded_products.csv` (tổng 54 dòng; lý do trỏ tới bản giữ): Mui Nai Beach,
  Battle of Ap Bac War Memorial, Bao Ninh Beach, Dark Cave, Tien Trang Beach, Tam Thang Square, Tay Ninh Black Virgin Temple,
  Halong Park (Dragon Park), Hacoconut Coconut Basket Boat.
- Giữ nguyên 70 (thương hiệu, du thuyền, sân golf, "Sa Pa"). Để trống 14 (không chắc tên tiếng Việt): Keo Yen Panorama, Hau de
  waterfall, Buffalo Cave, Hang Mua Big Pagoda, Thung Ui, Red Canyon Mui Ne, Red Sand Dunes Beach (địa chỉ Bắc Bình), Commander Cave,
  Mine Action Visitor Center, Trung Vuong Garden, Phu Thom, Chinatown Saigon, Sunset Viewpoint, Sun World Ba Den Mountain (nameEn
  "Rocky Mountain Lake" mâu thuẫn).
- **Chuyển sang mục 4:** `trip:attraction:133828272` "Dao Che Thanh Chuong" — tên đúng "Đảo chè Thanh Chương" nhưng toạ độ nằm ở
  TP Vinh (cạnh Bảo tàng Quân khu IV), lệch ~40 km; người dùng chưa chọn ẩn hay sửa toạ độ. `trip:attraction:152155369` (Hang
  Luồn): mô tả nói đảo Bồ Hòn (vịnh Hạ Long) nhưng điểm đến ghi Hải Phòng.

## 4. Mục 4 — job xong 13/10 (người dùng đã duyệt), CHƯA sửa production

Xem `history/2026-10-13-sua-diem-den-toa-do-va-mo-rong-tuyen-quang.md`. Đọc production read-only, kết quả:
- **Tour Booking ở tâm điểm đến (587):** giữ nguyên. `meetingPoints` chỉ là chuỗi địa chỉ (216/587), geocode không đáng tin ("112 Trần
  Hưng Đạo, TP.HCM" ra hai phường khác nhau); backend lịch trình đã bỏ toạ độ tâm khi tính khoảng cách (`domain/itinerary/geo.py`).
- **84 khách sạn Trip không toạ độ:** Cubicity bản Trip đã loại (mục 1); 83 còn lại để trống. `vn.trip.com/robots.txt` cấm
  `/hotels/detail/?hotelId=*` và `/hotels/list` cho mọi user-agent (đọc 13/10) — **chính hai trang collector `trip_hotels` đang cào
  hằng ngày**: báo người dùng/team, chưa sửa job. OSM Nominatim chỉ khớp chắc 3/83 → không thêm nguồn mới (người dùng có thể đổi ý).
- **3 tour Haven Sunset (Vinpearl, Phú Quốc):** nhà cung cấp "THE HAVEN SUNSET SHOW" không có trong `venues.csv`, không có nguồn → để trống.
- **Đảo chè Thanh Chương** (`trip:attraction:133828272`): toạ độ nguồn ở TP Vinh (~40 km), OSM/Wikipedia không có → **ẩn** (người dùng chốt).
- **Điểm đến** (`collectors/destination_overrides.csv`, +16): Hang Luồn, Hang Đầu Gỗ → Hạ Long (Trip xếp vịnh Hạ Long dưới slug
  haiphong, như Ti Tốp); 12 sản phẩm đảo Cát Bà (6 khách sạn + 26 hạng phòng con, 6 điểm) Hải Phòng → Cát Bà; Chùa Cầu, Chợ đêm Hội An
  Đà Nẵng → Hội An. Hạng phòng nhận điểm đến của khách sạn khi gộp cụm (`normalise.py` `merge_hotel_cluster`).
- **Gộp dữ liệu của bàn giao "chùa ở HCM"** (`docs/plan/2026-10-13-ban-giao-dieu-tra-agent-search-chua-hcm.md` §8, §11.2 — repo chính,
  nhánh `bench_search_recomSys`, chưa commit), người dùng chốt: ẩn 7 điểm tên chỉ là tên điểm đến (Sa Pa, Phú Quốc, Hội An, Ninh bình,
  Mai Châu, Mộc Châu, Côn Đảo) + tour Booking "Hue City"; ẩn "Núi Bà Nà", "Cáp treo Bà Nà" (cùng vé 1.000.000 ₫ với Sun World Bà Nà Hills,
  giữ) và "Hoàng Thành Huế" (giữ Kinh thành Huế có giá). Chưa làm các mục khác của bàn giao đó (tên viết hoa toàn bộ, tên dính chữ, lỗi
  "Thành phố TP. Hồ Chí Minh" trong mô tả, làm giàu mô tả, bổ sung chùa TP.HCM).
- **Tuyên Quang:** cào BFS `/travel-guide/attraction/` (robots cho phép) 227 trang, 0 lần bị chặn, dữ liệu ở
  `~/code/Travel-Recommendation-Product/src/data_collection/data/attractions-fill-20261012/trip_bfs_tq/`. Đợt `4tq`
  (`trip_poi_wave4tq/`, `trip_poi_load4tq/`): 110 dòng → duyệt tay → **41 điểm mới** (Tuyên Quang 40, Hà Giang 1: Cổng Trời Quản Bạ).
  Bỏ 60 điểm ngoài tỉnh (Đền Hùng/Việt Trì bị gán Tam Đảo; TP Yên Bái, Đoan Hùng, ATK Định Hóa bị gán Tuyên Quang theo tâm gần nhất),
  6 rác (thêm vào `tools/drop_reviewed.txt`), 3 trùng (`trip_poi_wave4tq/review_4tq.json`, `drop_4tq.txt`). `tools/build_wave.py` thêm
  biến `HOTELS_SEEDS` (danh sách điểm đến có khách sạn khác; mặc định như cũ) vì `trip_bfs/seeds.json` không có Tuyên Quang.
  **0/41 có mô tả thật** (mô tả tự sinh — đúng loại text mỏng của §8 bàn giao "chùa ở HCM"); người dùng chốt vẫn nạp cùng đợt.
  Xem trước `load_attractions.py` (read-only): `{'new': 41}`, demo_data `changed=0`.

**Đợt sửa production gộp mục 1 + 2 + 4** (xem trước read-only 13/10, `normalise` của worktree trên dữ liệu production): đổi tên 35, ẩn 38
(28 ref + 10 hạng phòng con; PANAMA là hạng phòng), đổi điểm đến 16 + 26 hạng phòng con → **115 dòng**, cộng nạp 41 điểm Tuyên Quang
(`cd <data>/attractions-fill-20261012/trip_poi_load4tq && python load_attractions.py --code-root <worktree>/src [--apply]`). Không thành
phần combo, không dòng đơn hàng nào trỏ vào dòng sắp ẩn. Đổi điểm đến trên production phải sửa cả hạng phòng con (job giữ `destination`
của dòng không phải vé máy bay).

## 5. Việc người dùng chưa quyết

- A/B (điểm thu phí và sân golf không giá bị tính 0 đ): ẩn, gắn cờ, hay để trợ lý ghi "chưa có giá"? — hỏi.
- Thí nghiệm làm sạch text embed (nhánh `exp/lam-sach-text-embed`, worktree `~/code/trp-embed-clean`, **chưa commit**): kết luận nên
  ship phần normalise (giữ `catalog-text-v2`), không ship `text_builder` v3 (lát cắt parent_child .626 → .427). Chờ người dùng.
- Nhánh `fix/crawl-stall-watchdog` (ee7b4201) đã cherry-pick vào `test/newcrawl` → thừa; xoá hay giữ do người dùng quyết.

## 6. Công cụ và ràng buộc

- Production DB: người dùng mở tunnel `127.0.0.1:15432`; DSN ở `CLOUD_SEED_DATABASE_URL` trong
  `~/code/Travel-Recommendation-Product/src/data_collection/.env`. Kiểm tra luôn chạy read-only
  (`options="-c default_transaction_read_only=on"`). **Hỏi trước mỗi lần ghi production**, báo số dòng từ bản xem trước.
- Script rà toàn bộ (đã dùng 13/10): truy vấn `cdp.products JOIN catalog.product_meta`, nhóm 1a–6b như bảng §1; scratchpad của
  session cũ đã mất — viết lại khi cần.
- Monitor: monitor.praxis.io.vn (`/api/runs`, `/api/run?id=`; POST `/api/settings` cần header `X-Requested-With: vota-monitor`).
- Test: từ `src/` chạy `python -m pytest -q -p no:cacheprovider data_collection/tests` với `DBX_TEST_DATABASE_URL` trỏ DB test local
  (container `travel-recommendation-product-postgres-1`); env `vsf2` (py3.11). Kết quả 13/10: 687 passed, 18 skipped (cần các DSN
  test khác: `CATALOG_TEST_DATABASE_URL`, `STREAM_TEST_ADMIN_URL`, `CATALOG_ONLY_TEST_DATABASE_URL`).
  Chạy đủ (13/10 chiều): thêm `CATALOG_TEST_DATABASE_URL` = `CATALOG_ONLY_TEST_DATABASE_URL` = DB mới tạo từ `template0` + `db/vota_schema.sql`;
  `STREAM_TEST_ADMIN_URL` = superuser local (`…/postgres`, test tự tạo/xoá DB); `APPEND_TEST_DATABASE_URL` = DB trống;
  `RELEASE_TEST_DATABASE_URL` = DB trống tên `vota_business_test_*` (tạo mới mỗi lần, test tự chạy DDL);
  `SIMULATED_TEST_DATABASE_URL` = bản sao `vota_simbiz_test_*` của DB có vé `demo:business:*` (vd. `TEMPLATE vota_crawl_vmcheck`).
  Kết quả: **704 passed, 1 failed, 0 skipped**. Lỗi duy nhất `test_stream_feed_db::test_rows_loaded_separately_then_merged_leave_one_visible`
  có từ trước (cũng lỗi ở `70e142e2` và `origin/release-mvp-v2`): test 29/09 dùng khách sạn không có hạng phòng, bị quy tắc FR-CAT-02
  (06/10) tắt. → Đã sửa 13/10: thực ra là bug của `seed/simulated_rooms.plan` (tắt nhầm khách sạn giữ sau khi gộp), xem
  `history/2026-10-13-sua-phong-mo-phong-tat-nham-khach-san-giu.md`; cả suite **706 passed, 0 failed, 0 skipped**.
- Hạ tầng (VM, lịch tắt) thuộc Khoa: chỉ đọc. Không `pkill -f`. Mọi thay đổi `src/`/`docs/`/`db/` cần entry `history/` mới.
