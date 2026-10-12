# Cào tiếp điểm tham quan Trip cho các nơi còn trống (đã nạp đợt 1, đóng băng trước đợt Côn Đảo/Bảo Lộc)

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở
- Phạm vi: data

## BÀN GIAO (đóng băng 12/10 ~16:06 theo yêu cầu người dùng, chuyển sang session khác)

### Yêu cầu của người dùng trong phiên (theo thứ tự)

1. Xem việc cào điểm tham quan Trip đang dừng ở đâu, làm tiếp để **mọi thành phố có attraction** (issue #159).
2. Xem lại toàn bộ, **test toàn bộ**, kiểm tra DB (production, chỉ đọc).
3. Báo cáo chi tiết lần nạp sẽ bổ sung gì.
4. Hỏi vì sao agent chỉ đưa **1 lựa chọn** khi hỏi trải nghiệm Vũng Tàu: do data hay agent; rồi "lỗi do ai".
5. **Cào thêm điểm tham quan Trip cho Vũng Tàu**; trước đó xem các issue GitHub đã xử lý hết chưa.
6. "Ngoài Vũng Tàu còn chỗ nào tương tự không".
7. **Cập nhật DB production trước, sửa job cào sau** — ưu tiên dữ liệu cho agent. Người dùng tự mở tunnel, chạy script sửa 3
   dòng, bấm "Bảo trì và index" trên monitor.
8. Yêu cầu sửa job embed so cả điểm đến → không cần (xem Kiểm tra: điểm đến lấy từ catalog backend, tự làm mới 15 phút).
9. Thống kê điểm đến còn ít/không có attraction.
10. **Làm Côn Đảo, Bảo Lộc trước**; "tập trung vào agent để nó lên kế hoạch và đề xuất được nhiều địa điểm vui chơi";
    "mở HTML lấy data, normalize chuẩn rồi đưa vào DB"; "job cào sửa sau, ưu tiên bổ sung data"; "bổ sung gấp".
11. Đóng băng, ghi đầy đủ yêu cầu và tiến độ để chuyển session.

Quy ước người dùng nhắc lại: chỉ dữ liệu thật; hỏi trước mỗi lần ghi production (đã cho phép nạp ở mục 7); người dùng tự
commit/mở PR; mock 09/10 giữ bật.

### Tiến độ

- **Đã lên production + index:** 134 dòng (131 mới, 3 sửa điểm đến) cho Bạc Liêu, Lý Sơn, Tam Đảo, Lạng Sơn, Bắc Ninh, Vũng
  Tàu (12), Hà Tiên, Mộc Châu, Sầm Sơn, Vân Đồn, Cà Mau, Tuyên Quang, Sơn La, Sóc Trăng, Mỹ Tho. Search production xác nhận.
- **Đã cào + chuẩn hoá, CHƯA NẠP:** `~/code/Travel-Recommendation-Product/src/data_collection/data/attractions-fill-20261012/trip_poi_load2/`
  — 37 dòng mới (Bảo Lộc 31, Côn Đảo 6; đều không giá → tham khảo), `validate_catalog` OK, 0 dòng trùng production (đọc
  16:05). Côn Đảo: Côn Đảo, Bảo tàng Côn Đảo, Vườn Quốc gia, Mũi Chim Chim, Công viên + Nhà tưởng niệm Võ Thị Sáu. Bảo Lộc:
  thác Đamb'ri, Tu viện Bát Nhã, Linh Quy Pháp Ấn (+ Cổng Trời), Chùa Trà, Đồi Mây, Đồi chè, Thác Liêng Ài, Dasara, nhà thờ,
  glamping… Bỏ "Mỹ Viện Thảo Nguyên" (tiệm làm đẹp), Vịnh Hạ Long và Nhà thờ Cần Giờ (lọt từ trang Moments).
- Cách lấy ID (vn.trip.com 404 trang danh sách của nhiều nơi sau sáp nhập 2025): wrapper
  `attractions-fill-20261012/tools/crawl_toplist_pois.py` (ngoài repo, bị git ignore; cùng thư mục có `crawl_with_trip_ids.py`
  để thử `trip_city` tạm; chạy từ `<worktree>/src/data_collection` qua `xvfb-run -a ~/miniconda3/envs/vsf2/bin/python <tool>
  "$PWD" --data-dir <dir> trip-attractions --destinations "<nơi>" ...`, biến môi trường `SEEDS`, `TOPLISTS`, `CITY_SLUGS`,
  `MAX_SEED_PAGES`, `MOMENTS_CITY_SLUG`, `TRIP_IDS`) thay `TripAttractions.discover`: đọc **HTML đầy đủ** trang chi tiết hạt giống
  (`get_html`, không qua `slim_html`) lấy link "điểm lân cận" (Bảo Lộc, từ thác Đamb'ri 58306775 → 27 link), và trang Trip
  Moments `vn.trip.com/moments/destination-con-dao-island-24761/` lấy `/moments/poi-<slug>-<id>/` → trang chi tiết (Côn Đảo:
  21 URL, 12 xong, 9 báo 404). Robots cho phép `/travel-guide/attraction/` và `/moments/destination-*`. `www.trip.com`,
  trình duyệt trong app và curl bị chặn (whaleguard) — không lách.

### Bắt đầu từ đây (session sau)

1. Mở tunnel (bastion cần mật khẩu, người dùng tự mở):
   `ssh -N -o ServerAliveInterval=30 -o ServerAliveCountMax=20 -o ExitOnForwardFailure=yes -L 127.0.0.1:15432:10.148.0.34:5432 bastion@34.142.132.251`
2. Nạp đợt 2 (37 dòng; ~15–20 phút vì tải catalog ~100 MB qua mạng chậm; kiểm job cào không chạy lượt nào trước):
   `cd ~/code/Travel-Recommendation-Product/src/data_collection && set -a && . ./.env && set +a && ~/miniconda3/envs/vsf2/bin/python data/attractions-fill-20261012/trip_poi_load2/load_attractions.py --code-root ~/code/Travel-Recommendation-Product-newcrawl/src --database-url-env CLOUD_SEED_DATABASE_URL --apply`
   (bỏ `--apply` để xem trước; kết quả đúng: `new 37`). Quyền tự động của agent từng chặn xem trước/ghi production lúc đầu
   nhưng cho chạy `--apply` khi người dùng yêu cầu rõ.
3. Người dùng bấm **"Bảo trì và index"** trên https://monitor.praxis.io.vn (agent bị chặn gọi POST). Kiểm: `GET
   https://monitor.praxis.io.vn/api/runs` (lượt `index` ok, `embedded` ≈ 37); Search
   `GET https://praxis.io.vn/api/v1/search?q=điểm tham quan nổi tiếng&taxonomy=attraction&destination=Côn Đảo` (catalog
   backend làm mới 15 phút).
4. Commit (người dùng tự làm): `plan.py`, `destination_overrides.csv` (+44 dòng tổng trong phiên), hai entry `history/`
   ngày 12/10; PR `test/newcrawl` → `release-mvp-v2` (có cả commit `845baf13` chưa PR).
5. Việc tiếp theo người dùng đã chọn/được đề xuất: (a) **lỗi agent** (mục Còn lại 8) — người dùng muốn agent đề xuất được
   nhiều điểm vui chơi; (b) các nơi chỉ có tour Booking: Ninh Bình, Phong Nha, Hà Giang, rồi Đà Nẵng, Quy Nhơn (mỏng so với số
   khách sạn); (c) sửa job cào (để sau).

## Mục tiêu

Tiếp `history/2026-10-12-diem-tham-quan-trip-cho-noi-thieu.md` (issue #159): mọi điểm đến có khách sạn phải có điểm tham
quan, để agent gợi ý được nơi đi chơi (grounding 100%, NFR-REL-01; FR-CAT-01, FR-AGT-03/04). Chỉ dùng dữ liệu thật.

Production đọc lúc 13:59 ngày 12/10 (chỉ đọc): 12 điểm đến có khách sạn nhưng 0 điểm tham quan — Cà Mau, Sóc Trăng, Tam
Đảo, Sơn La, Bảo Lộc, Bạc Liêu, Lạng Sơn, Hà Tiên, Tuyên Quang, Vân Đồn, Sầm Sơn, và "Vinpearl Onsen Resort Tuyên Quang"
(lỗi dữ liệu có sẵn). Còn mỏng: Côn Đảo 1 (340 khách sạn), Mộc Châu 1, Lý Sơn 1, Bắc Ninh 2.

## File thay đổi

- `src/data_collection/collectors/plan.py` — sửa: `trip_city` cho Cà Mau (`ca-mau-province-1524647`), Lạng Sơn
  (`lang-son-province-1445821`), Sơn La (`son-la-province-1524635`), Bắc Ninh (`bac-ninh-province-1445852`), Sóc Trăng
  (`soc-trang-2186660`); giữ Bạc Liêu, Tam Đảo của phiên trước; **bỏ** `trip_city` của Sầm Sơn, Hà Tiên, Vân Đồn mà phiên
  trước đã thêm (ba nơi thuộc `@extra`, làm FAIL `test_extra_destinations_are_booking_only_and_never_guess_ids`); mã đã kiểm
  của nhóm `@extra` (Sầm Sơn, Hà Tiên, Vân Đồn, Lý Sơn) và Tuyên Quang ghi trong comment.
- `src/data_collection/collectors/destination_overrides.csv` — sửa: thêm 44 dòng sửa điểm đến có bằng chứng (toạ độ, khoảng
  cách tới tâm, URL): 6 Bạc Liêu, 6 Mộc Châu, 2 Sóc Trăng, 1 Hà Tiên, 1 Mỹ Tho, 12 Vũng Tàu, 6 Côn Đảo, 10 Bảo Lộc.
- `history/2026-10-12-diem-tham-quan-trip-cho-noi-thieu.md` — thêm: entry bàn giao của phiên trước (chưa commit, không sửa).
- `history/2026-10-12-cao-tiep-diem-tham-quan-trip-noi-trong.md` — thêm: entry này.

Ngoài repo (thư mục bị git ignore `~/code/Travel-Recommendation-Product/src/data_collection/data/attractions-fill-20261012/`):
`trip_poi/` (5 nơi, cào tiếp từ 17/93), `trip_poi2/` (Cà Mau, Lạng Sơn, Sơn La, Lý Sơn), `trip_poi3/` (Bắc Ninh, Sóc Trăng,
Tuyên Quang), `trip_poi_all/` (gộp 212 bản ghi, chuẩn hoá một lần), `trip_poi_load/` (`products.jsonl`, `load_ids.json`
122 id, `load_attractions.py` chép từ đợt Booking).

## Quyết định

- Mã thành phố Trip tìm bằng tìm kiếm web rồi kiểm bằng chính crawler (`--discover-only`, xem `<title>` trang danh sách đã
  lưu). curl và trình duyệt trong app đều nhận "whaleguard block" (432) nên không dùng, không tìm cách lách. Crawler chạy qua
  wrapper trong scratchpad thay `trip_city` tạm thời, nên lượt cào không phụ thuộc `plan.py`.
- Mã thành phố Cà Mau 24733, Lạng Sơn 1447671, Sơn La 24744, Bắc Ninh 1447661 bị vn.trip.com báo 404 → dùng mã cấp tỉnh
  (tiêu đề trang khớp tên). Côn Đảo 24761, Mộc Châu 1540494 / 2133290, Tuyên Quang 24760, Sóc Trăng 24740 / 1524648, Bảo
  Lộc 121753: 404.
- Sau sáp nhập tỉnh 2025, địa chỉ Trip ghi tỉnh mới nên chuẩn hoá gán điểm Bạc Liêu → Cà Mau, Mộc Châu → Sơn La, Sóc Trăng →
  Cần Thơ, rồi loại vì xa tâm. Sửa bằng `destination_overrides.csv` (cơ chế có sẵn, có bằng chứng), chỉ cho điểm nằm trong
  bán kính điểm đến đúng; không đổi code chuẩn hoá. Điểm ngoài mọi bán kính (Tà Xùa, Mũi Cà Mau GPS 0001, Đồng Văn…) vẫn bị loại.
- Bộ nạp chỉ gồm dòng mới ở các nơi trống/mỏng (119) và 3 dòng đã có nhưng sai điểm đến trên production (Chùa Dơi, Chùa Sà
  Lôn: Cần Thơ → Sóc Trăng; Chùa Vĩnh Tràng: Đồng Tháp → Mỹ Tho). Bỏ VSIP (khu công nghiệp), sân vận động Lục Nam, và 5 dòng
  "Tuyên Quang" cách TP. Tuyên Quang 128–160 km (Laoshan ở Trung Quốc, cao nguyên Hà Giang); `geo.py` chưa có tâm Tuyên
  Quang nên bước kiểm vị trí không tự loại được. Bỏ 2 dòng trùng: "Mui Nai Beach" (cùng bãi với "Bãi tắm Mũi Nai", cách
  80 m) và "Điểm du lịch điện gió Bạc Liêu" (cùng cánh đồng điện gió, cách 100 m); giữ hai "Thác Bạc" (Tam Đảo, Đại
  Đình: hai địa chỉ khác nhau). 22 dòng mới ở nơi khác (Hạ Long, TP.HCM…) và 34 dòng đã có không nạp.
- Hầu hết không có giá → `is_bookable = false`, web hiện "Chưa có giá"; agent vẫn dùng làm điểm tham khảo trong lịch.

- **Vũng Tàu (bổ sung theo yêu cầu, chiều 12/10):** production có 48 attraction, toàn tour Booking tên tiếng Anh, 0 điểm Trip
  (`trip_city = None`). vn.trip.com báo 404 cho `vung-tau-1389` và `ba-ria-vung-tau-province-3172`; trang Trip.best trả trang
  mặc định (khách sạn Thượng Hải). Sau sáp nhập 2025 Trip xếp điểm ở Vũng Tàu vào thư mục `ho-chi-minh-city`. Lấy 13 ID điểm
  qua tìm kiếm web, cào trang chi tiết (`/travel-guide/attraction/`, robots cho phép) bằng wrapper scratchpad thay
  `TripAttractions.discover`: 11 xong, 2 báo 404 (Lăng Cá Ông 58300329, Mũi Nghinh Phong 55839543). Chuẩn hoá gán cả 11 về TP.
  Hồ Chí Minh theo địa chỉ, nên thêm 11 override về Vũng Tàu (cách tâm 0,3–18 km, cách TP.HCM ~60–72 km). Cùng với Sun World
  Vũng Tàu (đã có override), bộ nạp thêm 12 dòng Vũng Tàu (3 có giá: Sun World, Hồ Mây, Bảo tàng Robert Taylor).
- **Agent chỉ trả 1 thẻ khi hỏi trải nghiệm Vũng Tàu** (người dùng báo): ngoài phạm vi data, chưa sửa. `pick()` trong
  `agents/steps/exploration.py` trả đúng 1 thẻ khi `_asked` tìm được "nơi được hỏi"; `closest_matches(products, place)` khớp
  mọi sản phẩm có ≥ 2 từ và ≥ 60% số từ của `place` trong tên, nên LLM đặt `place` = tên thành phố ("Vũng Tàu", "biển Vũng
  Tàu") là khớp tour đầu tiên. Tái hiện bằng tên thật: `place="Vũng Tàu"` → 1 thẻ "1-Day Tour in Vung Tau Beach". Mô phỏng trên
  tên sản phẩm có ở máy: gần như mọi điểm đến tên ≥ 2 chữ đều có sản phẩm chứa tên thành phố (Nha Trang 42, Phú Quốc 52, Hội An
  27, Hà Giang 28/28, Mai Châu 29/29…). Chưa xác nhận được đầu ra LLM thật (Claude in Chrome không kết nối; gọi thẳng API chat
  bị kiểm tra CSRF chặn).

## Kiểm tra

- `crawl.py trip-attractions` (vsf2, Xvfb): 5 nơi 93/93; 4 nơi 73/73; 3 nơi 61/61; 0 lỗi, 0 bị chặn.
- `normalise.py --no-plan` trên `trip_poi_all`: 212 bản ghi → 184 sản phẩm, 24 dòng loại vì vị trí.
- Bộ nạp 122 dòng: Bạc Liêu 17, Lý Sơn 16, Tam Đảo 15, Lạng Sơn 13, Bắc Ninh 13, Hà Tiên 10, Mộc Châu 10, Sầm Sơn 9, Vân
  Đồn 7, Cà Mau 4, Tuyên Quang 3, Sơn La 2, Sóc Trăng 2, Mỹ Tho 1; 2 dòng có giá; đủ ảnh, toạ độ, tên/mô tả tiếng Việt
  (mô tả phần lớn tự sinh từ loại hình, địa chỉ, giờ mở cửa); không trùng tên với attraction đã có ở cùng điểm đến.
- Mô phỏng đường nạp cục bộ (không ghi), chạy trên bộ 122 dòng: `validate_catalog` OK; `prepare_rows` với các dòng
  production trùng id/ref (đọc): `new 119`, `refreshed 3` (3 dòng sửa điểm đến, vẫn mang điểm đến mới), 0 dòng bị cách ly.
- Production đọc lại sau đó (chỉ đọc): chưa nạp gì; 1.299 attraction như trước. Điểm Trip không giá hiện có trong
  `catalog.product_meta`: `is_bookable = false`, `is_search_unit = true`, `is_recommendable = false` (348 dòng), nên dòng mới
  sẽ vào Search/agent, không vào RecSys.
- `db/verify.sql` chạy từng câu trên production ở chế độ chỉ đọc (máy không có psql): PASS trừ 4 dòng không liên quan đợt
  này — `profiles = 2000` (7.005), `events 6000-8000` (40.248), `max events per user <= 15` (116): production có hoạt động
  thật và lịch sử bổ sung cho RecSys, vượt ngưỡng seed; `future purchases inside window` (1): đơn thật 08/10 vé Thương gia
  mô phỏng `demo:business:trip:flight:HAN-DLI:VJ409` dùng ngày 16/10, nhưng dòng vé đã bị dời sang 20/10.
  `db/verify_insider.sql` chưa chạy (không có DSN database `insider` production).
- Test toàn bộ trên worktree (như CI): `validate_contract.py` PASS; `compileall src/backend src/data_collection` OK;
  `pytest src/backend/tests` 2814 passed, 36 skipped; `pytest data_collection/tests` 649 passed, 27 skipped;
  `ops/tests/test_cluster_probe.py` 7 passed; `test-install-vota-cron.sh`, `test-backend-vm-cd-sync.sh`, `bash -n` OK;
  frontend `npm ci` + `generate:api-types` (không đổi) + lint (0 lỗi, 3 cảnh báo có sẵn) + typecheck OK + `vitest` 820/820 +
  build OK. Chưa chạy `test:e2e` (cần trình duyệt Playwright và stack chạy). `next build` ghi lại `next-env.d.ts`, đã trả về.
- `pytest data_collection/tests/test_plan.py`: trước khi sửa 1 failed (đúng test nhóm `@extra`), sau khi sửa 16 passed.
- `pytest data_collection/tests` (vsf2): 649 passed, 27 skipped.
- Xem trước nạp production do người dùng chạy (bộ 122 dòng, trước khi thêm Vũng Tàu): `xem trước ghép với DB: {'new': 119,
  'refreshed': 3}`; phần xem trước mock 09/10 lỗi `server closed the connection unexpectedly` vì tunnel SSH thoát (keepalive 15 s ×
  3 với mạng nghẽn: tải Cloudflare ~120 KB/s, ping bastion 87–754 ms). Chưa ghi gì.
- Sau khi thêm Vũng Tàu: bộ nạp 134 dòng, `validate_catalog` OK, 5 dòng có giá; 122 dòng cũ không đổi sau khi chuẩn hoá lại
  `trip_poi_all` (223 bản ghi → 195 sản phẩm); `pytest data_collection/tests` 649 passed, 27 skipped. Chưa xem trước lại với
  production (tunnel đóng).
- **Đã nạp production** (người dùng yêu cầu "cập nhật DB production trước", 12/10 ~15:08–15:25, tunnel do người dùng mở; job
  cào không chạy lượt nào lúc đó): `load_attractions.py --apply` exit 0, `new 131, refreshed 3, quarantined 0, dbRowsWritten
  134`; cùng transaction: `combosChanged 15`, `comboItemsChanged 136`, `mockProducts 100`, `mockProductsClosed 4`,
  `productsChanged 13`, `fillOneWay 3704`, `fillRoundTrip 3662`, `reverseRoutes 24`, `simulatedRooms 1` (log
  `trip_poi_load/apply.log`, ngoài repo). Đọc lại: 134/134 dòng có mặt, cửa sổ 12/10–10/11, `is_search_unit` true cả 134,
  `is_bookable` true 5; attraction 1.299 → 1.427, golf 6 → 9.
- **3 dòng sửa điểm đến KHÔNG đổi**: upsert của `fresh_catalog_db.load_into_db` cố ý không ghi đè `destination` (chỉ
  `attributes`, giá, cửa sổ…); mô phỏng `prepare_rows` trước đó không thấy điều này. Chùa Dơi, Chùa Sà Lôn vẫn ở Cần Thơ, Chùa
  Vĩnh Tràng vẫn ở Đồng Tháp; Sóc Trăng vẫn 0 attraction. UPDATE có chốt chặn bị quyền tự động chặn; script cho người dùng chạy:
  `trip_poi_load/fix_destinations.py` (ngoài repo; rollback nếu không khớp đúng 3 dòng). Người dùng đã chạy: `ĐÃ SỬA 3 dòng`;
  đọc lại: Chùa Dơi, Chùa Sà Lôn → Sóc Trăng, Chùa Vĩnh Tràng → Mỹ Tho; Sóc Trăng có 2 attraction.
- Bước `index` trên monitor (POST `/api/run {"mode":"index"}`) bị quyền tự động chặn; người dùng bấm "Bảo trì và index":
  `index-20261012T083309Z-222` ok (15:33–15:34), `searchUnits 4651, unchanged 4517, embedded 134, deletedOrphans 0,
  missingLexical 0`. `GET /search?q=điểm tham quan nổi tiếng&taxonomy=attraction&destination=…` trên praxis.io.vn: Vũng Tàu 20
  (có "Tượng đài Chúa Kitô"), Bạc Liêu 17, Tam Đảo 12, Lạng Sơn 13, Mộc Châu 3; **Sóc Trăng 0**.
- 15:36–15:39 `GET /search?q=Chùa Dơi` còn trả "Chùa Dơi (Cần Thơ)", lọc Sóc Trăng thì 0. Ban đầu chẩn đoán nhầm là job
  embed giữ điểm đến cũ trong Weaviate; thực tế Weaviate không lưu `destination` (object chỉ có `productId`, `modelVersion`,
  `textHash`, property BM25). Điểm đến lấy từ catalog backend giữ trong bộ nhớ (`PostgresCatalogReader`), nạp lại khi mã băm
  toàn dòng catalog (có `destination`) đổi, kiểm mỗi `catalog_refresh_seconds` = 900 s. Không sửa job embed. Lúc 15:46:48
  Search trả đúng: Sóc Trăng 2 (Chùa Dơi, Chùa Sà Lôn), Mỹ Tho 19 (có Chùa Vĩnh Tràng).
- Sau nạp, nơi có khách sạn nhưng < 3 attraction: Bảo Lộc 0, Sóc Trăng 0 (chờ script trên), "Vinpearl Onsen Resort Tuyên
  Quang" 0 (lỗi dữ liệu), Côn Đảo 1, Sơn La 2.

## Còn lại / rủi ro

1. ĐÃ NẠP (xem Kiểm tra). Còn: chạy `trip_poi_load/fix_destinations.py`, rồi bấm `index` trên monitor. Lệnh nạp đã dùng
   (tunnel `127.0.0.1:15432` do người dùng mở):
   `cd ~/code/Travel-Recommendation-Product/src/data_collection && set -a && . ./.env && set +a && ~/miniconda3/envs/vsf2/bin/python data/attractions-fill-20261012/trip_poi_load/load_attractions.py --code-root ~/code/Travel-Recommendation-Product-newcrawl/src --database-url-env CLOUD_SEED_DATABASE_URL`
   (134 dòng; thêm `--apply` để ghi; cùng transaction chạy `simulated_business` + `demo_data` như mọi lượt nạp). Sau đó bấm `index`
   trên monitor (hỏi trước, không bấm khi đang deploy crawler).
2. Côn Đảo, Bảo Lộc: đã cào, chờ nạp đợt 2 (xem BÀN GIAO). Sau đợt 2 vẫn mỏng: Tuyên Quang 3, Sơn La 2, Sóc Trăng 2,
   Cà Mau 4, Quảng Ngãi 3, Phan Rang 3, Biên Hòa 3 (thống kê production 15:50 trong phiên). Cần nguồn khác (vd. Klook, Traveloka, GetYourGuide; kiểm robots/điều khoản trước) hoặc
   `www.trip.com` (tiếng Anh, crawler đang khoá `BASE = vn.trip.com`).
3. `geo.py` chưa có `DESTINATION_CENTERS["Tuyên Quang"]`; "Vinpearl Onsen Resort Tuyên Quang" vẫn là điểm đến lỗi.
   Vé Thương gia mô phỏng có đơn thật vẫn bị dời ngày (xem dòng FAIL `future purchases inside window`), chưa xử lý.
4. Trip trả một số POI không phải điểm chơi (khu công nghiệp, sân vận động, tiệm xăm); job cào hằng ngày chưa lọc loại này.
5. Cùng hồ sơ dữ liệu với Vũng Tàu (chỉ tour Booking, `trip_city = None`, 0 điểm Trip — bảng production 14:00): Ninh Bình
   (16), Phong Nha (18), Tây Ninh (19), Hà Giang (27), Mai Châu (28), Cát Bà (14), Thanh Hóa (15), Mù Cang Chải (8), Phan Rang
   (3), Côn Đảo (1); Bảo Lộc 0. Chưa cào.
6. Issue GitHub (đọc 12/10 ~14:55): #158 có bản sửa trên `origin/feat/agent-end` (7dc86d22, 8a1c4d35), chưa có PR/merge; #160,
   #163 chưa thấy commit nào; #159 là việc của entry này.
7. Commit/PR: chưa commit; người dùng tự mở PR `test/newcrawl` → `release-mvp-v2`. Issue #159 chưa đóng.
8. **Lỗi agent khám phá** (`src/backend/app/agents/steps/exploration.py`, workstream agent — Nguyễn Minh Nhật viết cùng
   Claude Code 10–11/10, commit `34198d91`, `e94a3bb2`, `ab4e3754`), tái hiện bằng chat người dùng dán ("VŨng tàu có gì chơi"
   → "Còn gì khác không" → "Đi chơi thôi, không có khách sạn"):
   a. Chỉ 1 thẻ: LLM đặt `place` = tên thành phố; `_place_candidates` → `rules.closest_matches` khớp sản phẩm có tên chứa tên
      thành phố ("Vung Tau Essential…") → `pick()` trả nhánh `asked` 1 thẻ, lời dẫn "Có, … là một điểm đến…", "Vé vào cửa từ
      1.090.000 ₫" cho giá tour. Mô phỏng trên tên sản phẩm: gần như mọi điểm đến tên ≥ 2 chữ đều dính. Hướng sửa đề xuất:
      bỏ tên thành phố khỏi `place` (`_without_cities` có sẵn) trước khi so; còn < 2 từ thì coi như không hỏi nơi cụ thể.
   b. `focus = sights` ("không có khách sạn") vẫn 2 thẻ khách sạn: `pick()` luôn giữ `MAX_CARDS // 2` cho khách sạn trừ khi
      `hotel_focus`; comment "hỏi riêng một loại thì 4" chỉ đúng cho khách sạn.
   c. Lượt "còn gì khác" lặp đúng các thẻ trước, chỉ 2 chỗ cho điểm tham quan; không loại sản phẩm đã hiện (liên quan #163).
   Người dùng chưa quyết: soạn issue cho Nhật hay tự sửa. Người dùng muốn agent lên kế hoạch và đề xuất được nhiều điểm vui
   chơi.
9. Job cào (để sau theo yêu cầu): job hằng ngày chưa lấy vé Booking (giá 304 vé không được làm mới); điểm Trip của các nơi mới
   chỉ có nhờ lượt cào tay (scope Trip attractions của job là `@deep`); cách lấy ID qua trang chi tiết/Moments chưa có trong
   crawler; chuẩn hoá gán điểm đến theo tỉnh sau sáp nhập (Bạc Liêu→Cà Mau, Mộc Châu→Sơn La, Vũng Tàu/Côn Đảo→TP.HCM, Bảo
   Lộc→Đà Lạt) nên phải dùng override từng dòng — nên gán theo toạ độ gần nhất khi xa tâm điểm đến theo địa chỉ; upsert của
   loader không ghi đè `destination` của dòng đã có.
