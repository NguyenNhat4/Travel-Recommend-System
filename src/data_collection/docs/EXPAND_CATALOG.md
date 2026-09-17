# Sinh catalog 10.000 sản phẩm theo schema hiện tại

`expand_catalog.py` giữ các giá trị đã có, bổ sung hotel/tour/vé mock và điền các ô null cho bản demo.
Chỉ cần Python >= 3.10, không cần cài thư viện hay treo crawler. Không thay đổi database/schema.

## Cấu trúc Product

Mỗi sản phẩm mới có đúng 13 trường:

```text
productId, name, taxonomy, destination, description, attributes,
unitPrice, currency, available, availableFrom, availableTo, imageUrl, sourceRef
```

`attributes` của **hotel/room có đúng các khóa trong mẫu của bạn**, không thêm khóa nào:

```text
level, brand, hotelName, roomName, roomCode, parentProductId, starRating,
latitude, longitude, maxOccupancy, maxAdult, maxChild, bedrooms, roomSizeM2,
amenities, ratePlans, pricesByDate, familyFriendly, priceDate, images,
url, bookingUrl, descriptionLang, fieldSources, locationSource, locationPrecision
```

- Không có `isSynthetic`, `dataOrigin`, `generatorVersion`, `generationSeed` trong Product.
  Cũng bỏ các khóa bổ sung của bản trước như `priceBasis`, `category`, `venueRef`, `tourType`.
- Khách sạn cấp `property` dùng tập con của các khóa trên, không gắn thuộc tính phòng cho cơ sở.
- Tour và vé đều có `taxonomy: "attraction"`, dùng các khóa đã có trong catalog gốc như
  `tourCode`, `venue`, `durationMinutes`, `audience`, `tags`, `openingHours`.
  Thông tin chi tiết về nhóm khách, bữa ăn, đưa đón của tour nằm trong `description`.
- Mô tả tiếng Việt được sinh từ thuộc tính sản phẩm; phòng có diện tích, số phòng ngủ,
  giường, sức chứa và tiện nghi. `unitPrice` khớp `pricesByDate[priceDate]`.
- Phần mock có `available: true`; hai trường ngày vẫn là chuỗi ISO theo schema, được điền
  khoảng ngày thay cho null theo yêu cầu. Mọi giá trị nguồn không-null, kể cả `available: false`, giữ nguyên.

Giá trị mock dùng các trường nguồn **đã có**: `sourceRef` bắt đầu bằng `synthetic:`,
`fieldSources.unitPrice` và `locationSource` là `mock`. Không thêm cờ riêng.
Toạ độ được sinh quanh tâm điểm đến; `locationPrecision: "exact"` là giá trị fixture theo mẫu,
không thể hiện một vị trí doanh nghiệp đã xác minh ngoài thực tế.
`url`/`bookingUrl` là URL placeholder tại `example.com`, không phải dịch vụ đặt chỗ thật.

## Ảnh ngẫu nhiên từ dữ liệu đã crawl

Mỗi sản phẩm mới có 6 URL ảnh trong `attributes.images`, `imageUrl` bằng ảnh đầu tiên.
Ảnh được lấy nguyên URL từ `imageUrl` và `attributes.images` của các sản phẩm thật trong `--input`.
Sản phẩm có `sourceRef` bắt đầu bằng `synthetic:` không được dùng làm nguồn ảnh.

Ưu tiên ảnh cùng taxonomy và level (phòng dùng ảnh phòng, cơ sở dùng ảnh cơ sở,
tour/vé dùng ảnh attraction). Nếu không có, dùng kho ảnh cùng taxonomy, rồi kho ảnh toàn nguồn.
Các URL được khử trùng lặp và sắp xếp trước khi random theo seed, nên cùng nguồn và seed
cho cùng bộ ảnh, kể cả khi đổi thứ tự dòng đầu vào. Nếu kho ảnh ít hơn 6 URL thì lặp lại ảnh sẵn có.

Script không lấy ảnh từ dịch vụ placeholder và không tải thêm ảnh trên mạng.
Nếu không có ảnh từ nguồn thật thì báo lỗi trước khi ghi output. Mọi URL ảnh mock đều được kiểm tra
thuộc tập URL nguồn. Trình duyệt vẫn cần mạng để hiển thị ảnh từ URL crawl được;
script không kiểm tra lại tình trạng truy cập của các URL đó.

## Điền null cho bản demo

Mặc định script điền null trước khi xuất file, không thêm trường vào Product hoặc attributes.
Chỉ các giá trị đang null được thay thế; không đổi ID, giá đã có, ảnh đã có hay trạng thái availability.
File catalog đã crawl dùng làm input không bị ghi đè.

| Trường | Quy tắc |
|---|---|
| `unitPrice` | Attraction có `ticketed=false`: 0 VND (quy ước không thu tiền vé trong demo). Các loại khác: ưu tiên giá ngày/giá gốc có sẵn; rồi trung vị giá cùng loại/điểm đến, trung vị cùng loại hoặc giá demo mặc định |
| `imageUrl` | Dùng ảnh gallery đã crawl nếu có; nếu thiếu thì lấy ảnh cùng điểm đến từ catalog thật. Tuyến bay và chuyến bay con dùng cùng ảnh đại diện điểm đến |
| `availableFrom` | Ngày sớm nhất trong `priceDate`, `pricesByDate`, `datesSeen`; không có thì dùng `--start-date`. Không vượt ngày kết thúc đã có |
| `availableTo` | 180 ngày sau ngày bắt đầu, kéo dài nếu cần để bao phủ ngày giá đã biết. Ngày kết thúc đã có giữ nguyên |

