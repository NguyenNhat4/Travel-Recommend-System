# Thống kê catalog

Tạo lúc 2026-09-23 · **11387 sản phẩm**

## Đối chiếu handbook §3

| Mục tiêu | Thực tế | |
|---|---|---|
| 2.000–5.000 sản phẩm | 11387 | ⚠️ |
| 10–15 điểm đến (≥ 20 sản phẩm mỗi nơi) | 27 | ⚠️ |
| Đủ hotel, flight, attraction, combo | attraction, combo, flight, golf, hotel | ✅ |
| Mô tả được nhận diện là tiếng Việt | 11351 (99.7%) | ✅ |
| Có giá | 11087 (97.4%) | ✅ |
| Được đánh dấu available trong dữ liệu | 11386 (100.0%) | |
| Có toạ độ | 11387 (100.0%) | |
| Sản phẩm trùng giữa các nguồn đã gộp | 220 | |

Nhãn ngôn ngữ được ước lượng từ tỷ lệ ký tự có dấu trong mô tả; không xác nhận tên hoặc toàn bộ nội dung đã là tiếng Việt. Cần đọc tay các mẫu bên dưới.
Cờ available được suy ra từ dữ liệu nguồn và giá tại thời điểm crawl; chưa xác minh đặt chỗ hiện tại. Các trường còn thiếu được liệt kê trong `quality_review.csv`.
Trong 300 sản phẩm không có giá, 300 là điểm tham quan trip.com không hiện giá (chưa rõ có bán vé hay không, `unitPrice = null`, không phải miễn phí); phần còn lại mới là thiếu giá cần đối chiếu nguồn.

## Điểm đến × loại sản phẩm

| Điểm đến | hotel | flight | attraction | combo | golf | tổng |
|---|---|---|---|---|---|---|
| Đà Nẵng | 854 | 65 | 10 | 6 | 0 | 935 |
| Nha Trang | 687 | 48 | 63 | 19 | 1 | 818 |
| Phú Quốc | 607 | 68 | 67 | 26 | 1 | 769 |
| TP. Hồ Chí Minh | 613 | 100 | 25 | 4 | 1 | 743 |
| Hà Nội | 529 | 94 | 83 | 14 | 0 | 720 |
| Hội An | 653 | 0 | 24 | 8 | 1 | 686 |
| Phan Thiết | 651 | 0 | 16 | 0 | 1 | 668 |
| Đà Lạt | 585 | 44 | 18 | 6 | 0 | 653 |
| Huế | 603 | 21 | 16 | 6 | 0 | 646 |
| Quy Nhơn | 549 | 15 | 14 | 6 | 0 | 584 |
| Hải Phòng | 472 | 23 | 25 | 8 | 1 | 529 |
| Sa Pa | 507 | 0 | 17 | 0 | 0 | 524 |
| Hạ Long | 453 | 0 | 19 | 6 | 0 | 478 |
| Côn Đảo | 325 | 24 | 0 | 0 | 0 | 349 |
| Cần Thơ | 260 | 19 | 15 | 6 | 0 | 300 |
| Ninh Bình | 272 | 0 | 15 | 0 | 0 | 287 |
| Nghệ An | 195 | 30 | 27 | 11 | 0 | 263 |
| Pleiku | 175 | 0 | 5 | 0 | 0 | 180 |
| Tuy Hòa | 168 | 0 | 10 | 0 | 0 | 178 |
| Buôn Ma Thuột | 151 | 16 | 7 | 0 | 0 | 174 |
| Rạch Giá | 155 | 0 | 17 | 0 | 0 | 172 |
| Cát Bà | 148 | 0 | 1 | 0 | 0 | 149 |
| Điện Biên | 118 | 0 | 17 | 0 | 0 | 135 |
| Quảng Bình | 102 | 2 | 17 | 0 | 0 | 121 |
| Hà Tĩnh | 110 | 0 | 3 | 7 | 0 | 120 |
| Thanh Hóa | 46 | 10 | 0 | 0 | 0 | 56 |
| Phong Nha | 52 | 0 | 0 | 0 | 0 | 52 |
| Châu Đốc | 0 | 0 | 18 | 0 | 0 | 18 |
| Cao Bằng | 0 | 0 | 18 | 0 | 0 | 18 |
| Kon Tum | 0 | 0 | 16 | 0 | 0 | 16 |
| Quảng Trị | 0 | 0 | 15 | 0 | 0 | 15 |
| Bắc Ninh | 7 | 0 | 0 | 0 | 0 | 7 |
| Tây Ninh | 7 | 0 | 0 | 0 | 0 | 7 |
| Sầm Sơn | 5 | 0 | 0 | 0 | 0 | 5 |
| Mỹ Tho | 0 | 0 | 5 | 0 | 0 | 5 |
| Biên Hòa | 0 | 0 | 3 | 0 | 0 | 3 |
| Bến Tre | 0 | 0 | 2 | 0 | 0 | 2 |
| Mai Châu | 0 | 0 | 2 | 0 | 0 | 2 |

