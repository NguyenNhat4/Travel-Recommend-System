# Cào theo thành phố, giữ nguyên template Product

Môi trường: dùng Python của env conda `vsf` (`conda activate vsf`; nơi không có shell tương tác thì gọi thẳng
`~/miniconda3/envs/vsf/bin/python`). Mọi lệnh chạy trong `src/data_collection/` của monorepo.

## Đợt lớn 19/09/2026: 67 điểm đến, mục tiêu ~10.000 Product

Luồng: **cào theo job → theo dõi bằng UI → xem bản xem trước → chốt catalog**. Rate-limit dùng chung theo host,
nên số terminal hữu ích bằng số host (Booking, Agoda, Trip); thêm terminal cùng host không nhanh hơn.

| Bước | Lệnh |
|---|---|
| Theo dõi (UI, chỉ đọc) | `python monitor.py` rồi mở http://127.0.0.1:8765 |
| Trip điểm tham quan + chuyến bay (HTTP, nhẹ) | `python batch.py run trip-attractions --cities @all --per-destination 100` rồi `python batch.py run trip-flights` |
| Booking khách sạn (cửa sổ Chromium) | `python batch.py run booking-hotels --cities @core --per-destination 100 --dates 2026-10-15 --fast --concurrency 2`, rồi `--cities @new --per-destination 60` |
| Agoda khách sạn (cửa sổ Chromium) | `python batch.py run agoda-hotels --cities @all --per-destination 100 --dates 2026-10-15 --concurrency 2` |
| Cào thêm trên Booking (nối tiếp, chỉ trong giờ có mặt) | `./run_extra_queue.sh` (khung 07:00–23:00, chỉnh bằng `FROM=`/`UNTIL=`): chờ khách sạn Booking xong → vé/tour Booking tối đa 2.500 trang (mỗi đợt 500) → 19 điểm nhỏ `@extra` × 40 khách sạn → đào sâu 8 thành phố `@deep` 100 → 200 khách sạn |
| Thử lại khách sạn chưa có giá | `python retry_unpriced.py` xem kế hoạch, `--run` để chạy (ngày +14, +45) |
| Xem con số thật trước khi chốt | nút **Tạo bản xem trước** trong monitor (ghi vào `data/preview/`, không đụng catalog chính) |
| Chốt catalog | `./finalize_catalog.sh` (sao lưu → merge → normalise → catalog) |

`--cities` nhận tên (có hoặc không dấu) hoặc `@core` (15 điểm gốc), `@new` (33 điểm mở rộng), `@extra` (19 điểm nhỏ chỉ Booking), `@deep` (8 thị trường lớn), `@all`.
Ngày hỏi giá cố định `2026-10-15` để khớp với catalog đợt trước; mỗi giá ghi ngày thật trong `priceQuery`.

**Đào sâu không cào lại:** job batch được đặt tên theo tham số (gồm `--per-destination`), nên đổi 100 → 200 sẽ tạo job mới và cào lại
100 khách sạn đầu. `python deepen_jobs.py --cities @deep --to 200 --apply` tạo sẵn job 200 với hàng đợi sao chép từ job 100
(URL đã cào đánh dấu `skipped`), rồi `batch.py run booking-hotels --cities @deep --per-destination 200 ...` chỉ cào phần mới.
Dừng hàng đợi nền: `pkill -INT -f run_extra_queue.sh; pkill -INT -f "batch.py run"`; chạy lại cùng lệnh để tiếp tục.

### Trạng thái chốt 19/09/2026 14:51

Đã dừng cào (Booking 16/16 thành phố gốc + Ninh Bình, Côn Đảo, Cần Thơ dở dang; Agoda 13/15) và chốt catalog: **10.323 sản phẩm**
(9.105 hotel gồm 2.116 cơ sở, 571 attraction, 93 combo, 6 golf, 548 flight); 97% có giá, 100% có toạ độ; 35/67 điểm đến có dữ liệu.
Bản sao lưu trước khi ghi đè: `data/backups/finalize-20260919-145124/`. Chưa cào: Vũng Tàu (Booking gặp trang xác minh do mạng chập chờn lúc
14:33), Agoda Sa Pa (49 URL lỗi chứng chỉ TLS cùng lúc, vẫn `failed`, chạy lại là lấy tiếp), phần lớn 33 điểm mở rộng và 19 điểm nhỏ, vé/tour Booking,
đào sâu 8 thành phố. Muốn tiếp tục: chạy lại đúng các lệnh ở bảng trên (hàng đợi tiếp tục từ chỗ dừng) rồi `./finalize_catalog.sh`.
Dừng êm bất cứ lúc nào: `./stop_crawl.sh` (nếu có tab đang chạy vòng chờ `while pgrep ...`, Ctrl-C tab đó trước).

### Thay đổi so với luồng cũ, và lý do

