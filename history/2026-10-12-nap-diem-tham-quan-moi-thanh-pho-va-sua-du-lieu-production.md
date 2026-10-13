# Nạp điểm tham quan cho mọi thành phố và sửa dữ liệu production (đợt 2, 3a, 3b; ảnh vé bay; điểm đến sai tỉnh)

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`); không đổi file nào trong repo, mọi script ở
  thư mục bị git ignore `~/code/Travel-Recommendation-Product/src/data_collection/data/`
- Trạng thái: dang dở (bộ cào vẫn chạy ở máy, phần cào sau đợt 3g chưa nạp; sửa job: xem `history/2026-10-12-job-cao-giu-du-lieu-sua-tren-production.md`, chưa deploy)
- Phạm vi: data
- Tiếp: `history/2026-10-12-cao-tiep-diem-tham-quan-trip-noi-trong.md` (phần BÀN GIAO)

## Mục tiêu

Người dùng (theo thứ tự): xem đầu việc dang dở → nạp đợt 2 Côn Đảo/Bảo Lộc ("ưu tiên đưa vào DB production trước để team agent
có đủ data, job cào sửa sau", "nhớ test đầy đủ", "nhớ normalize và kiểm tra DB") → sửa tour Cần Thơ bị gán Côn Đảo → logo hãng
cho vé máy bay, rồi đổi ảnh tuyến sang ảnh thành phố đến (như OTA khác) → sản phẩm "luôn available, có giá mới thì cập nhật" →
bổ sung điểm tham quan cho **mọi** thành phố, bỏ trần → sửa điểm đến sai tỉnh → báo lỗi agent "đi chùa" lên GitHub. FR-CAT-01/02,
FR-AGT-03/04, NFR-REL-01 (grounding: chỉ dữ liệu thật).

## Đã ghi production (mỗi lần ghi đều xem trước + hỏi người dùng)

| Việc | Số dòng | Script (thư mục data/ bị ignore) |
|---|---|---|
| Đợt 2 Côn Đảo 6 + Bảo Lộc 30 (bỏ "Cổng Trời Chùa Linh Quy Pháp Ấn" trùng chùa, 19 m) | 36 mới | `attractions-fill-20261012/trip_poi_load2/` |
| Tour Booking gán theo nơi khởi hành → nơi đến (Cái Răng → Cần Thơ ×6, Nha Trang→Đà Lạt ×5, Huế→Quảng Trị ×2) | 13 | `attractions-fill-20261012/fix_tour_destinations.py` |
| Logo hãng (CDN Trip) cho vé; ảnh thành phố đến (điểm tham quan nhiều đánh giá nhất) cho tuyến | 11.005 vé, 140 tuyến | `flight-logos-20261012/set_flight_images.py` (thay `set_airline_logos.py`) |
| Bật lại khách sạn có phòng đặt được mà bị tắt (FR-CAT-02); giá = phòng rẻ nhất; khoá `reopenedFromRooms` | 87 | `vm-repair-20261012/reopen_hotels_with_rooms.py` |
| Pleiku → Quy Nhơn (Bình Định gộp Gia Lai) | 6 | `vm-repair-20261012/fix_pleiku_to_quynhon.py` |
| Gán tỉnh sau sáp nhập: Tuy Hòa←BMT 9, Mỹ Tho←Đồng Tháp 9, Bến Tre/Mỹ Tho←Vĩnh Long 5, Kon Tum←Quảng Ngãi 2, Chùa Cam Lộ HCM→Quảng Trị | 26 | `vm-repair-20261012/fix_merged_province_destinations.py` |
| 5 điểm ngoài bán kính (Hải Vân→Đà Nẵng, Mr. Biker Bentre Hội An→Bến Tre…) + ẩn gym, sân vận động | 5 + 2 ẩn | `vm-repair-20261012/fix_more_destinations_and_hide.py` |
| Đợt 3a: điểm Trip mới (BFS điểm lân cận) | 138 mới | `attractions-fill-20261012/trip_poi_load3a/` |
| Đợt 3b: BFS + trang Trip Moments | 259 mới | `attractions-fill-20261012/trip_poi_load3b/` |
| Ẩn 20 điểm Trip không phải điểm tham quan (rạp phim, karaoke, massage, sân vận động, hội nghị…) | 20 ẩn | `vm-repair-20261012/hide_junk_attractions.py` |
| Đợt 3c (Moments + BFS, tối 12/10) | 195 mới | `attractions-fill-20261012/trip_poi_load3c/` |
| Đợt 3d | 114 mới | `attractions-fill-20261012/trip_poi_load3d/` |
| Đợt 3e | 181 mới | `attractions-fill-20261012/trip_poi_load3e/` |
| Đợt 3f | 55 mới | `attractions-fill-20261012/trip_poi_load3f/` |
| Đợt 3g (cuối ngày, link lân cận + Moments gần bão hoà) | 106 mới | `attractions-fill-20261012/trip_poi_load3g/` |

Điểm tham quan đang bán: 1.411 (16:50) → 1.784 (18:10) → 2.274 (22:15) → 2.435 (22:34). Index: đợt 2 `embedded 36`; tour `13`; đợt 3a + 37 dòng đổi điểm đến `175`
(`searchUnits` 4.825); đợt 3b `259` (`searchUnits` 5.084); 3c `195` (5.279); 3d `114` (5.393); 3e `181` (5.574); 3f `55` (5.629); 3g `106` (5.735). Không có vector mồ côi. Cuối ngày: 11.005/11.005 vé có logo hãng, 140/140 tuyến có ảnh thành phố, 87/87 khách sạn bật lại vẫn bán.

## Cách lấy dữ liệu (bộ cào lan, ngoài repo)

- `attractions-fill-20261012/tools/crawl_bfs_pois.py`: thay `TripAttractions.discover` của `crawl.py`. Hạt giống = trang chi tiết
  588 điểm Trip đã có trên production (`trip_bfs/seeds.json`) + `EXTRA_SEEDS` (điểm/ trang danh sách/ trang Moments). Mỗi trang tải
  một lần (HTML đầy đủ), ghi bản ghi như `TripCrawler.run`, đi tiếp link "điểm lân cận" khi toạ độ nằm trong bán kính một điểm đến
  có khách sạn; xoay vòng điểm đến; **điểm mới trước, hạt giống sau**; hàng đợi lưu `trip_bfs/bfs_frontier.json` (chạy lại là đi
  tiếp). Nhịp 2,5 s/request của crawler, tôn trọng robots, dừng khi bị chặn. Chỉ `vn.trip.com`; không lách whaleguard.
- Trang Trip Moments (robots chỉ cấm `/moments/tag-*`, `*-hotel(s)-`): `destination-<slug>-<id>/`, `theme/destination-…-attractions-993137/`,
  `type-destination-…-attraction-3/` → link `/moments/poi-<slug>-<id>/` → trang chi tiết. 161 trang / 53 điểm đến thêm 849 link
  (`trip_bfs/extra_seeds_moments.json`; mã Moments cho nơi ngoài plan.py tìm bằng tìm kiếm web).
- `tools/build_wave.py <đợt>`: chụp interim → `normalise.py --no-plan` → override điểm đến theo toạ độ (bằng chứng) cho dòng bị loại
  vì vị trí → chuẩn hoá lại qua `tools/normalise_with_overrides.py` (không sửa `collectors/destination_overrides.csv`) → lọc mã mới
  (đọc production), tên rác (regex), trùng tên → gán điểm đến có tâm gần nhất khi gần hơn rõ (< 80% khoảng cách cũ) → `validate_catalog`
  → `trip_poi_load<đợt>/`. Danh sách bỏ sau duyệt tay: `tools/drop_reviewed.txt`. Override sinh ra: `trip_poi_wave<đợt>/overrides_wave*.csv`
  (để sau đưa vào job).

## Quyết định

- Bật lại 87 khách sạn là đúng FR-CAT-02 (khách sạn có hạng phòng đang bán, có giá). 211 khách sạn không có giá nào giữ ẩn
  (người dùng chọn); thử cào bù giá Agoda 5 khách sạn × 3 ngày: 4/4 `rooms: []` → dừng (người dùng đồng ý).
- Ảnh tuyến bay = ảnh thành phố đến, logo hãng chỉ ở từng vé (người dùng chốt, như OTA khác). Vì `seed/simulated_fill.py` chép
  ảnh tuyến cho vé `demo:fill:` và tuyến chiều ngược mỗi lần nạp/bảo trì, phải chạy lại `set_flight_images.py --apply` sau mỗi lần
  nạp hoặc bấm "Bảo trì và index" cho tới khi sửa job.
- Điểm đến của điểm tham quan theo toạ độ thật (bán kính `geo.destination_radius_km`), không theo địa chỉ tỉnh mới sau sáp nhập
  2025; upsert của job không ghi đè `destination` nên các sửa giữ được.
- Đợt 3a/3b bỏ: tên rác, trùng production, trùng nơi < 150 m (Sapa Heaven Gate = Cổng Trời Ô Quy Hồ, Tata Show đã có vé…).

## Kiểm tra

- Trên worktree (code repo không đổi trong phiên): `pytest data_collection/tests` 649 passed, 27 skipped; `pytest src/backend/tests`
  2814 passed, 36 skipped; `validate_contract.py` PASS; `compileall` OK.
- Đợt 2: chuẩn hoá lại khớp 37/37 (0 trường lệch); `validate_catalog` OK; `db/verify.sql` chỉ đọc trên production: 4 FAIL đã biết
  (profiles/events vượt ngưỡng seed, 1 vé Thương gia mô phỏng dời ngày), còn lại PASS.
- Mỗi đợt: xem trước `load_attractions.py` ra đúng `{'new': N}` trước `--apply`; sau nạp `db_report` toàn `new`.
- Search production (`/api/v1/search`) ra điểm mới: Thác Đamb'ri, Bảo tàng Côn Đảo, Mù Cang Chải, tháp Chàm Phan Rang, Cố đô Hoa
  Lư, Chùa Một Cột, Tháp Trầm Hương, An Bàng (Hội An); 5/5 khách sạn bật lại đứng hạng 1 khi tìm đúng tên (17:31).
- Rà toàn bộ 819 điểm tham quan có toạ độ thật: chỉ KDL Hầm Hô (41 km, bán kính Quy Nhơn 40) ngoài bán kính.
- Sai sót của agent trong phiên: lần chạy lại xem trước của `reopen_hotels_with_rooms.py` ghi đè bản sao lưu bằng file rỗng; đã dựng
  lại `backup-before-reopen-2026-10-12-reconstructed.jsonl` từ DB (mất `priceObservedAt` gốc cấp khách sạn của 87 dòng); script đã
  sửa (sao lưu chỉ khi `--apply`, tên theo giờ, không ghi đè).

## Còn lại / rủi ro

1. Bộ cào vẫn chạy (`trip_bfs/bfs.log`): ~1.600 link mới từ Moments; nạp tiếp theo đợt bằng `build_wave.py 3c --drop-file
   tools/drop_reviewed.txt`, duyệt tay, xem trước, hỏi người dùng, `--apply`, `set_flight_images.py --apply`, người dùng bấm index.
2. Job cào (để sau): đưa override `trip_poi_wave*/overrides_wave*.csv` vào `collectors/destination_overrides.csv`; bộ lọc tên rác vào
   normalise; `simulated_fill` dùng logo hãng cho vé và ảnh thành phố cho tuyến (kể cả tuyến chiều ngược); khách sạn tắt vì một ngày
   không giá nhưng còn phòng có giá thì bật lại (dấu riêng, như `noBookableRoom`); trần `tripAttractions.perDestination` 25.
3. Agent: GitHub [#177](https://github.com/Zeno2k3/Travel-Recommendation-Product/issues/177) — "đi chùa" bị coi là tên một nơi
   (`conversation.py` `conversational_update`, `explore_place`) → báo "chưa tìm thấy" dù có 67 chùa. Liên quan #168, #163, #160.
   GitHub [#183](https://github.com/Zeno2k3/Travel-Recommendation-Product/issues/183) — bỏ qua "miễn phí, rẻ nhất": thêm tour có phí,
   đổi khách sạn đắt hơn dù Vũng Tàu có 19 điểm miễn phí; liên quan đề xuất chờ chốt `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md`.
4. Production bị 503 hai lần trong phiên do CD staging-ha (Backend CD lỗi IAM `vota-ha-patroni`, firewall `vota-ha-pg-clients`;
   sau đó "unconditional drop overload" khi chuỗi CD 17:01–17:21) — hạ tầng của Khoa, đã tự lên lại.
5. Vẫn mỏng: thành phố lớn (link lân cận của Trip lặp lại; Moments đang bổ sung), Hà Tĩnh (chưa có mã Moments), 211 khách sạn
   không giá (ẩn), "Vinpearl Onsen Resort Tuyên Quang" điểm đến lỗi.
