# Điểm tham quan Trip cho nơi còn thiếu (tạm dừng, bàn giao)

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở
- Phạm vi: data

## Mục tiêu

Tiếp `history/2026-10-12-bo-sung-ve-booking-noi-thieu-diem-tham-quan.md` (issue #159). Sau đợt nạp 304 vé Booking vẫn còn
18 điểm đến có khách sạn nhưng 0 vé có giá. Người dùng chỉ cho dùng **dữ liệu thật** (không tạo vé giả). Đợt này thử hai
nguồn Trip cho các nơi đó. Phục vụ FR-CAT-01, FR-AGT; NFR-REL-01 (grounding 100%: agent chỉ gợi ý sản phẩm có trong catalog).

Người dùng yêu cầu **tạm đóng băng** lúc ~13:53 để chuyển sang agent mới. Mục "Còn lại" dưới đây là điểm bắt đầu.

## File thay đổi

- `src/data_collection/collectors/plan.py` — sửa (CHƯA COMMIT): thêm `trip_city` cho Bạc Liêu (`bac-lieu-2044758`), Hà Tiên
  (`ha-tien-24758`), Tam Đảo (`tam-dao-1447662`), Sầm Sơn (`sam-son-1525754`), Vân Đồn (`van-don-district-1542075`), kèm
  comment ghi ngày kiểm và các mã chưa dùng được.
- `history/2026-10-12-diem-tham-quan-trip-cho-noi-thieu.md` — thêm: entry này (CHƯA COMMIT).

Ngoài repo (thư mục bị git ignore, worktree chính `~/code/Travel-Recommendation-Product/src/data_collection/data/attractions-fill-20261012/`):
- `trip_xp/`: lượt thử `crawl.py trip-experiences` (44 bản ghi, không nạp).
- `trip_poi/`: lượt `crawl.py trip-attractions` cho 5 nơi trên, **dừng giữa chừng ở 17/93 trang** (`interim/trip_attractions.jsonl`
  17 dòng, `crawl.log`). Chưa chuẩn hoá, chưa nạp.

## Quyết định

- **Trip experiences (things-to-do) không dùng**: tìm theo từ khoá nên kết quả lạc chỗ (tour Đà Lạt cho Buôn Ma Thuột, Trung
  Quốc cho Lạng Sơn, Lisbon cho Vân Đồn, Mekong từ TP.HCM cho Đồng Tháp, vé xe cho Quy Nhơn); chỉ ~2 bản ghi đúng nơi (Thác
  Dray Nur ở Buôn Ma Thuột, Cửa khẩu Hữu Nghị ở Lạng Sơn). `normalise.py` cũng chưa có bước cho `trip_experiences`. Người
  dùng chọn chuyển sang điểm tham quan Trip.
- **Điểm tham quan Trip** (`trip-attractions`, đã có crawler + normalise): phần lớn không có giá → `is_bookable = false`,
  web hiện "Chưa có giá" + "Sản phẩm này chỉ để tham khảo, không bán vé trên V-OTA." và tắt nút giỏ/đặt
  (`ProductDetailView.tsx` isBookable, `PriceTag.tsx`); agent vẫn đưa vào lịch trình tham khảo. Đúng triệu chứng của #159
  ("không có gợi ý địa điểm đi chơi") cho nơi chưa có gì.
- Mã thành phố Trip tìm qua tìm kiếm web (trip.com) rồi mở `vn.trip.com/travel-guide/attraction/<slug>/tourist-attractions/`
  kiểm tiêu đề. Đường dẫn chỉ phụ thuộc số ID (slug bỏ qua). Robots của Trip cho phép `/travel-guide/attraction/` và
  `/things-to-do/list`.
- Cà Mau 24733, Lạng Sơn 1447671, Sóc Trăng 24740, Sơn La 24744, Bảo Lộc 121753 có trang ở www.trip.com nhưng vn.trip.com trả
  301 → /404; crawler dùng `BASE = https://vn.trip.com` nên chưa dùng được (không đổi BASE vì sẽ ra tên/mô tả tiếng Anh).

## Kiểm tra

- `crawl.py trip-experiences` (17 điểm đến, budget 40): 44 bản ghi, phân loại tay như trên.
- Kiểm mã Trip: Bạc Liêu, Hà Tiên, Tam Đảo, Sầm Sơn, Vân Đồn → tiêu đề đúng tên (Vân Đồn 18 link POI); 5 mã còn lại → 404.
- `crawl.py trip-attractions` 5 nơi: discovery Bạc Liêu 19, Tam Đảo 18, Sầm Sơn 18, Hà Tiên 21, Vân Đồn 18 điểm; dừng ở 10/93
  trang chi tiết (log), 17 dòng interim.
- Chưa chạy test sau khi sửa `plan.py` (chỉ đổi dữ liệu kế hoạch). Lần chạy gần nhất `pytest data_collection/tests`: 649
  passed, 27 skipped (trước khi sửa plan.py).

## Còn lại / rủi ro

1. **Cào tiếp** (resumable, chỉ cào trang còn thiếu):
   `cd ~/code/Travel-Recommendation-Product-newcrawl/src/data_collection && xvfb-run -a ~/miniconda3/envs/vsf2/bin/python crawl.py --data-dir ~/code/Travel-Recommendation-Product/src/data_collection/data/attractions-fill-20261012/trip_poi trip-attractions --destinations "Bạc Liêu,Hà Tiên,Tam Đảo,Sầm Sơn,Vân Đồn" --budget trip_attractions=25`
2. **Chuẩn hoá** `normalise.py --data-dir <trip_poi> --no-plan` **không** kèm `--keep-location-warnings` để bỏ điểm nằm xa điểm
   đến (danh sách Trip lẫn điểm nơi khác; trang Tam Đảo được báo lẫn nhiều điểm Hà Nội). Kiểm điểm đến/toạ độ từng dòng.
3. **Nạp**: dùng mẫu `attractions-fill-20261012/load_attractions.py` (đọc `load_ids.json` + `products.jsonl` cạnh nó; sửa
   đường dẫn cho `trip_poi`). Mặc định xem trước; `--apply` ghi qua `fresh_catalog_db.load_into_db` (chỉ upsert; cùng
   transaction chạy `simulated_business` + `demo_data`). **Hỏi người dùng trước mỗi lần ghi production.** Tunnel do người
   dùng tự mở (`127.0.0.1:15432`, DSN `CLOUD_SEED_DATABASE_URL` trong `src/data_collection/.env`). Sau khi ghi: bấm index trên
   monitor `POST https://monitor.praxis.io.vn/api/run {"mode":"index"}` với header `X-Requested-With: vota-monitor` (hỏi trước;
   không bấm khi đang deploy crawler — CD `docker rm -f` monitor sẽ giết lượt đang chạy).
4. **Commit**: `plan.py` + entry này chưa commit. Người dùng tự mở PR `test/newcrawl` → `release-mvp-v2` (đã có commit
   `845baf13` sửa gán điểm đến tour Booking, push `b0f4fae4`, chưa PR).
5. **Vẫn chưa có nguồn**: Cà Mau, Lạng Sơn, Sóc Trăng, Sơn La, Bảo Lộc (Trip chỉ có bản tiếng Anh), Tuyên Quang (không có trong
   `plan.py`; Trip ID 24760), và các nơi chỉ có điểm Trip không giá: Quy Nhơn, Pleiku, Kon Tum, Buôn Ma Thuột, Tuy Hòa,
   Rạch Giá, Đồng Tháp. Hướng khác (người dùng chưa chọn): nguồn OTA mới (Klook, Traveloka, GetYourGuide) — phải kiểm
   robots/điều khoản trước.
6. Job cào hằng ngày chưa lấy vé Booking (`booking-attractions`) nên giá 304 vé đã nạp sẽ không được làm mới; người dùng để
   phần "chỉnh job cào" sau. Muốn job tự lấy điểm tham quan Trip cho 5 nơi mới cần đưa chúng vào `scope.destinations`
   (đang `@deep`) hoặc tách phạm vi riêng cho Trip attractions.
7. Issue #159 chưa đóng; bản nháp comment cập nhật đã đưa người dùng trong phiên (chưa đăng).