1. **Booking chỉ trả 15–20 khách sạn mỗi điểm đến** dù đặt `--per-destination 100`: tham số `offset` trong URL không còn
   hiệu lực (trang 2 trả lại đúng 15 thẻ của trang 1). Nay cuộn rồi bấm **"Tải thêm kết quả"** (mỗi lần ~20 khách sạn,
   Nha Trang lên 100–120). Việc cuộn chỉ tải thêm khi có CSS nên bước tìm URL tạm tắt `--fast`; hộp thoại quảng cáo
   "Đăng nhập để tiết kiệm" được đóng bằng nút "Bỏ qua phần đăng nhập." (không đăng nhập gì).
2. **Việc dùng chung chỉ làm một lần** thay vì lặp ở mỗi job: khách sạn thương hiệu Vinpearl trên Booking (`--brand-only`,
   một job toàn quốc) và cache trang dùng chung (`data/batches/shared/`: sitemap, trang sân bay, danh sách Trip).
3. **Chuyến bay: một job cho mỗi sân bay đến** (tối đa 21) thay vì 110 job mỗi tuyến một tiến trình. URL tuyến của Trip dùng
   *mã thành phố của Trip* (Nha Trang là `nha`, sân bay CXR), không phải IATA; bộ lọc `--routes` cũ so nhầm hai loại mã
   nên bỏ sót tuyến Nha Trang. Nay ánh xạ IATA ↔ mã Trip suy ra từ chính trang sân bay.
4. **Booking Flights không dùng được** (xem mục chuyến bay bên dưới).
5. **Hội An chưa từng có điểm tham quan Trip**: `hoi-an-668` trả 404 và Trip không có trang danh sách riêng cho Hội An.
6. **Lọc điểm tham quan theo quy tắc** (bảo hiểm, y tế, taxi/thuê xe, ngân hàng, siêu thị, trường học, cơ quan, bất động sản,
   đại lý lữ hành, quán ăn/cà phê) thay cho danh sách tay; điểm bị loại nằm trong `data/excluded_auto.csv` để soát lại.
7. **Form catalog không đổi**: 13 trường của Product và các khoá trong `attributes` giữ nguyên. Cờ `hasRoomRows` (khách sạn chỉ có ở
   Agoda không có dòng phòng theo thiết kế) và `rentalUnit=entire_place` chỉ có khi chủ động bật
   `normalise.py --annotate-hotel-granularity`; `finalize_catalog.sh` không bật. Tình trạng còn phòng không nằm trong mô tả
   để embedding, chỉ là bộ lọc lúc truy vấn.
8. **Điểm đến chưa có slug Agoda / ID Trip đã kiểm chứng không tạo job** (Agoda còn mở cả cửa sổ trình duyệt rồi đóng ngay).
9. Sửa khớp điểm đến từ địa chỉ: bỏ qua tên đường trùng tên địa danh ("Đường Hai Bà Trưng", "Bien Hoa Street", "Nguyễn Huệ",
   "Điện Biên Phủ" không kèm "thành phố"), đã bảo toàn "Thành phố X". Bán kính Hà Tĩnh 30 → 50 km (resort ven biển cách thành phố 34–45 km).
10. **Dòng lỗi dữ liệu bị xoá khi chuẩn hoá** (theo yêu cầu 19/09/2026: không phải soát tay rồi thêm lại). Mặc định xoá, cùng hạng phòng/chuyến
    bay con: (a) dòng có `attributes.locationWarning` (toạ độ xa tâm điểm đến quá bán kính), (b) dòng thiếu toạ độ, (c) sản phẩm không có giá
    mà nguồn không cung cấp được (khách sạn/combo/golf/tuyến; điểm công cộng không bán vé vẫn giữ), (d) dòng con mồ côi. Danh sách (a)(b)(d) ở
    `data/excluded_location.csv`; tổng theo lý do ở mục "Bị loại" của `stats.md`. Sản phẩm Vinpearl và khách sạn mang thương hiệu Vinpearl luôn
    được giữ. Cờ giữ lại: `--keep-location-warnings`, `--keep-missing-coordinates`, `--keep-unsellable`. Lưu ý: toạ độ các dòng cảnh báo vị trí
    thường **đúng**, chỉ nhãn điểm đến sai (sáp nhập tỉnh 2025 khiến trang Trip "Gia Lai", "Đắk Lắk", "Đồng Tháp", "Vĩnh Long" chứa cả điểm ở tỉnh cũ).

## Luồng chính: cào theo thành phố trước, chia taxonomy sau

**Không cần chọn taxonomy khi cào.** Chọn một hoặc nhiều thành phố; mặc định chạy các bộ cào hiện có:
Vinpearl (hotel và vé/combo/golf), Booking hotel, Agoda hotel, Trip attraction, Trip flight. Booking flight và Booking vé/tour là nguồn chọn thẳng (`batch.py run booking-attractions`).

