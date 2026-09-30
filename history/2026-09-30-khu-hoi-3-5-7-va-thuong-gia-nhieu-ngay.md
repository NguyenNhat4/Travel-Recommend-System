# Khứ hồi 3/5/7 ngày và thương gia nhiều ngày (xoay vòng), sửa đề xuất vé mô phỏng lên VM

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu: "tôi muốn vé khứ hồi, thương gia cũng vậy, cào lấy giá nhiều ngày như vé bình thường"; ngày về sau "3, 5 và 7
ngày"; chọn "Xoay vòng có hạn mức". Sau khi thấy Trip chặn: giữ code "vẫn bật như cũ, giữ nguyên"; vé thương gia nhiều ngày cho
demo dùng đề xuất mô phỏng, sửa để "nạp cả lên VM".

Tiếp task đang làm dở ở phiên khác (chưa có file thay đổi nào khi nhận).

## File thay đổi

- `src/data_collection/collectors/trip_roundtrip_search.py` — thêm: tìm khứ hồi trên UI Trip (chuyến đi → chuyến về đề xuất →
  modal giá trọn hành trình); `parse_roundtrip` fail closed: đúng 2 chặng bay thẳng, ngày/tuyến/chuyến về khớp URL, thẻ ghi
  "Khứ hồi", nhãn hạng chính xác, giá rẻ nhất mỗi hạng. `open_search`: HTTP 432 chờ 45 giây rồi thử lại một lần
  (người yêu cầu: "mã 432 thì chờ 45s rồi thử lại"); vẫn 432 hoặc 403/429 thì báo bị chặn.
- `src/data_collection/collectors/trip_business.py` — sửa: `enrich` lên kế hoạch mọi việc (thương gia một chiều theo ngày; khứ
  hồi theo ngày × số ngày ở lại), chưa tìm/ngày gần trước, rồi việc tìm lâu nhất; dừng khi hết hạn mức phút, trước hạn nguồn 3
  phút, hoặc sau 3 lỗi liên tiếp. Trạng thái xoay vòng `<CATALOG_STATE_DIR>/trip_fares_rotation.json`. Tìm rỗng không tính lỗi.
  Mở trang tìm bằng `open_search` (cùng quy tắc 432).
- `src/data_collection/crawl.py` — sửa: cờ `--business-offsets` (mặc định `1-29`, nhận khoảng), `--business-max-flights` 4,
  `--roundtrip-stays` 3,5,7, `--roundtrip-pairs` 2, `--fares-minutes` 30, `--source-deadline-minutes`; exit 2 chỉ khi dừng vì lỗi
  liên tiếp hoặc mọi lần tìm đều lỗi.
- `src/data_collection/fresh_settings.py` — sửa: mục monitor `tripFlights.fareMinutes` (30, 0 = tắt).
- `src/data_collection/fresh_catalog.py` — sửa: truyền `--fares-minutes` và hạn giờ nguồn cho `trip-flights`.
- `src/data_collection/normalise.py` — sửa: gom `roundTripQuotes` qua bản ghi; `trip_roundtrip_search_products` dùng cùng
  `sourceRef` với thẻ khứ hồi SEO, vé tìm kiếm thắng thẻ SEO cùng mã; `MAPPER_VERSION` 3 → 4.
- `src/data_collection/fresh_catalog_db.py` — sửa: vé ngày cố định cập nhật mà không có `priceValidUntil` thì xoá hạn cũ.
- `src/data_collection/tests/test_trip_roundtrip_search.py` — thêm: 15 test (fixture modal thật 30/09; chờ/thử lại 432).
- `docs/guide/ve-thuong-gia-va-index-cho.md` — sửa: luồng khứ hồi/xoay vòng, cờ mới, giới hạn robots/432.
- `docs/prd/update/2026-09-30-ve-thuong-gia-mo-phong-cho-demo.md` — sửa: mở rộng sang DB VM (`SIMULATED_BUSINESS_FARES`),
  vé thật thắng, tắt thì khoá; trạng thái vẫn `chờ chốt`.
- `history/2026-09-30-khu-hoi-3-5-7-va-thuong-gia-nhieu-ngay.md` — thêm: entry này.

## Quyết định

- FR-CAT-01, FR-CAT-03, NFR-REL-01. Phần cào không lệch PRD (giá và hạng từ nguồn, không suy). Vé mô phỏng lệch PRD → chỉ
  sửa đề xuất, chưa code.
- Đã đọc: `docs/prd/README.md`, `requirements.md` (FR-CAT), `data-model.md` §3, `docs/spec/data-collection/schema.md`,
  `docs/prd/update/*`, các entry history 30/09 về thương gia/khứ hồi/deploy/merge; code collector, normalise, DB writer, crawl,
  fresh settings.
- Kiểm 30/09: `robots.txt` của vn.trip.com cấm `/flights/showfarefirst*`, `/flights/ShowFareNext*`,
  `/flights/*-to-*/tickets-*`; Chromium headless nhận `HTTP 432` "whaleguard block" cho cả tìm thương gia một chiều lẫn khứ
  hồi. Không lách chống bot. Người yêu cầu vẫn giữ code bật; collector dừng nhanh khi bị chặn.

## Kiểm tra

- `PYTHONPATH=src:src/data_collection python -m pytest -q src/data_collection/tests` (env vsf2): 449 passed, 6 skipped.
- Chạy thật headless 1 lần tìm HAN–SGN (+10 ngày, về sau 3 ngày): trước khi xử lý 432 chờ hết timeout 45 giây; coi 432 là bị
  chặn: báo lỗi sau 1 giây; bản cuối (chờ 45 giây, thử lại): vẫn `HTTP 432`, báo lỗi sau 46 giây.
- Modal khứ hồi đọc bằng trình duyệt tương tác (Claude Browser) 30/09: HAN–SGN 10/10–13/10, VN6025 / 9G808, Phổ thông 2.083.000₫,
  Thương gia 21.621.000₫ — dùng làm fixture.

## Còn lại / rủi ro

- Chờ người yêu cầu chốt đề xuất vé mô phỏng (bản cho cả VM). Chưa code phần đó.
- Trên VM, phần cào thương gia/khứ hồi từ trang tìm kiếm gần như chắc bị chặn (432); lượt `full` sẽ báo nguồn chưa hoàn tất.
- Chưa commit.