## Theo nguồn

- booking: 9470
- trip: 991
- agoda: 498
- vinpearl: 428

## Theo loại / cấp

- attraction/-: 610
- combo/-: 133
- flight/flight: 466
- flight/route: 113
- golf/-: 6
- hotel/property: 2321
- hotel/room: 7738

Độ dài mô tả trung vị: 925 ký tự

## Bị loại

- không có giá và nguồn không cung cấp được (không đặt được): 271
- khách sạn trùng giữa các nguồn (đã gộp): 216
- cảnh báo vị trí: toạ độ xa tâm điểm đến (đã xoá, xem data/excluded_location.csv): 145
- biến thể giá thành viên Vinpearl (đã gộp, giá từng hạng giữ trong memberPrices): 53
- đã soát tay và loại (collectors/excluded_products.csv): 10
- thuộc sản phẩm cha đã bị loại (đã xoá, xem data/excluded_location.csv): 10
- thiếu toạ độ (đã xoá, xem data/excluded_location.csv): 6
- điểm tham quan trip.com trùng vé Vinpearl (đã gộp): 4
- trùng sourceRef: 4
- không phải điểm du lịch theo quy tắc: cơ sở y tế: 2
- không phải điểm du lịch theo quy tắc: quán ăn / cà phê: 2
- không phải điểm du lịch theo quy tắc: hãng taxi / cho thuê xe: 1
- giá phòng bất thường: 27× giá trung vị các hạng phòng cùng khách sạn (369.000 ₫) (đã xoá, xem data/excluded_location.csv): 1
- giá phòng bất thường: 20× giá trung vị các hạng phòng cùng khách sạn (913.500 ₫) (đã xoá, xem data/excluded_location.csv): 1
- giá phòng bất thường: 101× giá trung vị các hạng phòng cùng khách sạn (1.306.800 ₫) (đã xoá, xem data/excluded_location.csv): 1

## Vị trí (toạ độ)

| Loại / cấp | Sản phẩm | Có toạ độ | |
|---|---|---|---|
| attraction/- | 610 | 610 | 100.0% |
| combo/- | 133 | 133 | 100.0% |
| flight/flight | 466 | 466 | 100.0% |
| flight/route | 113 | 113 | 100.0% |
| golf/- | 6 | 6 | 100.0% |
| hotel/property | 2321 | 2321 | 100.0% |
| hotel/room | 7738 | 7738 | 100.0% |

Nguồn toạ độ: booking.com 9466, ourairports 579, trip.com 568, agoda.com 496, vinpearl 95, destination_center 79, manual 52, osm 52

Độ chính xác: exact 10432, airport 579, venue 297, destination 79 (exact = vị trí riêng của sản phẩm; venue = khu vui chơi/sân golf dùng vé; poi = điểm tham quan trip.com; airport = sân bay đến)

- vé có toạ độ địa điểm: 377
- khách sạn: toạ độ xa tâm điểm đến: 32
- điểm đến sửa theo bằng chứng (destination_overrides.csv): 14
- khách sạn: trùng toạ độ khách sạn khác: 4
- toạ độ sửa tay (location_overrides.csv): 3
- vé đổi điểm đến theo địa điểm: 3