```bash
# Một thành phố, tất cả nguồn đang tích hợp
python batch.py run --cities 'Hà Nội'

# Nhiều thành phố; xem kế hoạch trước, bỏ --dry-run để chạy
python batch.py run --cities 'Hà Nội,Đà Nẵng,Nha Trang' --dry-run

# Chia cùng kế hoạch ra 3 terminal: lần lượt dùng 1/3, 2/3, 3/3
python batch.py run --cities 'Hà Nội,Đà Nẵng,Nha Trang' --worker 1/3
```

Theo thứ tự trong mỗi worker: Vinpearl toàn nguồn một job dùng chung, rồi các nguồn theo từng thành phố.
Các job của cùng thành phố có thể nằm ở worker khác nhau. Source bị chặn sẽ dừng các job còn lại của
source đó trong worker; các source khác tiếp tục. Chạy lại cùng lệnh để tiếp tục phần đang dở.

“Tất cả” ở đây là tất cả bộ cào đã tích hợp và dữ liệu chúng đọc được, **chưa phải cam kết toàn bộ
sản phẩm trên mọi website**. Hotel/attraction vẫn có `--per-destination` và giới hạn discovery của
từng adapter: Booking hotel hiện tối đa 8 trang tìm kiếm mỗi điểm đến; Agoda đọc các link hiện trên
trang thành phố. Tăng quota không tự vượt được giới hạn discovery. Chưa có adapter VinWonders độc lập.
Phần chuyến bay có phạm vi và báo cáo riêng bên dưới, không dùng quota `--per-destination`.

Khi cào xong, xuất mỗi thành phố một JSON gồm mọi taxonomy, rồi mới chia taxonomy/gộp catalog:

```bash
python batch.py merge
python normalise.py --no-plan --rooms-per-hotel 0 --flights-per-route 0
python catalog.py cities
python catalog.py split
python catalog.py merge
```

`data/cities/ha-noi.json`, `data/cities/da-nang.json`… chứa Product của từng thành phố;
`data/cities/_index.json` liệt kê file, số Product và số lượng từng taxonomy. Chúng được tạo sau
chuẩn hóa để các nguồn dùng cùng destination và cùng ID. `catalog.py split` và `cities` đều đọc
`data/products.jsonl`; không cần ghép lại các bản sao thành phố để tạo bảng taxonomy.
Chỉ các file ghi trong `_index.json` thuộc lần xuất hiện tại; file cũ ngoài index không tự bị xóa.

## Danh sách điểm đến (67)

Đối chiếu `collectors/plan.py`, sinh tự động ngày 19/09/2026. **15 điểm gốc** của handbook (`@core`), **33 điểm mở rộng** (`@new`)
và **19 điểm nhỏ chỉ cào từ Booking** (`@extra`); `@deep` là 8 thị trường lớn được cào sâu hơn (200 khách sạn Booking). Đây là điểm đến
du lịch (thành phố, tỉnh/vùng, đảo), không phải danh mục đơn vị hành chính. Cột Agoda/Trip là `✓` khi đã có slug/ID được kiểm chứng
trên chính nguồn (Agoda: trang trả 200 hoặc 301 sang slug chuẩn, slug lạ bị chuyển 302 sang `pagenotfound`; Trip: trang
`tourist-attractions` trả 200 và tên trong tiêu đề khớp). Ô `–` nghĩa là chưa kiểm chứng được, **không đoán**: nguồn đó bỏ qua điểm đến này.
Booking chỉ cần tên tìm kiếm nên có mặt ở cả 67. Sân bay chỉ gán khi sân bay nằm trong địa phương đó.
Cát Bà, Lý Sơn, Sầm Sơn, Hà Tiên, Phong Nha trước là địa danh con của Hải Phòng, Quảng Ngãi, Thanh Hóa, Rạch Giá, Quảng Bình;
nay là điểm đến riêng nên bản ghi cũ ở đó được gán lại khi chuẩn hoá (`geo.py`).