Với catalog 10.000 sản phẩm hiện tại: điền 140 giá (139 điểm tham quan về 0 VND; Sea Links Golf
về 1.700.000 VND theo trung vị 5 sản phẩm golf có giá), 244 ảnh vé máy bay và 9.459 cặp ngày.
Đây là giá trị phục vụ demo, không phải thông tin giá/ngày bán đã xác minh từ nhà cung cấp.
Đặc biệt, `0 VND` không xác nhận mọi hoạt động tại điểm đến đều miễn phí.

`report.json` có mục `nullFill`: số ô đã điền theo trường, các productId/trường bị tác động,
quy tắc và số null còn lại. Phần này là nguồn tham chiếu cho giá trị điền; nhãn nguồn cũ trong
`attributes.fieldSources` được giữ nguyên. Không thêm flags vào Product.
Nếu dữ liệu tương lai có null ở trường chưa có quy tắc, script báo lỗi trước khi ghi thay vì đoán kiểu dữ liệu.

## Chạy với catalog đang có

```bash
cd /home/dangkhoi/code/Travel-Recommendation-Product/src/data_collection
python3 expand_catalog.py --input /home/dangkhoi/code/vsf/data-collection/data/products.jsonl --target-total 10000 --seed 42 --start-date 2026-10-15 --output-dir data/recsys
```

Catalog nguồn có 2.216 sản phẩm; lệnh trên giữ tất cả sản phẩm và giá trị không-null, điền null và thêm 7.784 sản phẩm.
Đường dẫn `vsf` chỉ là vị trí dữ liệu hiện tại, không hardcode trong script.
Muốn 20.000, đổi `--target-total 20000`. Ngày mặc định cố định `2026-10-15` để giá theo ngày
không tự đổi giữa các lần chạy; đổi `--start-date` khi cần thử ngày khác.

Muốn chỉ sinh mock, vẫn cần chỉ định catalog thật làm kho ảnh (không gộp sản phẩm của kho này):

```bash
python3 expand_catalog.py --synthetic-only --image-source /home/dangkhoi/code/vsf/data-collection/data/products.jsonl --target-total 10000 --output-dir data/mock-only
```

Giới hạn điểm đến của phần mới bằng `--destinations 'Phú Quốc,Nha Trang,Đà Nẵng,Đà Lạt'`.
Mặc định sinh trên 15 điểm đến. Mỗi 25 sản phẩm mới gồm 3 cơ sở lưu trú, 12 hạng phòng,
5 tour và 5 vé/hoạt động. Khối cuối được cắt vừa đủ target.
**10.000 Product bao gồm cơ sở và hạng phòng, không phải 10.000 khách sạn riêng biệt.**

## Đầu ra và chạy lại

| File | Nội dung |
|---|---|
| `data/recsys/products.jsonl` | Catalog đầy đủ |
| `data/recsys/synthetic-products.jsonl` | Chỉ phần mock, cùng schema Product |
| `data/recsys/report.json` | Cấu hình sinh, thống kê, SHA-256, kết quả kiểm tra và nhật ký điền null; nằm ngoài Product |

Cùng input, kho ảnh, seed, ngày và điểm đến cho cùng kết quả. ID phòng/khách sạn giữ nguyên so với
bản generator trước; phần điền null giữ nguyên các trường đã có giá trị.
**Để thay bản cũ, chạy lệnh trên với catalog thật ban đầu**, không lấy output cũ làm input.

Sau khi đã tạo bằng bản mới, có thể dùng output mới làm input để tăng số lượng; cần giữ
cùng cấu hình/kho ảnh và chọn output-dir khác. Có thể bổ sung kho ảnh qua `--image-source PATH`
(lặp cờ nếu có nhiều file). Nếu chỉ có file mock làm input, cần dùng cờ này để cấp lại kho ảnh thật.
Không ghi đè file nguồn. Bản ghi trùng hoàn toàn
được gộp; xung đột ID/nội dung sẽ báo lỗi. Target thấp hơn số lượng đầu vào không xoá dữ liệu.
Input có `parentProductId` phải kèm sản phẩm cha tương ứng.

Không chạy nhiều tiến trình cùng ghi một output-dir. Mỗi file được thay thế atomically;
report ghi cuối cùng chứa checksum để nhận biết file hoàn chỉnh.

## Nạp vào CDP local

Sau khi database/migrations đã sẵn sàng theo `cdp/README.md`, chạy từ `src/data_collection`:

```bash
python -m cdp.load_products --file data/recsys/products.jsonl
python -m cdp.check
```

Loader hiện tại nạp trực tiếp được, không cần migration. Upsert theo ID sẽ cập nhật toàn bộ
attributes của sản phẩm đã có. Loader không xoá sản phẩm dư đã được nạp từ seed/bộ dữ liệu khác.

## Kiểm thử

```bash
python3 -m unittest discover -s tests -p 'test_expand_catalog.py' -v
```

Kiểm tra 10.000 dòng, đúng bộ khóa mẫu cho phòng, không có flags bổ sung, mô tả/ảnh đầy đủ,
mọi ảnh mock có trong catalog thật, ưu tiên đúng loại ảnh, kho ảnh ít/rỗng và chạy lại ổn định,
giá/sức chứa nhất quán, parentProductId hợp lệ, điền null hợp lý và chỉ đổi ô null,
giữ nguyên file input, chạy lại/tăng target giữ ID,
checksum và không ghi đè nguồn khi input lỗi.
