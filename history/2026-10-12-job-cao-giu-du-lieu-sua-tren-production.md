# Job cào không ghi đè dữ liệu đã sửa trên production 12/10 (khách sạn bật lại, điểm đã ẩn, ảnh vé máy bay)

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`); người dùng tự mở PR vào `release-mvp-v2`
- Trạng thái: hoàn thành phần code + test; chưa deploy (có hiệu lực sau khi merge vào `release-mvp-v2` và Crawler CD chạy)
- Phạm vi: data
- Liên quan: `history/2026-10-12-nap-diem-tham-quan-moi-thanh-pho-va-sua-du-lieu-production.md`

## Mục tiêu

Người dùng: "sửa job cào để nó không sửa lại data đã làm hôm nay". Dữ liệu sửa tay trên production 12/10 mà job hằng ngày sẽ
ghi đè: (1) 87 khách sạn bật lại vì có hạng phòng đang bán — lượt cào sau nguồn không trả giá cho đúng ngày hỏi thì
`prepare_rows` tắt lại và xoá giá, `_hide_hotels_without_rooms` chỉ bật dòng có dấu `noBookableRoom`; (2) 22 điểm Trip không
phải điểm tham quan đã ẩn — cào trúng lại thì upsert lấy `available` của nguồn; (3) ảnh vé máy bay — `seed/simulated_fill.py`
chép ảnh tuyến cho vé `demo:fill:` và ảnh tuyến gốc cho tuyến chiều ngược, `seed/combo_components.py` đặt ảnh combo (trống) cho
tuyến mô phỏng mỗi lần nạp/bảo trì; vé Trip mới không có ảnh. Điểm đến đã sửa không cần sửa job: upsert không ghi đè
`destination`. FR-CAT-02, FR-CAT-03, NFR-REL-01.

## File thay đổi

- `src/data_collection/fresh_catalog_db.py` — sửa: `_hide_hotels_without_rooms` bật lại mọi khách sạn tổng quan có hạng phòng
  đặt được (không chỉ dòng có `noBookableRoom`), trừ dòng đã gộp/giá quá hạn/ngoài cửa sổ; khách sạn bật lại thiếu giá lấy giá
  hạng phòng rẻ nhất đang bán. `apply_window` so cả `unit_price` (hàm `_price`) khi tìm dòng đổi.
- `src/data_collection/collectors/airlines.py` — thêm: tên hãng → logo CDN Trip (`airline_logo`); 5 hãng đã kiểm URL trả ảnh.
- `src/data_collection/normalise.py` — sửa: `apply_airline_logos` gán logo cho vé (`level: flight`) chưa có ảnh; tuyến để trống.
- `src/data_collection/seed/simulated_fill.py` — sửa: vé phủ ngày dùng logo hãng của vé; tuyến chiều ngược giữ `image_url` đã có
  trên DB (dòng mới mới lấy ảnh tuyến gốc).
- `src/data_collection/seed/combo_components.py` — sửa: tuyến bay mô phỏng của combo giữ ảnh đã có trên DB.
- `src/data_collection/collectors/excluded_products.csv` — sửa: thêm 22 điểm đã ẩn (rạp phim, karaoke, massage, sân vận động,
  hội nghị, khách sạn…), mỗi dòng có lý do + bằng chứng.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: test cũ "khách sạn tắt không dấu không bật lại" đổi theo luật mới;
  thêm test giá rẻ nhất, dòng gộp/giá quá hạn vẫn ẩn.
- `src/data_collection/tests/test_simulated_fill.py` — sửa: thêm test logo vé phủ ngày, tuyến chiều ngược giữ ảnh.
- `src/data_collection/tests/test_quality.py` — sửa: thêm test logo vé trong chuẩn hoá, danh sách loại có 22 điểm.
- `src/data_collection/tests/fixtures/normalise_sample/expected_products.jsonl` — sửa: sinh lại bằng `normalise.py` (tham số của
  test, `--today 2026-09-28`); 94/94 dòng, chỉ khác `imageUrl` của 51 vé máy bay (null → logo hãng).
- `src/data_collection/README.md`, `docs/spec/data-collection/schema.md` — sửa: luật bật lại khách sạn, ảnh vé máy bay, danh sách loại.
- `history/2026-10-12-job-cao-giu-du-lieu-sua-tren-production.md` — thêm: entry này.

(Cùng nhánh, commit riêng theo entry khác: `collectors/plan.py`, `collectors/destination_overrides.csv` +44 dòng, 3 entry
lịch sử 12/10 về điểm tham quan.)

## Quyết định

- Không lệch PRD: FR-CAT-02 ghi khách sạn "tự bật lại khi có hạng phòng đặt được (đang bán và có giá)"; code cũ chỉ bật dòng có
  dấu nên câu "dòng tắt vì lý do khác không bị bật lại" ở README/docstring được sửa cùng code. PRD không quy định ảnh vé máy bay;
  spec "Vé máy bay không có ảnh" đổi theo quyết định người dùng 12/10 (logo hãng cho vé, ảnh thành phố đến cho tuyến, như OTA khác).
- Dùng cơ chế có sẵn `collectors/excluded_products.csv` (đã soát tay, có bằng chứng) thay vì thêm luật tự động mới; mở rộng
  `NON_TOURISM_RULES` (rạp phim, karaoke, sân vận động…) để sau, khi người dùng muốn.
- Ảnh tuyến bay (ảnh thành phố đến) do DB giữ, job không tính: chọn ảnh cần dữ liệu điểm tham quan trên DB; tuyến mới hiếm, đặt
  bằng `data/flight-logos-20261012/set_flight_images.py` (ngoài repo).

## Kiểm tra

- `pytest data_collection/tests` (vsf2, từ `src/`): 654 passed, 27 skipped (trước thay đổi 649 + 5 test mới); lần đầu 6 FAIL ở
  golden `expected_products.jsonl` (đúng chỗ đổi `imageUrl`), đã sinh lại và đối chiếu chỉ khác `imageUrl` vé máy bay.
- `python -m compileall -q src/data_collection`: OK. Không đổi backend/contract nên không chạy lại backend tests/validate_contract.
- `curl` 5 logo `pic.tripcdn.com/airline_logo/3x/{vj,vn,9g,vu,qh}.png`: 200 image/png.

## Còn lại / rủi ro

1. Chưa có hiệu lực tới khi merge + Crawler CD. CD staging-ha bị chặn 23:45–08:40 giờ VN, nên lượt cào 08:35 ngày 13/10 vẫn chạy
   code cũ: sau lượt đó chạy lại (idempotent, ngoài repo) `data/vm-repair-20261012/reopen_hotels_with_rooms.py --apply`,
   `data/vm-repair-20261012/hide_junk_attractions.py --apply` (khi có dòng bị bật lại), `data/flight-logos-20261012/set_flight_images.py --apply`.
2. Override điểm đến sinh từ toạ độ của các đợt (`data/attractions-fill-20261012/trip_poi_wave*/overrides_wave*.csv`) chưa đưa vào
   `collectors/destination_overrides.csv`: không cần cho dòng đã có (upsert không ghi đè `destination`), cần khi dựng lại catalog từ đầu.
3. Trần `tripAttractions.perDestination` 25, bộ lọc tên rác tự động, cào trang Moments trong job: chưa làm (người dùng để sau).