| STT | Điểm đến | Agoda | Trip | Sân bay | Nhóm |
|---:|---|:-:|:-:|---|---|
| 1 | Nha Trang | ✓ | ✓ | CXR | gốc · đào sâu |
| 2 | Phú Quốc | ✓ | ✓ | PQC | gốc · đào sâu |
| 3 | Hội An | ✓ | – | – | gốc · đào sâu |
| 4 | Đà Nẵng | ✓ | ✓ | DAD | gốc · đào sâu |
| 5 | Hạ Long | ✓ | ✓ | VDO | gốc · đào sâu |
| 6 | Hà Nội | ✓ | ✓ | HAN | gốc · đào sâu |
| 7 | TP. Hồ Chí Minh | ✓ | ✓ | SGN | gốc · đào sâu |
| 8 | Hải Phòng | ✓ | ✓ | HPH | gốc |
| 9 | Nghệ An | ✓ | ✓ | VII | gốc |
| 10 | Hà Tĩnh | ✓ | – | – | gốc |
| 11 | Đà Lạt | ✓ | ✓ | DLI | gốc · đào sâu |
| 12 | Huế | ✓ | ✓ | HUI | gốc |
| 13 | Quy Nhơn | ✓ | ✓ | UIH | gốc |
| 14 | Sa Pa | ✓ | ✓ | – | gốc |
| 15 | Phan Thiết | ✓ | ✓ | – | gốc |
| 16 | Ninh Bình | ✓ | – | – | mới |
| 17 | Vũng Tàu | ✓ | – | – | mới |
| 18 | Côn Đảo | ✓ | – | VCS | mới |
| 19 | Cần Thơ | ✓ | ✓ | VCA | mới |
| 20 | Hà Giang | ✓ | – | – | mới |
| 21 | Cao Bằng | ✓ | ✓ | – | mới |
| 22 | Mộc Châu | ✓ | – | – | mới |
| 23 | Buôn Ma Thuột | ✓ | ✓ | BMV | mới |
| 24 | Pleiku | – | ✓ | PXU | mới |
| 25 | Tuy Hòa | – | ✓ | TBB | mới |
| 26 | Châu Đốc | – | ✓ | – | mới |
| 27 | Bắc Ninh | ✓ | – | – | mới |
| 28 | Thanh Hóa | ✓ | – | THD | mới |
| 29 | Quảng Bình | – | ✓ | VDH | mới |
| 30 | Tây Ninh | ✓ | – | – | mới |
| 31 | Kon Tum | ✓ | ✓ | – | mới |
| 32 | Cà Mau | ✓ | – | CAH | mới |
| 33 | Bến Tre | ✓ | ✓ | – | mới |
| 34 | Mỹ Tho | – | ✓ | – | mới |
| 35 | Sóc Trăng | ✓ | – | – | mới |
| 36 | Bạc Liêu | ✓ | – | – | mới |
| 37 | Điện Biên | ✓ | ✓ | DIN | mới |
| 38 | Lạng Sơn | ✓ | – | – | mới |
| 39 | Sơn La | ✓ | – | – | mới |
| 40 | Biên Hòa | – | ✓ | – | mới |
| 41 | Vĩnh Long | ✓ | – | – | mới |
| 42 | Đồng Tháp | ✓ | – | – | mới |
| 43 | Quảng Trị | ✓ | ✓ | – | mới |
| 44 | Quảng Ngãi | ✓ | – | – | mới |
| 45 | Phan Rang | – | – | – | mới |
| 46 | Tam Đảo | ✓ | – | – | mới |
| 47 | Mai Châu | – | – | – | mới |
| 48 | Rạch Giá | – | ✓ | VKG | mới |
| 49 | Cát Bà | – | – | – | nhỏ (chỉ Booking) |
| 50 | Lý Sơn | – | – | – | nhỏ (chỉ Booking) |
| 51 | Sầm Sơn | – | – | – | nhỏ (chỉ Booking) |
| 52 | Hà Tiên | – | – | – | nhỏ (chỉ Booking) |
| 53 | Bảo Lộc | – | – | – | nhỏ (chỉ Booking) |
| 54 | Phong Nha | – | – | – | nhỏ (chỉ Booking) |
| 55 | Vân Đồn | – | – | – | nhỏ (chỉ Booking) |
| 56 | Mù Cang Chải | – | – | – | nhỏ (chỉ Booking) |
| 57 | Thái Nguyên | – | – | – | nhỏ (chỉ Booking) |
| 58 | Nam Định | – | – | – | nhỏ (chỉ Booking) |
| 59 | Vĩnh Phúc | – | – | – | nhỏ (chỉ Booking) |
| 60 | Móng Cái | – | – | – | nhỏ (chỉ Booking) |
| 61 | Long Xuyên | – | – | – | nhỏ (chỉ Booking) |
| 62 | Bắc Kạn | – | – | – | nhỏ (chỉ Booking) |
| 63 | Hà Nam | – | – | – | nhỏ (chỉ Booking) |
| 64 | Trà Vinh | – | – | – | nhỏ (chỉ Booking) |
| 65 | Tam Kỳ | – | – | – | nhỏ (chỉ Booking) |
| 66 | Gia Nghĩa | – | – | – | nhỏ (chỉ Booking) |
| 67 | Thái Bình | – | – | – | nhỏ (chỉ Booking) |

Tổng: 39 điểm có Agoda, 27 có Trip điểm tham quan, 21 sân bay đến. Muốn thêm ID còn thiếu: kiểm chứng bằng cách mở trang nguồn, rồi
sửa `plan.py` (Trip nhận slug tuỳ ý miễn ID số đúng; các ID Việt Nam nằm trong dải 24722–24782).
Chưa có gì tự chạy sang điểm mới: lệnh chỉ cào phạm vi bạn chọn qua `--cities`.

## Tỷ lệ taxonomy ban đầu và sau làm giàu

