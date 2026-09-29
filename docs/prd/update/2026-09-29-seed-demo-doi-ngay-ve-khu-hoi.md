# Seed demo dời ngày vé khứ hồi vào cửa sổ 30 ngày

- Ngày: 2026-09-29
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/data-model.md` §3 (đoạn "Vé có báo giá theo ngày cố định", dòng 264)
- Mã FR/NFR: FR-CAT-01, FR-CAT-03

## Lý do

Snapshot `2026-09-29` có 290 vé khứ hồi thật của trip.com, ngày đi 30/09 – 24/11/2026. PRD hiện giữ nguyên ngày bay khi seed,
nên số vé khứ hồi đặt được trên máy dev/FE giảm theo ngày chạy `make demo-db-reset`:

| Ngày seed | 29/09 | 15/10 | 05/11 | 15/11 | 25/11 |
|---|---|---|---|---|---|
| Vé khứ hồi đặt được | 189 | 172 | 58 | 11 | 0 |

Sau 24/11, demo không còn vé khứ hồi nào, trong khi vé một chiều cũ (không có `fixedDepartureDate`) vẫn được dời vào cửa sổ và
luôn đặt được. Team FE cần vé khứ hồi ổn định để làm và demo UI `fareClasses`.

## Nội dung đề xuất

`docs/prd/data-model.md`, đoạn "Vé có báo giá theo ngày cố định":

- Hiện tại: "`available_from = available_to` là ngày đi; loader không dời ngày của vé này vào cửa sổ demo."
- Thay bằng:
  - "`available_from = available_to` là ngày đi."
  - "Job cào (VM, dữ liệu thật) không dời ngày của vé này."
  - "Riêng seed demo (`make demo-db`, snapshot có version): vé có ngày đi ngoài cửa sổ được dời vào cửa sổ như vé không cố
    định ngày (as_of + crc32(productId) % 30). Khi dời, cả hai chặng dời cùng số ngày, giữ giờ bay và `stayDays`; `returnDate`
    và ngày trong `name` đổi theo. Dòng bị dời có `attributes.dateShifted: true`."
  - "Giá giữ nguyên từ nguồn, gắn với ngày gốc nên chỉ là giá tham khảo."
  - "`priceValidUntil` giữ nguyên, nên `fareClasses` vẫn báo `EXPIRED` khi báo giá hết hạn."
  - "Vé có ngày đi thật nằm trong cửa sổ thì giữ ngày thật."

Không đổi contract, 13 cột, ID sản phẩm hay cách thêm giỏ.

## Ảnh hưởng

- Có lợi: seed ở ngày nào cũng có đủ 290 vé khứ hồi đặt được, cùng cách xử lý với vé một chiều cũ.
- Đánh đổi (grounding): giá của vé bị dời không phải giá nguồn báo cho ngày mới. Giữ nguyên `priceValidUntil` và thêm
  `dateShifted` để tránh coi đó là báo giá thật; FE có thể ghi "giá tham khảo".
- Không ảnh hưởng DB trên VM / staging nạp bằng job cào: job vẫn giữ ngày thật, cào lại hằng ngày.

## Thay đổi source sau khi chốt

- `src/data_collection/seed/load_products.py`:
  - `fixed_flight_window` / đường seed dời vé `fixedDepartureDate` có ngày ngoài cửa sổ;
  - thêm hàm dời chặng về (`returnFlight.departureAt/arrivalAt`, `returnDate`) và ngày trong `name`; gắn `dateShifted`.
- `src/data_collection/fresh_catalog_db.py` (`apply_window` của job): giữ hành vi hiện tại. Thêm tham số để chỉ seed bật dời
  ngày.
- Test: `src/data_collection/tests/` (seed dời đủ hai chặng, giữ `stayDays`, job không dời).
- `docs/spec/data-collection/schema.md` dòng `fixedDepartureDate`; `docs/spec/MOCK_DATA_SPEC.md` §2.1;
  `src/data_collection/snapshots/README.md`.
- Không cần snapshot mới: dời ngày làm lúc seed theo `--as-of`.
