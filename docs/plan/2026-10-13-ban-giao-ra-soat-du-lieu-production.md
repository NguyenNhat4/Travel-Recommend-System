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
  → **ẩn 17 dòng**; đổi tên 2 dòng → tổng 19 dòng. Không dòng nào mang `windowClosed`; tuyến `cah-han` 0 chuyến. Bản giữ
  (`VW00613`, `booking:hotel:16986224`) đang bán bình thường.
- Đổi tên trên production: ghi cả `attributes.originalName`, `nameSource`, `nameEvidence` như `apply_name_overrides`.

Việc còn lại của mục 1:
1. Nếu commit chưa lên remote: `git -C ~/code/Travel-Recommendation-Product-newcrawl log origin/test/newcrawl..HEAD` rồi push
   (không thêm Co-Authored-By / "Generated with Claude Code").
2. Viết script sửa production `src/data_collection/data/vm-repair-20261013/fix_names_and_hide.py` (thư mục `data/` bị ignore, ở repo
   chính `~/code/Travel-Recommendation-Product`): mặc định **chỉ đọc** (transaction read-only) in đúng các dòng sẽ đổi; `--apply` chỉ chạy
   khi người dùng đồng ý **trong chat**.
   - Đổi tên 2 dòng: `name` + đầu `description` nếu bắt đầu bằng tên cũ + ".".
   - Ẩn (`available = false`) 7 ref (6 ref trên + `trip:attraction:141833025`) + hạng phòng con của chúng (đếm lúc rà: Cubicity Trip 2 phòng, Gia An 2, Mango House 6 —
     kiểm lại bằng `catalog.product_meta.parent_product_id`).
   - Trước khi ghi: đọc `fresh_catalog_db.py` để chắc dòng **vắng khỏi catalog** không bị lượt sau bật lại (quy tắc FR-CAT-02 chỉ bật
     khách sạn còn phòng đặt được — phòng đã ẩn + ref đã loại thì không còn).
3. Người dùng bấm "Bảo trì và index" trên monitor → kiểm lại (chạy lại script rà, xem §6).
4. **Hỏi người dùng** các trùng lặp chưa rõ: ~~L'azur 29 tin condotel + TMS ×2~~ (đã chốt giữ hết, 13/10); 2 cặp tour Booking cùng
   tên (giữ cả hai?); Thác Bạc ×2 (khả năng là hai thác khác nhau → giữ).

## 3. Mục 2 — chưa làm

Lập danh sách 121 điểm tham quan Trip có tên không chứa chữ tiếng Việt (search unit đang bán, `source_ref` bắt đầu `trip:attraction:`;
regex chữ có dấu như `audit 4a` ở §6), kèm `attributes.nameEn`, slug, địa chỉ. Đề xuất tên tiếng Việt **chỉ khi chắc chắn** (giữ
thương hiệu: "Sun World…", "VinWonders…"); không chắc thì để trống. Gửi người dùng duyệt → thêm vào `collectors/name_overrides.csv`
(cột `evidence` bắt buộc) → test → sửa production như mục 1 (hỏi trước khi ghi).

## 4. Mục 4 — chưa làm (điều tra rồi báo, chưa ghi gì)

- Toạ độ tâm điểm đến: 586 tour Booking — dữ liệu Booking có `meetingPoints` cho 144/586 (kiểm lại trong interim/raw);
  còn lại cân nhắc giữ precision `destination`.
- Thiếu toạ độ: 84 khách sạn Trip → trang chi tiết khách sạn Trip (qua crawler của repo, tôn trọng robots); 3 combo Vinpearl →
  `venues` / `collectors/location_overrides.csv`.
- Tuyên Quang chỉ 3 điểm: mở rộng BFS trên vn.trip.com theo `docs/plan/2026-10-12-ban-giao-lam-giau-diem-tham-quan.md`.
- Chỉ cào bằng crawler của repo, không vượt chặn (403/429), không dùng dữ liệu do LLM bịa.

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