“Ban đầu” ở đây là catalog **2.216 Product** trước lần nhập Trip ngày 19/09/2026, có bản sao ở
`data/backups/20260919-city-enrichment/products.jsonl`. “Hiện tại” là `data/products.json`, **3.082 Product**.

| Taxonomy | Ban đầu | Tỷ lệ ban đầu | Hiện tại | Tỷ lệ hiện tại |
|---|---:|---:|---:|---:|
| hotel | 1.466 | 66,16% | 2.195 | 71,22% |
| flight | 244 | 11,01% | 356 | 11,55% |
| attraction | 407 | 18,37% | 420 | 13,63% |
| combo | 93 | 4,20% | 105 | 3,41% |
| golf | 6 | 0,27% | 6 | 0,19% |
| **Tổng** | **2.216** | **100%** | **3.082** | **100%** |

Phần trăm làm tròn có thể cộng lệch 0,01 điểm phần trăm. Đây là tỷ lệ bản ghi thực tế, **không phải quota**:
hotel tính cả property và room; flight tính cả route và flight. Ban đầu hotel = 559 property + 907 room,
flight = 60 route + 184 flight. Hiện tại hotel = 583 property + 1.612 room, flight = 61 route + 295 flight.
Không hiểu 2.195 hotel là 2.195 cơ sở lưu trú khác nhau. RecSys nên kiểm soát việc nhiều room cùng một
property chiếm hết danh sách gợi ý; mở rộng dữ liệu không tự cân bằng phân bố taxonomy.

Nếu “ban đầu” là file template 6 dòng bạn gửi: hotel 2, flight 2, attraction 1, combo 1, golf 0.
Đó chỉ là ví dụ schema, không phải phân bố mục tiêu. Handbook §3 đặt mục tiêu 2.000–5.000 sản phẩm,
10–15 điểm đến, không quy định phần trăm cứng cho mỗi taxonomy. Kế hoạch 30 điểm bên trên là đề xuất
mở rộng theo yêu cầu mới của bạn.

Giới hạn cào/xuất ban đầu trong `collectors/plan.py` là Booking 30 khách sạn, Agoda 20 khách sạn,
Trip 25 điểm tham quan **mỗi điểm đến**; khi xuất giữ tối đa 3 hạng phòng OTA/khách sạn và 5 số hiệu
chuyến/tuyến. Batch mặc định `--per-destination 100`: Booking 100, Agoda 66, Trip attraction 100,
do Agoda dùng `floor(2 × per-destination / 3)`. Đây là số tối đa yêu cầu, không đảm bảo website trả đủ;
trùng nguồn và phân loại sau parse còn làm thay đổi số Product. Vinpearl và flight không dùng quota này.

## Tuỳ chọn: chỉ chạy một nguồn hoặc một taxonomy

Các lệnh dưới chỉ cần khi muốn chạy bổ sung có chọn lọc. Luồng chính ở đầu tài liệu bỏ `--taxonomy`.

```bash
# Khách sạn + hạng phòng: mỗi thành phố tối đa 100 Booking và 66 Agoda
python batch.py run --taxonomy hotel --cities 'Hà Nội' --per-destination 100
python batch.py run --taxonomy hotel --cities 'Đà Nẵng,Nha Trang,Phú Quốc' --per-destination 200

# Chuyến bay (Trip); chọn thành phố ĐẾN
python batch.py run --taxonomy flight --cities 'Hà Nội,Đà Nẵng' --origins SGN,CXR

# Điểm tham quan Trip và vé Vinpearl
python batch.py run --taxonomy attraction --cities 'Nha Trang,Phú Quốc'

# Hoặc chọn đúng một nguồn
python batch.py run trip-attractions --cities 'Hà Nội,Đà Nẵng' --per-destination 100
python batch.py run trip-flights --cities 'Hà Nội' --origins SGN,DAD
```

Không truyền `--cities` thì dùng cả 15 điểm đến trong `collectors/plan.py`. Tên không dấu được chấp nhận;
tên chưa có trong cấu hình sẽ báo lỗi, không tự đoán ID của nguồn. Bốn điểm Hội An, Hà Tĩnh, Sa Pa,
Phan Thiết chưa có sân bay trong cấu hình nên flight báo SKIP; không tự gán sân bay gần đó.
Catalog không giới hạn 15 điểm đến, nhưng bộ lập kế hoạch hiện mới cấu hình 15. Booking còn có
`python crawl.py booking-hotels --all-vietnam` để discovery rộng hơn từ sitemap, tách khỏi batch theo thành phố.

`--taxonomy` chọn các nguồn để làm giàu loại sản phẩm đó. Vinpearl vé/combo/golf dùng chung discovery
toàn nguồn và chưa lọc thành phố; `combo` và `golf` chạy cùng một job Vinpearl nên có thể tiếp tục cache.
Chưa có adapter VinWonders độc lập mới trong lần thay đổi này. Hotel dùng dữ liệu Vinpearl đã có trong
catalog; cập nhật riêng bằng `python crawl.py vinpearl`.