Cảnh báo toạ độ (1 sản phẩm, không tính hạng phòng):

- Meliá Vinpearl Phu Ly · Ninh Bình · cách tâm Ninh Bình 32 km

Bản đồ: 2806 ghim trong `map/` (mymaps-khach-san.csv, mymaps-khach-san-2.csv, mymaps-vui-choi.csv, mymaps-san-bay.csv, places.geojson). Cần kiểm tra tay: 19 dòng trong `map/can-kiem-tra.csv`.

## Mẫu để đọc tay (kiểm tra chất lượng tên + mô tả)

- **Hòn Tằm Resort** · hotel · Nha Trang · 2267636 VND

  Với vẻ đẹp của thiên nhiên kết hợp cùng kiến trúc bungalow và villa sang trọng, Hòn Tằm Resort Nha Trang mang đến cho du khách một kỳ nghỉ đẳng cấp, riêng tư và ấn tượng khó quên. Khu nghỉ dưỡng được bao phủ bởi cảnh quan xanh mát, yên ả của rừng và biển giúp thư giãn cả cơ thể l
- **Seaside Boutique Resort Quy Nhon** · hotel · Quy Nhơn · 982773 VND

  Vị trí bên bờ biển tuyệt vời: Seaside Boutique Resort Quy Nhon tại Quy Nhon cung cấp khu vực bãi biển riêng và lối đi thẳng ra bãi biển. Khách có thể thưởng thức tầm nhìn tuyệt đẹp ra biển và hồ bơi với cảnh quan đẹp.  Chỗ nghỉ thoải mái: Các phòng có điều hòa không khí, phòng tắ
- **Catba Buffalo Hostel** · hotel · Cát Bà · 500000 VND

  Các Chỗ Nghỉ Thoải Mái: Catba Buffalo Hostel tại Cát Bà cung cấp các phòng có điều hòa không khí với phòng tắm riêng, ban công và WiFi miễn phí. Mỗi phòng đều có máy sấy tóc, vòi sen và TV.  Các Tiện Nghi Giải Trí: Khách có thể thư giãn trong khu vườn hoặc quầy bar, tận hưởng hồ
- **Hanoi View Hotel** · hotel · Hà Nội · 840000 VND

  Chỗ Nghỉ Thoải Mái: Hanoi View Legend Hotel tại Hà Nội cung cấp các phòng gia đình với điều hòa không khí, phòng tắm riêng và tầm nhìn ra thành phố. Mỗi phòng đều có bàn làm việc, minibar và WiFi miễn phí.  Ẩm Thực và Giải Trí: Khách sạn có nhà hàng thân thiện với gia đình phục v
- **Chill Hotel Ha Bong** · hotel · Đà Nẵng · 399168 VND

  Chỗ Nghỉ Thoải Mái: Chill Hotel Ha Bong tại Đà Nẵng cung cấp các phòng gia đình với tầm nhìn ra biển hoặc thành phố. Mỗi phòng đều có điều hòa không khí, phòng tắm riêng với vòi sen đi bộ và WiFi miễn phí.  Tiện Nghi Thuận Tiện: Khách có thể tận hưởng WiFi miễn phí, dịch vụ nhận
- **Spring Home 2** · hotel · Cần Thơ · 346500 VND

  Chỗ Nghỉ Thoải Mái: Spring Home tại Cần Thơ cung cấp chỗ nghỉ theo phong cách căn hộ dịch vụ với điều hòa không khí, phòng tắm riêng và ban công. Mỗi đơn vị đều có bàn ăn, tủ lạnh, bàn làm việc và cách âm để đảm bảo sự thoải mái cho khách lưu trú.  Tiện Nghi Cần Thiết: Khách có t
- **The Apec Mandala Ocean View Mui Ne - Condotel** · hotel · Phan Thiết · 474083 VND

  Chỗ Nghỉ Thanh Lịch: The Apec Mandala Ocean View Mui Ne tại Mũi Né mang đến trải nghiệm khách sạn 5 sao với tầm nhìn ra biển, điều hòa không khí và WiFi miễn phí. Khách có thể tận hưởng quầy bar, hồ bơi ngoài trời và phòng tập thể dục.  Tiện Nghi Thoải Mái: Chỗ nghỉ có phòng chờ,
