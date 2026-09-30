# Bàn giao catalog du lịch V-OTA — 23/09/2026

Dữ liệu sản phẩm du lịch thật, thu thập theo §3 handbook RecSys internship v3. Người thu thập: mảng Data.
**Tài liệu bàn giao 23/09/2026, giữ để tra cứu.** Giá quan sát 15/09–22/09/2026. Công cụ sinh gói bàn giao (`make_docs.py`, `finalize_catalog.sh`, `make_handover.py`) đã gỡ ngày 29/09/2026; catalog giờ do job `fresh_catalog.py` tạo.

## 1. Đọc gì trước

| Nếu bạn định… | Đọc file này |
|---|---|
| Viết code đọc catalog | **`SCHEMA.md`** — 13 trường, toàn bộ `attributes`, ngữ nghĩa và bẫy thường gặp |
| Thử nhanh không muốn tải cả catalog | **`sample/`** — bộ mẫu, liên kết cha–con toàn vẹn, có README riêng |
| Tra một khoá cụ thể bằng code | **`template.json`** — bản máy đọc được, mọi khoá `attributes` theo loại kèm độ phủ |
| Biết dữ liệu tới đâu, thiếu gì | **`stats.md`** (thống kê) và `quality_review.csv` (danh sách cần soát) |

## 2. Gói này có gì

| File | Nội dung |
|---|---|
| `products.jsonl` | **Bản chuẩn.** 11.387 sản phẩm, mỗi dòng 1 JSON đúng 13 trường §6 |
| `products.csv`, `products.json` | Cùng dữ liệu ở dạng bảng / mảng JSON, để mở xem. Khi viết code đọc JSONL |
| `catalog/*.json` | Tách theo loại (hotel, flight, attraction, combo, golf) |
| `SCHEMA.md`, `template.json` | Schema dạng người đọc và dạng máy đọc |
| `sample/` | Bộ mẫu chạy thử, liên kết cha–con toàn vẹn |
| `combo_items.jsonl`/`.csv`, `combo_items_review.csv`, `combo_attributes.json` | Thành phần của combo (parse từ tên + mô tả bằng `parse_combos.py`) và `priceBasis`; để loader nạp vào `catalog.combo_items`. `products.jsonl` không đổi |
| `map/` | Ghim bản đồ: CSV cho Google My Maps + `places.geojson` |
| `stats.md`, `quality_review.csv`, `dedup_report.csv` | Thống kê, danh sách cần soát, các cặp trùng đã gộp |
| `excluded_location.csv`, `excluded_auto.csv` | Dòng đã xoá vì lỗi dữ liệu / không phải điểm du lịch, để truy vết |

```python
import pandas as pd
df = pd.read_json("products.jsonl", lines=True)
```

## 3. Số liệu nhanh

- **11.387 sản phẩm** · 38 điểm đến có dữ liệu · 2.321 khách sạn riêng biệt (+ 7.738 hạng phòng)
- Theo loại: hotel 10.059 · attraction 610 · flight 579 · combo 133 · golf 6 (vé máy bay: 113 tuyến + 466 chuyến)
- Theo nguồn chính: booking 9.470 · trip 991 · agoda 498 · vinpearl 428
- **100% mô tả tiếng Việt · 100% có toạ độ** · 97,4% có giá · 94,7% có ảnh (vé máy bay không có ảnh)
- 11.386/11.387 đánh dấu `available` (100,0%); 10.804 có `availableFrom/To`

Catalog chỉ giữ sản phẩm hoàn chỉnh: sản phẩm mà nguồn không cung cấp được giá, dòng có toạ độ sai/thiếu và hạng phòng giá phi lý
đã bị loại, ghi rõ trong mục "Bị loại" của `stats.md`.

## 4. Những điều phải biết trước khi dùng

1. **`available = true` không phải là còn phòng/vé/chỗ.** Nó chỉ nói nguồn có trả giá lúc crawl (riêng điểm tham quan trip.com chưa có giá cũng là `true`, để dùng trong demo). Đừng hiển thị như xác nhận đặt được; luồng đặt thật phải gọi lại nguồn.
2. **`unitPrice = null` không phải là miễn phí.** 300 sản phẩm còn `null`, 300 là điểm tham quan trip.com không hiện giá
   (chưa rõ có bán vé không). Web cần trạng thái hiển thị riêng, không quy về 0 đồng.
3. **75,6% mô tả là tự sinh** từ dữ liệu có cấu trúc, nhận biết qua `attributes.descriptionSource`. Điều khoản vé đã được tách khỏi `description` sang `attributes.policies`.
4. **Giá là một lần hỏi giá:** khách sạn nhận phòng 2026-10-15, 1 đêm, 2 người lớn; sau ngày đó giá là của quá khứ. Vé máy bay là giá tham khảo theo ngày bay trip.com liệt kê.
5. **`availableFrom/To` chỉ có ở 10.804 sản phẩm** (vé/combo/golf Vinpearl = thời gian bán, vé máy bay = các ngày bay đã liệt kê). Khách sạn và điểm trip.com để `null` vì nguồn không công bố.
   Giờ bay (`departureTimeLocal`) là **giờ Việt Nam**.