## Nhiều terminal

Cùng câu lệnh và cùng `--root`, chỉ thay `--worker`:

```bash
# Terminal 1
python batch.py run --taxonomy hotel --cities 'Hà Nội,Đà Nẵng,Nha Trang,Phú Quốc' --worker 1/3
# Terminal 2
python batch.py run --taxonomy hotel --cities 'Hà Nội,Đà Nẵng,Nha Trang,Phú Quốc' --worker 2/3
# Terminal 3
python batch.py run --taxonomy hotel --cities 'Hà Nội,Đà Nẵng,Nha Trang,Phú Quốc' --worker 3/3
```

Hoặc mỗi terminal chọn thành phố/nguồn khác nhau và để mặc định `--worker 1/1`. Không cần cả hai
cách chia cùng lúc. Mỗi job có state, cache và browser profile riêng dưới `data/batches/<job-id>/`;
job trùng đang chạy bị khóa. Chạy lại cùng lệnh để tiếp tục. Giữ cùng tổng số worker khi đang chạy.
Mọi batch cùng root dùng `rate.sqlite3` để giãn cách thao tác theo host giữa các tiến trình;
tăng terminal không nhân tốc độ truy cập website vô hạn. Bắt đầu 2–3 terminal để tránh hết RAM.
Giới hạn này áp dụng thao tác điều hướng/HTTP của collector; không điều khiển từng subrequest của browser.

Thêm `--dry-run` để xem job, `--limit 1` để chạy thử mỗi job. Limit là giới hạn trang, không phải sản phẩm.
Không ghi nhiều tiến trình normalise vào cùng output. Nên dừng worker trước khi merge; merge từ chối
đọc source đang chạy. Các thư mục dữ liệu cũ ngoài batch vẫn dùng khóa một tiến trình/nguồn như trước.

## Cào xong lưu ở file riêng của thành phố không?

**Trong lúc cào: tách dữ liệu theo job. Sau chuẩn hóa: dùng `python catalog.py cities` để xuất
`ha-noi.json`, `da-nang.json`… chứa tất cả taxonomy của thành phố đó.**
Một lệnh nhiều thành phố tạo nhiều job. Hotel/attraction chia theo thành phố + nguồn; hotel có thêm
ngày tra cứu. Flight chia theo sân bay đến (mỗi job gồm mọi tuyến tới sân bay đó). Vì vậy một thành phố có thể có nhiều
job, không có quan hệ một thành phố = một file duy nhất.

```text
data/batches/
  query-day.txt                         # ngày tra cứu mặc định của campaign
  rate.sqlite3                          # giới hạn tốc độ dùng chung
  <job-id>/
    job.json                            # city, source, route/period và tham số
    raw/<source>/...                    # bằng chứng nguồn đã lọc, nén gzip
    interim/<source>.jsonl              # kết quả đã parse, mỗi dòng một observation
    state/...                           # hàng đợi và tiến độ resume
    browser-profile/...                # profile nếu nguồn dùng browser
    last-run.json                       # mã thoát lần chạy gần nhất
```

Ví dụ Booking hotel Hà Nội nằm trong `interim/booking_hotels.jsonl` của job có
`job.json` chứa `city: "Hà Nội"`, `source: "booking-hotels"`. Một job Agoda Hà Nội có file
`interim/agoda_hotels.jsonl` riêng. Vinpearl là ngoại lệ: một job toàn nguồn, `city: "all"`.
JSONL trung gian còn là schema từng nguồn; **chưa phải template Product 13 trường**.

Liệt kê các job và đường dẫn để tìm dữ liệu của thành phố:

```bash
python - <<'PY'
import json
from pathlib import Path
for manifest in sorted(Path('data/batches').glob('*/job.json')):
    job = json.loads(manifest.read_text(encoding='utf-8'))
    source = job['source'].replace('-', '_')
    file = manifest.parent / 'interim' / f'{source}.jsonl'
    print(job['city'], job['source'], job.get('route', ''), file, sep=' | ')
PY
```

`batch.py merge` đọc các file riêng này, nhập vào `data/interim/<source>.jsonl` dùng chung.
`normalise.py` sau đó chuẩn hóa và khử trùng lặp giữa các nguồn/thành phố. `catalog.py cities` tách
theo thành phố; `catalog.py split` tách theo taxonomy. Hai cách xuất đều giữ nguyên template 13 trường.

## Giá và availability thật

Mặc định mỗi job hỏi giá **một ngày**: ngày bắt đầu campaign + 30, lưu cố định ở `data/batches/query-day.txt`
để resume qua đêm không đổi ngày. Hotel: 1 đêm/2 người lớn. Flight: 1 chiều/1 người lớn/economy.
Đổi bằng `--dates 2026-10-20`. Ngày đó là điều kiện hỏi giá, không phải ngày cào hay ngày giả lập còn hàng.
Không cần chạy lịch tháng để mở rộng catalog. Tùy chọn tháng vẫn có nếu sau này cần: `--year 2027 --months 1,2`.