- **Aries House Sapa - 2 ROOM** · hotel · Sa Pa · 1080000 VND

  Aries House Sapa - 2 ROOM là chỗ nghỉ có khu vườn và sân hiên, nằm ở Sa Pa, cách Hồ Sa Pa 19 phút đi bộ, Sa Pa Bus Station 1.4 km và Sa Pa Stone Church 12 phút đi bộ. Chỗ nghỉ điều hòa này cách Trạm cáp treo Fansipan 2.5 km, khách có thể sử dụng WiFi miễn phí và chỗ đậu xe riêng
- **Siren Flamingo Hải Tiến** · hotel · Thanh Hóa · 1980000 VND

  Siren Flamingo Hải Tiến có khu vườn, khu vực bãi biển riêng, sân hiên và quầy bar ở Gò Ba Quần. Chỗ nghỉ này cung cấp dịch vụ phòng, quầy lễ tân 24 giờ và phòng giữ hành lý cho khách.  Các căn đi kèm điều hòa, TV màn hình phẳng có truyền hình cáp, tủ lạnh, ấm đun nước, vòi xịt/ch
- **Caravelle Saigon Hotel** · hotel · TP. Hồ Chí Minh · 5854207 VND

  Caravelle Saigon Hotel tại Hồ Chí Minh: Tất cả những gì bạn cần biếtCaravelle Saigon Hotel mang đến điểm dừng chân nổi bật giữa nhịp sống sôi động của Hồ Chí Minh, phù hợp cho cả chuyến công tác hiệu quả lẫn kỳ nghỉ khám phá thành phố đầy cảm hứng. Được xây dựng từ năm 1959 và cả
- **Oakwood Hạ Long (Oakwood Ha Long)** · hotel · Hạ Long · 4084656 VND

  Oakwood Hạ Long tại Hạ Long: Tất cả những gì bạn cần biếtOakwood Hạ Long tại Hạ Long là điểm dừng chân đáng cân nhắc cho cả chuyến công tác hiệu quả lẫn kỳ nghỉ thư thái bên cảnh quan nổi tiếng của Việt Nam. Với quy mô 86 phòng, khách sạn mang đến không gian lưu trú phù hợp cho n
- **[Times City Hà Nội] - Vé vào cửa Khu vui chơi VinKE | TẶNG Voucher Ẩm thực** · attraction · Hà Nội · 240000 VND

  [Times City Hà Nội] - Vé vào cửa Khu vui chơi VinKE | TẶNG Voucher Ẩm thực  Vé vào cửa trực tiếp khu vui chơi dành cho trẻ em VinKE sử dụng trong ngày dành cho 01 người Phụ thu 30.000đ/vé trong trường hợp khách hàng cao từ 140cm nhưng mua vé dành cho khách hàng có chiều cao từ 80
- **[Combo 01 ngày] - Vinpearl Safari + VinWonders Phú Quốc** · combo · Phú Quốc · 1500000 VND

  [Combo 01 ngày] - Vinpearl Safari + VinWonders Phú Quốc  - Combo vé tiêu chuẩn vào cửa trực tiếp VinWonders và Vinpearl Safari Phú Quốc trong 01 ngày  Bao gồm - Combo vé tiêu chuẩn vào cửa trực tiếp VinWonders và Vinpearl Safari Phú Quốc
- **Làng chài Mũi Né** · attraction · Phan Thiết · None VND

  Làng chài Mũi Né. Loại hình: Cảnh đêm. Địa chỉ: Huỳnh Thúc Kháng, Mũi Né, Bình Thuận, Việt Nam. Giờ mở cửa: Mở cửa cả ngày. Thời gian tham quan đề xuất: 30–60 phút
- **Hồ Thang Hen** · attraction · Cao Bằng · None VND

  Hồ Thang Hen. Loại hình: Phong cảnh thiên nhiên. Địa chỉ: Trà Lĩnh, Cao Bằng, Việt Nam. Giờ mở cửa: Vui lòng liên hệ với điểm tham quan để xác nhận giờ mở cửa cụ thể