## 5. Độ phủ từng trường — đọc trước khi code

| Loại | n | có giá | ảnh | mô tả ≥200 ký tự | sao/điểm | toạ độ | giờ mở cửa |
|---|---|---|---|---|---|---|---|
| hotel_property | 2.321 | 100% | 100% | 99% | 98% | 100% | – |
| hotel_room | 7.738 | 100% | 100% | 100% | 70% | 100% | – |
| attraction | 610 | 51% | 100% | 47% | 36% | 100% | 68% |
| flight | 579 | 100% | **0%** | 94% | – | 100% | – |
| flight_route | 113 | 100% | **0%** | 76% | 0% | 100% | – |
| combo | 133 | 100% | 83% | 63% | 48% | 100% | 19% |
| golf | 6 | 83% | 100% | 83% | 0% | 100% | 17% |

Chỗ dưới 100% đều thuộc về bản chất dữ liệu: điểm tham quan thiếu giá là điểm trip.com không hiện giá; vé máy bay không có ảnh vì một chuyến bay không có ảnh sản phẩm.

## 6. Ghi chú theo đội

**Web** — `imageUrl` phủ 94,7%; chỉ 579 vé máy bay không có ảnh (dùng placeholder hoặc logo hãng qua `airlineCode`/`airlines`).
Cần trạng thái hiển thị riêng cho 300 điểm chưa có giá so với sản phẩm có giá — đừng quy về 0 đồng. Ảnh phụ nằm trong `attributes.images` (3.147 sản phẩm, trung vị 9 ảnh).

**Agent (trợ lý lịch trình)** — `products.jsonl` có `latitude`/`longitude` cho 100% sản phẩm, dùng thẳng là đủ.
`map/places.geojson` là bản gom theo địa điểm (2.806 điểm thay vì 11.387 sản phẩm, mỗi điểm kèm `items` có `productId`).
`openingHours` chỉ có ở 68% điểm tham quan và 19% combo, `durationMinutes` 40% điểm tham quan
→ chưa đủ xếp lịch theo giờ cho mọi sản phẩm. `locationPrecision = venue` (297 sản phẩm) là vị trí khu vui chơi chứ không phải vị trí riêng của vé.
Còn 4 sản phẩm mang `locationWarning` (Vinpearl được giữ), xem `quality_review.csv`.

**RecSys** — 8.611 mô tả tự sinh; kiểm tra `attributes.descriptionSource` trước khi đưa vào text builder. Câu mô tả khách sạn và câu mô tả vé máy bay không nên xây cùng một cách.
Hạng phòng cùng khách sạn có mô tả gần trùng nhau: nên gom kết quả theo `parentProductId` (hoặc embed cấp khách sạn) để top-k không bị một khách sạn chiếm hết.
Toàn bộ catalog là tiếng Việt, nên `all-MiniLM-L6-v2` — mô hình chỉ hỗ trợ tiếng Anh mà mọi tutorial đều dùng — sẽ cho kết quả gần như ngẫu nhiên; cần mô hình đa ngôn ngữ.
**Gợi ý chéo danh mục:** 15/30 điểm đến có khách sạn có tuyến bay *đến* nó. Điểm đến có khách sạn nhưng không có sân bay riêng
(Cát Bà (35), Hà Tĩnh (28), Hạ Long (122), Hội An (140), Ninh Bình (61), Phan Thiết (111), Pleiku (30), Rạch Giá (29), Sa Pa (133), Tuy Hòa (30), Điện Biên (35)) cần ánh xạ sang sân bay gần nhất khi gợi ý vé máy bay.

## 7. Pháp lý và dữ liệu cá nhân

- **Không có dữ liệu cá nhân.** Review, tên và ảnh người đánh giá bị xoá trước khi ghi đĩa. Chỉ giữ điểm trung bình và số lượt.
- Điều khoản booking.com và agoda.com không cho phép thu thập tự động. **Dữ liệu chỉ dùng nội bộ cho demo thực tập, không phân phối lại, không đưa lên repo hay trang công khai.**
- Toạ độ OpenStreetMap theo giấy phép ODbL: khi hiển thị bản đồ phải ghi "© OpenStreetMap contributors". Toạ độ sân bay từ OurAirports (public domain).
- Không ghi gì vào CDP hay Insider production.

## 8. Tái tạo bộ dữ liệu

Code và hướng dẫn đầy đủ: `src/data_collection/README.md` trong monorepo. Sau khi cào xong và dừng các tiến trình cào, chạy một lệnh:

```
./finalize_catalog.sh     # sao lưu → gộp batch → chuẩn hoá → catalog → template.json + sample/ + SCHEMA.md + BANGIAO.md
```

Kiểm tra hồi quy: `python -m unittest discover -s . -p "test_*.py"` (không cần mạng).