- `attributes.priceObservedAt`: thời điểm thu thập, giữ nguyên khi reparse/import.
- Hotel: `priceQuery`, `checkIn/checkOut`; Vinpearl giữ các ngày thực có giá trong `pricesByDate`
  và `availabilityDatesObserved`. Không kéo các ngày rời rạc thành khoảng liên tục.
- Flight: `departureAt/arrivalAt`, `datesSeen`; Booking còn có offer và điều kiện khách/hạng vé.
- Vé/combo/golf: giữ khoảng nguồn công bố. Với `saleStartDate/saleEndDate`, nhãn
  `availabilityRangeKind=sale_window` nghĩa là khoảng **mở bán**, không khẳng định ngày sử dụng.
- `availableFrom/availableTo` không có bằng chứng rõ thì `null`. Không sinh ngày hay giá random.
  `available` là quan sát theo điều kiện tra cứu, không bảo đảm còn hàng lúc người dùng đặt sau này.
- Trip SEO là giá tham khảo, không xác minh tồn chỗ hiện tại. Từ 19/09/2026 (theo yêu cầu: dữ liệu để mock, thanh toán giả)
  chuyến/tuyến có giá được đánh dấu `available=true` và `availableFrom/To` = ngày bay sớm nhất/muộn nhất trip.com liệt kê
  (giờ Việt Nam); không thêm cờ phụ (`bookable`, `priceKind`, `availabilityStatus`). Thời điểm chuyến bay trong JSON-LD của
  trip.com là **UTC** (`…Z`), catalog quy về giờ Việt Nam (+07:00).
  Chuyến từng thấy nhưng vắng trong snapshot tuyến mới vẫn giữ ID, ngày quan sát cũ và
  `notInLatestSnapshot=true`; không lấy thời điểm crawl mới gán vào giá cũ.

**Booking Flights không dùng được (kiểm 19/09/2026).** Trình duyệt thường mở
`flights.booking.com` cho SGN→HAN ngày 15/10/2026 thấy **281 chuyến**, còn phiên Playwright của crawler nhận trang
"Không có chuyến bay nào khớp với tìm kiếm" cho cả 15/10, 17/10 và 20/11. Đây là kết quả rỗng dành cho phiên tự động, không phải
lỗi selector hay hết chỗ. Cách duy nhất để lấy là che dấu hiệu tự động (stealth, đổi fingerprint), việc dự án này không làm,
nên `booking-flights` không nằm trong mặc định. Muốn giá vé thời gian thực cần nguồn có giấy phép (API đối tác của hãng/OTA).

**Chuyến bay hiện lấy từ dữ liệu có cấu trúc của trip.com** (`trip-flights`): giá thấp/cao theo tháng và các chuyến cụ thể (số hiệu,
hãng, giờ bay, giá) trên trang giá vé từng tuyến. Đây là giá tham khảo tại thời điểm quan sát, không xác minh còn chỗ;
`available=true` chỉ nghĩa là trip.com liệt kê chuyến này kèm giá (xem trên). Giờ bay đã quy từ UTC về giờ Việt Nam.

```bash
# Mọi tuyến tới các sân bay đến của điểm đến đã chọn (một job cho mỗi sân bay đến)
python batch.py run trip-flights --cities @all
python batch.py run trip-flights --cities 'Hà Nội,Đà Nẵng' --origins SGN,CXR
```

`normalise.py` giữ mọi số hiệu thu thập được (`--flights-per-route 0`). Chuyến từng thấy nhưng vắng trong snapshot mới vẫn giữ
ID và ngày quan sát cũ (`notInLatestSnapshot=true`). Product flight là cấp số hiệu; một tuyến có sản phẩm cấp `route` riêng.

## Gộp observations → chuẩn hóa → 5 bảng → products.json

Crawler đã parse ngay trong lúc chạy: **không cần gọi `reparse` sau mỗi lần cào**.
Sau khi các worker dừng, chạy lần lượt:

```bash
# 1. Nhập observations riêng của các job vào data/interim theo nguồn
python batch.py merge
# 2. Chuẩn hóa, khử trùng lặp, tạo ID/quan hệ; giữ mọi phòng/chuyến đã có
python normalise.py --no-plan --rooms-per-hotel 0 --flights-per-route 0
# Tuỳ chọn: xuất tất cả taxonomy của mỗi thành phố vào một JSON
python catalog.py cities
# 3. Tách products.jsonl thành 5 file JSON taxonomy
python catalog.py split
# 4. Ghép 5 file taxonomy thành một JSON array products.json
python catalog.py merge
```

