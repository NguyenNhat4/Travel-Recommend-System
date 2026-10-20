# Giá sân golf từ golfscape.com, ẩn điểm Trip trùng voucher Vinpearl Golf Hải Phòng

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`); người dùng tự mở PR vào `release-mvp-v2`
- Trạng thái: dang dở — code + test xong, chưa commit; đã ghi production 23:51 (người dùng: "ghi ngay bây giờ"); chưa deploy
- Phạm vi: data
- Liên quan: `docs/plan/2026-10-12-ban-giao-lam-giau-diem-tham-quan.md` §2.2, §3;
  `history/2026-10-12-dot-cuoi-diem-tham-quan-golf-va-sua-tuyen-quang.md`

## Mục tiêu

Người dùng: "vé golf không có giá? tôi muốn bổ sung có giá", "có thể xem các nguồn khác", rồi chốt (12/10 ~23:45) bốn bước:
(1) lấy giá golfscape cho các sân có giá; (2) sân khác kiểm web chính thức, "sân nào không có giá thì thôi"; (3) "giá tham khảo cũng
không"; (4) ẩn "Vinpearl Golf Hải Phòng" của Trip (trùng voucher Vinpearl có giá). Production 23:14: 25 golf đang bán, chỉ 5 voucher
Vinpearl có giá; 20 sân Trip `unit_price = null`. FR-CAT-03 (định giá), NFR-REL-01 (chỉ dữ liệu thật).

## Kết quả tìm nguồn (12/10 23:30–23:45)

| Nguồn | Dùng? | Ghi chú |
|---|---|---|
| golfscape.com (đặt tee time) | có | robots.txt `Disallow:` rỗng; giá ở `priceRange` JSON-LD `GolfCourse`. Có giá: Bà Nà Hills 3.950.000–5.000.000; Legend Đà Nẵng Norman 5.666.667–7.533.334, Nicklaus 5.866.667–7.733.334; Vinpearl Golf Hải Phòng 2.500.000–4.500.000 (dòng Trip này ẩn). Vietnam Golf & Country Club có trang, không có giá |
| banahillsgolf.com (chính thức) | đối chiếu | chỉ giá khuyến mãi; Chủ nhật khách quốc tế 3.950.000 (gồm green fee, caddie, xe chung) = giá thấp nhất golfscape |
| Expedia | không | HTTP 429 (chặn bot); chỉ có gói tour kèm xe đưa đón |
| 1golf.eu, leadingcourses.com | không | HTTP 403 |
| Where2Golf | không | giá 2021–2024 (người dùng: không dùng giá tham khảo) |
| Klook, Pelago | không | gói tour có xe, giá theo nhóm/ngoại tệ, không phải giá sân |
| Waug | không | trang điểm đến Việt Nam không có sản phẩm golf |
| Bảng giá ngân hàng (SHB, PVcombank, ACB, OCB) | không | giá ưu đãi chủ thẻ 2024–2025 |

17 sân còn lại (Amber Hills, Corn Hill, Sam Tuyền Lâm, Sono Felice, FLC Hạ Long, Hanoi Golf Club, KN Golf Links, Hoàng Gia,
Tràng An, NovaWorld Phan Thiết, Sea Links, FLC Sầm Sơn, Đại Lải, Tam Đảo, Thanh Lanh, Vietnam Golf & Country Club, Paradise
Vũng Tàu): không tìm được giá hiện hành từ nguồn cho phép cào → giữ `unit_price = null`.

## File thay đổi

- `src/data_collection/collectors/golf_prices.csv` — thêm: 2 sân (Bà Nà Hills `trip:attraction:58257538` 3.950.000; Legend
  Danang Golf Resort `trip:attraction:15151594` 5.666.667 = giá thấp nhất của hai sân), cột giá, nguồn, URL, thời điểm tải trang,
  bằng chứng.
- `src/data_collection/normalise.py` — sửa: `load_golf_prices`, `apply_golf_prices` (chỉ dòng `golf` chưa có giá; giá nguồn
  thắng; ghi `priceObservedAt`, `fieldSources.unitPrice`), gọi sau bước loại; `stage_report["golfPricesApplied"]`.
- `src/data_collection/collectors/excluded_products.csv` — sửa: thêm `trip:attraction:147484815` Vinpearl Golf Hải Phòng (38 dòng).
- `src/data_collection/tests/test_quality.py` — sửa: 3 test (CSV có nguồn/URL/thời điểm; chỉ điền golf chưa có giá, dòng thiếu
  URL bị bỏ; điểm Trip trùng voucher nằm trong danh sách loại).
- `src/data_collection/README.md`, `docs/spec/data-collection/schema.md` — sửa: một câu về `golf_prices.csv`.
- `docs/plan/2026-10-12-ban-giao-lam-giau-diem-tham-quan.md` — sửa: script 5 ở §2.2, §2.3 năm lệnh, §3 mục 1–2 đã chốt,
  §5 lịch tắt VM bị gắn lại 23:37.
- `history/2026-10-12-gia-san-golf-tu-golfscape.md` — thêm: entry này.
- Ngoài repo (thư mục ignored): `~/code/Travel-Recommendation-Product/src/data_collection/data/golf-prices-20261012/set_golf_prices.py`
  — sửa production tới khi deploy; xem trước bằng transaction chỉ đọc, `--apply` ghi và kiểm trạng thái cuối, lệch thì ROLLBACK.

## Quyết định

- Không lệch PRD: spec đã cho giá lấy từ nguồn khác nguồn của sản phẩm (`fieldSources`, ví dụ `{"unitPrice": "booking.com"}`);
  PRD chỉ cấm giá không thật (NFR-REL-01). Không thêm khoá `attributes` mới (URL + bằng chứng nằm trong CSV); không đặt
  `priceBasis` (931 điểm/golf có giá trên production đều không có khoá này; FR-BKG-08 tính golf theo người).
- Giá = mức thấp nhất trong `priceRange` golfscape (một khách, 18 hố), không làm tròn: số lẻ của Legend (5.666.667) là giá nguồn.
  Golfscape không ghi giá gồm gì; giá Bà Nà trùng giá chính thức đã gồm green fee, caddie, xe chung.
- Luật giá quá hạn của job (`fresh_catalog_db.trip_price_reference`) chỉ áp cho khách sạn Trip, nên giá golfscape không bị tự tắt.
  Backend đọc giá từ Postgres (`infrastructure/vectors/postgres_store.py`), không cần index lại Weaviate.

## Kiểm tra

- `cd src && python -m pytest -q data_collection/tests` (vsf2): 659 passed, 27 skipped (trước 656 + 3 test mới).
- Production chỉ đọc 23:31: khách sạn cần bật lại 0, 20 + 5 điểm rác còn bán 0, Tuyên Quang 8/8; người dùng chạy
  `set_flight_images.py` xem trước: 0 dòng.
- `set_golf_prices.py` xem trước (transaction chỉ đọc) 23:46: đặt giá 2 dòng (Bà Nà Hills 3.950.000, Legend 5.666.667), ẩn 1 dòng
  (Vinpearl Golf Hải Phòng Trip), 0 dòng giữ giá nguồn.
- `set_golf_prices.py --apply` 23:51:22: "2 dòng đặt giá, 1 dòng ẩn … ĐÃ GHI". Đọc lại (chỉ đọc): golf đang bán 24 = 7 có giá
  (5 voucher Vinpearl 1.700.000 + Bà Nà Hills 3.950.000 + Legend 5.666.667, `fieldSources.unitPrice = golfscape.com`) + 17 không giá;
  1 dòng ẩn.

## Còn lại / rủi ro

1. Hai sân có giá được job đọc lại hôm nay (`lastSeenAt` 2026-10-12): job code cũ ghi đè `unit_price` mỗi lượt, nên chạy lại
   `set_golf_prices.py` sau mỗi lượt cào/bảo trì tới khi deploy (plan §2.2 lệnh 5).
2. Chưa commit/push (người dùng commit khi bảo).
3. Giá golfscape thay đổi theo ngày/mùa: chưa có job cào lại; giá giữ thời điểm quan sát 12/10.
4. Issue #185 (golf không giá ≠ miễn phí) chưa bổ sung.