| Bước | Đọc từ | Ghi ra |
|---|---|---|
| `batch.py merge` | `data/batches/*/interim/*.jsonl` | `data/interim/<source>.jsonl` |
| `normalise.py ...` | `data/interim/*.jsonl` | `data/products.jsonl`, CSV và báo cáo |
| `catalog.py cities` | `data/products.jsonl` | `data/cities/<thanh-pho>.json` và `_index.json` |
| `catalog.py split` | `data/products.jsonl` | `data/catalog/<taxonomy>.json` |
| `catalog.py merge` | 5 file trong `data/catalog/` | `data/products.json` |

Nếu đã sửa trực tiếp 5 bảng taxonomy và chỉ muốn ghép chúng, chạy riêng `python catalog.py merge`.
Chạy `catalog.py split` sẽ tạo lại cả 5 bảng từ `products.jsonl`; không dùng bước đó sau sửa tay nếu
muốn giữ các thay đổi chỉ có trong bảng taxonomy. `normalise.py` cũng tạo lại catalog từ interim.

### Khi cần parse lại cache

Chỉ dùng khi sửa parser hoặc muốn dựng lại interim từ raw. Lấy đường dẫn job từ lệnh liệt kê bên trên,
thay `JOB_ID` bằng ID thật và chọn đúng source của job:

```bash
python crawl.py --data-dir data/batches/JOB_ID reparse booking-hotels
# Hoặc source tương ứng: agoda-hotels, trip-attractions, trip-flights, booking-flights, vinpearl

# Sau reparse, nhập lại observations và xuất Product theo đúng thứ tự
python batch.py merge
python normalise.py --no-plan --rooms-per-hotel 0 --flights-per-route 0
python catalog.py split
python catalog.py merge
```

Reparse không cào giá mới và không đổi thời điểm quan sát sang hôm nay. Không reparse thư mục `data/`
rồi cho rằng đã đọc raw của mọi batch: raw của từng job vẫn ở thư mục job đó.
Với dữ liệu cào trực tiếp bằng `crawl.py` vào `data/` thay vì batch, bỏ bước `batch.py merge` và bắt đầu
từ `normalise.py`. Nếu dùng root batch khác, import bằng `python batch.py merge --root DUONG_DAN_ROOT`.

Kết quả:

```
data/catalog/hotel.json
data/catalog/flight.json
data/catalog/attraction.json
data/catalog/combo.json
data/catalog/golf.json
data/products.json
```

Mỗi bảng là JSON array chứa Product theo đúng 13 trường. Hotel chứa cả property/room;
flight chứa cả route/flight, nối bằng `attributes.parentProductId`. ID không bị tạo lại khi tách/gộp.
`catalog.py merge` báo lỗi khi cùng ID có nội dung khác hoặc thiếu parent, không âm thầm ghi đè.
Đây là file để import DB, chưa phải migration tạo năm bảng SQL hoặc ba database.

`batch.py merge` chỉ nhập observations vào `data/interim/`, không tự ghi lại catalog. Merge lặp lại
không nhân bản observations giống hệt. Raw giữ ở job gốc, có `rawArchive` truy ngược. Không xóa
`data/batches/` sau import. Reparse từng job bằng `crawl.py --data-dir <job-dir> reparse <source>`, rồi merge lại.
Mặc định `normalise.py` xoá sản phẩm không có giá mà nguồn không cung cấp được (trừ điểm công cộng không bán vé); thêm `--keep-unsellable` nếu cần giữ để làm giàu nội dung, khi đó phải lọc giá/availability trước luồng đặt chỗ.

## Kết quả kiểm tra ngày 19/09/2026

Đã cào live 61 trang tuyến Trip, lưu ở `data/enrichment-20260919/`, nhập vào interim rồi xuất catalog
giữ mọi phòng/chuyến đã thu thập: **3.082 sản phẩm**, gồm 2.195 hotel, 356 flight, 420 attraction,
105 combo và 6 golf. Phần tăng gồm dữ liệu Trip mới và các sản phẩm trước đó bị giới hạn số lượng khi xuất;
không phải 866 sản phẩm đều vừa cào mới. Giữ đủ ID của 2.216 sản phẩm cũ, không trùng ID/sourceRef hoặc thiếu parent.
Có 188 discovery chưa có giá; kiểm tra chi tiết trong `design/audit-enriched.json`.
35 kiểm thử offline đạt, bao gồm chia lô, gộp dữ liệu, ID, ngày thật và parser Booking Flights.
Bản sao catalog trước khi nhập ở `data/backups/20260919-city-enrichment/`.

Các hạng mục thiết kế chưa triển khai: ba database; adapter VinWonders riêng; so sánh đầy đủ điều kiện giá
phòng giữa nguồn; component links cho combo. Audit còn 19 trường hợp giá OTA được logic cũ chọn cao hơn
giá Vinpearl lưu kèm, cần đối chiếu điều kiện trước khi sử dụng làm “giá rẻ nhất”.
