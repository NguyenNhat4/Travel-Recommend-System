# Rà soát hợp đồng theo catalog thực và phương án mock 30 đêm

Ngày: **17/09/2026**. Phạm vi: các tài liệu được cung cấp trong `Downloads`, catalog hiện tại và thiết kế ba service. Đây là **kết quả review và đề xuất sửa hợp đồng**, không phải xác nhận code đã triển khai hay các team đã nghiệm thu.

**Kết luận:** ranh giới Web → Backend → CDP/Insider phù hợp. Bộ hợp đồng **chưa đồng bộ để triển khai booking theo từng đêm**: thiếu lịch khả dụng, còn nhầm cơ sở với hạng phòng, và nhiều đoạn Backend/Frontend cũ mâu thuẫn với baseline/Agent mới.

Xem [bản vẽ database và luồng chi tiết](thiet-ke-schema-3-service-chi-tiet.md). Các hướng dẫn giao việc nằm trong brief UX được xem là nội dung tham khảo, không phải yêu cầu chạy lại nghiên cứu UX.

## 1. Quyết định từ cuộc trao đổi này

| Nội dung | Quy tắc dùng trong thiết kế |
|---|---|
| Giá phòng | Một giá VND cho **mỗi hạng phòng / mỗi đêm**, dùng chung trong cửa sổ 30 đêm; không nhân bản giá thành 30 dòng |
| Khả dụng | Mỗi hạng phòng có trạng thái theo từng đêm. Đặt một đêm thì đêm đó hết khả dụng; đặt ba đêm thì cả ba đêm hết khả dụng |
| Cửa sổ | Trượt theo ngày hiện tại tại `Asia/Ho_Chi_Minh`, thêm một đêm mới mỗi ngày |
| Khoảng lưu trú | `[checkIn, checkOut)`: tính đêm nhận phòng, không tính ngày trả phòng |
| Tồn mock | Diễn giải thiết kế: mỗi hạng phòng đại diện **một đơn vị tồn mỗi đêm**, vì đặt một lần làm đêm đó hết khả dụng. `quantity=1` cho phòng. Nếu muốn nhiều phòng cùng hạng, phải mở rộng sang số lượng tồn |
| Đặt thành công | Giữ đủ dòng lịch; thay `available=true` thành `false` và liên kết dòng booking. Không xóa ngày đã đặt |
| Tài khoản demo | Bỏ bảng `demo_accounts` theo yêu cầu. Nếu cần tài khoản mẫu thì seed trực tiếp `users`; đề xuất bỏ endpoint/UI liệt kê persona tương ứng |

Ngày 17/09/2026: 30 đêm là **17/09–16/10**, ngày trả phòng muộn nhất **17/10**. “30 ngày tiếp theo” ở đây bao gồm hôm nay, không phải hôm nay cộng thêm 30 ngày thành 31 đêm.

## 2. Dữ liệu đã đối chiếu

Đọc toàn bộ [products.jsonl](../../src/data_collection/data/recsys/products.jsonl), không suy rộng từ sample 50 dòng. [Bằng chứng thống kê](evidence/catalog-audit-2026-09-17.json) ghi checksum và ID ví dụ.

| Loại thực tế | Số dòng | Bảng chuyên biệt đề xuất |
|---|---:|---|
| Khách sạn / cơ sở lưu trú `hotel/property` | 1.494 | `hotel_properties` |
| Hạng phòng `hotel/room` | 4.646 | `hotel_rooms` |
| Tuyến bay `flight/route` | 60 | `flight_routes` |
| Chuyến bay `flight/flight` | 184 | `flight_services` |
| Vé, tour, điểm tham quan `attraction` | 3.517 | `attraction_products` |
| Gói combo `combo` | 93 | `combo_packages` |
| Voucher / địa điểm golf `golf` | 6 | `golf_products` |
| **Tổng** | **10.000** | **7 cấu trúc sản phẩm** |

- 10.000 `productId`, 10.000 `sourceRef` duy nhất; mỗi dòng có đúng 13 trường.
- 4.830 quan hệ cha–con, không thiếu cha: 4.646 phòng → khách sạn, 184 chuyến → tuyến.
- 243 cơ sở chưa có hạng phòng trong file: được hiển thị nhưng chưa có phòng để đặt theo thiết kế mới.
- 7.784 dòng có `sourceRef` bắt đầu `synthetic:`; 2.216 dòng còn lại đến từ catalog nguồn, **một số trường đã được điền bằng quy tắc demo**. Không gọi cả 2.216 dòng là dữ liệu nguyên bản hoàn toàn.
- Có 9.859 `available=true`, 141 `false`; không có khóa availability/stock theo ngày trong `attributes`.
- Có 2.224 dòng chứa thuộc tính boolean `false`, 26 dòng có hạng sao thập phân.
- 139 attraction có `ticketed=false`; Sea Links Golf cũng có `ticketed=false` dù được điền giá 1.700.000 VND. Có giá không đồng nghĩa được đặt.
- Không còn null ở giá/ngày/ảnh trong file này do bước điền mock. API vẫn cần hỗ trợ nullable cho dữ liệu khác.
- Lịch ban đầu cho toàn bộ phòng: **4.646 × 30 = 139.380 dòng**. Đây là lịch cần sinh, chưa có trong file hiện tại.

`SCHEMA.md` còn mô tả 2.216 dòng; baseline 1.1 mô tả sample 50 dòng. Cả hai không phải thống kê của catalog 10.000 dòng hiện tại. Xem [quy tắc mở rộng catalog](data-collection/expand-catalog.md).

## 3. Phiên bản tài liệu và code không trùng nhau

| Nguồn | Kết quả kiểm tra |
|---|---|
| Nhánh đang mở | `data`; có thay đổi chưa commit của người dùng |
| OpenAPI tại working tree | `src/shared/contracts/openapi.yaml`: **0.1.0**, `paths: {}`; chưa phải hợp đồng triển khai đầy đủ |
| Ref local `origin/data_contract` | Commit **`0f630a2`**; OpenAPI Backend **1.3.0**, CDP **0.2.0**; đọc bằng `git show`, không fetch, không khẳng định đây là bản mới nhất trên server |
| Backend đính kèm | Header phiên bản 1.0 + ghi chú MVP 1.2.0; thân tài liệu còn nhiều quy tắc cũ |
| Frontend đính kèm | Còn gọi shape Agent là đề xuất và còn bảng đối chiếu Agent cũ |
| Agent đính kèm | 1.2.0; đã có nullable, `UNKNOWN`, bốn trạng thái response |
| Thiết kế ba service cũ | Dựa trên `origin/data_contract`, không phản ánh đầy đủ code đang ở nhánh `data` |

Không thể nói “OpenAPI thắng” mà để mỗi team dùng một bản OpenAPI khác nhau. Cần chọn cùng commit hợp đồng khi tích hợp. Các thay đổi lịch phòng dưới đây là **đề xuất tiếp theo**, chưa có trong cả 0.1.0 lẫn 1.3.0 đã kiểm tra.

## 4. Những điểm đúng nên giữ

1. Web chỉ gọi Backend; không nắm token hoặc URL nội bộ CDP.
2. Backend sở hữu catalog, tài khoản, giỏ, đơn; CDP sở hữu event/profile; Insider giữ bản sao phục vụ kích hoạt kênh.
3. Không FK/join xuyên database. Dùng ID ổn định và các client API.
4. `product_view`, `search`, `add_to_cart` ghi nền; `purchase` là sự kiện nghiệp vụ có ID chống trùng.
5. Agent truy xuất sản phẩm qua API; tên, ID, giá phải có căn cứ; không tự tạo booking.
6. Khi CDP không đọc được, Recommendation có fallback; khi thiếu căn cứ tính tổng, Agent trả `null` + cảnh báo.
7. Taxonomy công khai vẫn là `hotel`, `flight`, `attraction`, `combo`, `golf`; database có thể tách chi tiết hơn mà không tạo thêm taxonomy.

## 5. Các điều khoản cần sửa

**P1**: cần sửa trước tích hợp luồng liên quan. **P2**: cần hoàn thiện để vận hành/diễn giải đúng. Đây là mức ưu tiên review, không phải lỗi đã quan sát trên server đang chạy.

| Mã | Mức | Bằng chứng | Vấn đề / sửa cụ thể |
|---|---|---|---|
| R01 | P1 | Backend §2.2, §5.3; Agent §2.2; baseline phần quyết định | `available` vừa bị gọi là còn chỗ, vừa là snapshot crawl. Giữ trường cũ cho catalog; thêm API lịch phòng có availability theo đêm và kết quả cho cả kỳ lưu trú. Checkout đọc lịch này |
| R02 | P1 | Backend §2.6, §7.1; baseline “Đơn vị” | Không được suy đơn vị của mọi sản phẩm từ taxonomy. **Riêng phòng mock** đã có quyết định nghiệp vụ nên dùng `PER_NIGHT`, số lượng là phòng; loại khác cần mapping có căn cứ hoặc `UNKNOWN` |
| R03 | P1 | Backend §2.5 so với catalog và `schemas/catalog.yaml` tại `0f630a2` | Bỏ quy tắc “attributes chỉ true; sao là integer”. Giữ false, số thập phân, mảng, object, `level`, `parentProductId`, provenance |
| R04 | P1 | Backend §7.1, §7.2; thiết kế cũ §3.5 | Chỉ kiểm `usingDate` trong khoảng là thiếu. Phải kiểm **đủ N đêm**, cùng một room, không có đêm thiếu/hết khả dụng; ngày trả phòng không bị kiểm như đêm ở |
| R05 | P1 | Backend §7.1 “quantity ≥ 1”; lựa chọn mock hiện tại | Một lần đặt làm đêm hết khả dụng → phòng mock chỉ nhận `quantity=1`. Muốn `quantity>1` phải có `remainingRooms`, không thể suy sức chứa từ boolean |
| R06 | P1 | Backend §7.1 quy tắc 6; UNIQUE giỏ trong thiết kế cũ | Cùng room/ngày nhưng khác số đêm bị gộp sai. Với tồn 1: dùng UNIQUE `(cart_id, room_product_id)` cho dòng phòng; POST lặp cùng kỳ là idempotent, đổi kỳ bằng PATCH, không cộng số lượng |
| R07 | P1 | Catalog có 7 cấu trúc; Backend §7.1 chỉ cần ID + available | `hotel/property` và `flight/route` là cha, không tự thành hàng bán. Phòng phải đặt ID `hotel/room`; chuyến chọn ID `flight/flight`. `ticketed=false` không có CTA mua, kể cả giá 0 hoặc giá điền mock |
| R08 | P1 | Backend §7.4; CDP §5, §7 | Chống trùng event theo `bookingItemId` **không** chống trùng checkout sau timeout nếu mỗi lần sinh ID mới. Thêm `Idempotency-Key` cho checkout, lưu hash request và kết quả; không tạo booking mới cho cùng key |
| R09 | P1 | CDP §5 | Ghi CDP trước commit là bù trừ, không phải transaction phân tán. Timeout có thể để lại purchase mồ côi. Với tồn phòng cần rollback cả lịch. Giữ cách cũ cho MVP nhưng ghi rõ giới hạn; thêm journal để khôi phục, không khẳng định exactly-once xuyên service |
| R10 | P1 | Frontend §9.3, §9.5, §10; Agent §4–5; baseline | `bookableCount = số available=true` sai cho cha/điểm không bán/đêm hết chỗ. Không cộng giá khách sạn cha và phòng con. Render tổng nullable, `UNKNOWN`, hydrate recommendation; bỏ bảng yêu cầu Agent sửa những thứ Agent đã sửa |
| R11 | P1 | Backend §10 D12; `datesSeen` của chuyến bay | Khoảng min–max ngày bay không chứng minh bay mỗi ngày. 184 chuyến có danh sách ngày rời rạc; tách `flight_observed_dates`. Mock 30 đêm do người dùng chọn **chỉ áp dụng phòng**, không tự áp cho chuyến/tour/golf |
| R12 | P2 | Backend §2.2; baseline; OpenAPI 1.3.0 | File hiện tại đủ giá/ngày không làm nullable trong API trở nên sai. Sửa bảng required/optional cũ theo schema, không ép `null` thành 0 hoặc ngày tùy ý |
| R13 | P2 | Backend §7.3; thiết kế cũ §3.6 | Đọc lại đơn từ catalog sống sẽ đổi tên/giá sau reseed. Lưu snapshot `name`, `taxonomy`, `destination`, `imageUrl`, đơn vị và giá chốt; giữ FK tới ID để truy vết |
| R14 | P2 | CDP §6–7; Backend §8.5 | Timeout CDP 2 giây không bảo vệ được mục tiêu Recommendation 300 ms khi CDP chậm. Đây là khoảng trống ngân sách, không phải chứng cứ vi phạm p95 thực tế. Tách timeout đọc lịch sử/ghi purchase và đo end-to-end |
| R15 | P2 | Thiết kế cũ §8 Q1–Q3 | Thiếu API thống kê popular và liệt kê khách. Demo có thể dùng snapshot seed + danh sách persona; tổng quát cần endpoint/job rõ ràng. Không join sang DB CDP để lấp thiếu hụt |
| R16 | P2 | CDP §1.6; handbook §3; thiết kế cũ §6 | Chưa có hợp đồng Insider riêng. Chốt upsert/identity/profile/export, mapping opt-in, TTL, giới hạn request; đây không phải điều kiện để hoàn thành booking phòng |
| R17 | P2 | Thiết kế cũ §5.4, §7 | Chỉ soft-delete theo “không có trong file” khi đó là snapshot đầy đủ của phạm vi import. Nạp một sample/delta không được xóa catalog còn lại; không tự viết lại migration đã áp dụng |
| R18 | P1 | Yêu cầu mới của người dùng; Backend §3.4, Frontend phần chọn tài khoản mẫu | Bỏ `demo_accounts` trong thiết kế; loại phụ thuộc model/seed/API/UI khi triển khai. Tài khoản mẫu vẫn là row `users` thông thường |

## 6. Sửa theo từng tài liệu

| Tài liệu | Phần giữ | Phần cần cập nhật |
|---|---|---|
| `hop-dong-tich-hop-backend.md` | Auth, ID, event ownership, error envelope | §2.2/2.5/2.6; thêm lịch phòng; §7 giỏ/checkout/idempotency/khóa đêm/snapshot; sửa D12 |
| `hop-dong-tich-hop-frontend.md` | Route, tracing, cấu trúc màn hình | Chọn hạng phòng + check-in/out + lịch đêm; khóa CTA theo kết quả kiểm kỳ ở; quantity phòng = 1; bỏ công thức suy taxonomy và shape Agent lỗi thời |
| `hop-dong-tich-hop-itinerary-assistant.md` | Grounding, 4 trạng thái, nullable tổng | Stay phải là room ID; có ngày thì hậu kiểm toàn kỳ qua lịch phòng; chưa có ngày thì không khẳng định đặt được; phòng mock có thể tính tổng do đơn vị đã rõ |
| `hop-dong-tich-hop-cdp.md` | Event store riêng; TTL không áp CDP; tracing | Phân biệt idempotency checkout và event; bù trừ gồm rollback lịch phòng; dùng tiền nguyên; tùy chọn thêm nights vào event bằng thay đổi schema rõ ràng |
| `contract-baseline-v1.1.md` | Giữ nguyên dữ liệu, chống bịa, nullable, không đếm trùng cha–con | Ghi rằng phần **mock phòng** đã có câu trả lời: giá cố định, 30 đêm trượt, tồn boolean. Không suy rằng đơn vị/checkout các loại khác cũng đã được chốt |
| `product.md` | Vòng phản hồi booking → recommendation và giải thích `because` | §4.3.3 hộp đặt theo loại cụ thể; §4.5 giá mock; §6 stay chọn room và kiểm từng đêm; minh bạch đây là đặt demo |
| `recsys-internship-handbook-v3-vi.md` | Mục tiêu học tập, thuật toán, event và tích hợp | Dùng phụ lục quyết định thay vì diễn giải 13 trường JSON thành yêu cầu một bảng vật lý duy nhất |
| `ux-research-brief.md` | Bối cảnh UX | Không phải hợp đồng DB/API và không cần chạy lại nhiệm vụ Mobbin để review này |

## 7. Các phần không nên tự quyết thay nhóm

- Chính sách booking/đơn vị cho combo, vé trẻ em/thành viên, golf và tồn tour chưa được người dùng chốt; bản thiết kế giữ phần chưa biết.
- Việc chuyển catalog sang CDP thật chưa có API thật xác nhận; tiếp tục ownership Backend theo kiến trúc được cung cấp.
- Mô hình embedding, kích thước vector, tên attribute Insider không được suy ra từ file catalog.
- Mọi endpoint/field/lỗi mới trong bản vẽ là **đề xuất hợp đồng**, cần được đưa vào cùng bản OpenAPI trước khi các team triển khai. Review này không sửa hợp đồng trên nhánh khác, không merge hay chạy migration.

## 8. Tiêu chí kiểm chứng khi triển khai

| Ca | Kết quả cần đạt |
|---|---|
| Import catalog | 10.000 ID; đúng subtype; không mồ côi cha–con |
| Seed lịch | 30 dòng active / room; một giá / room; chạy lại không thay đêm đã đặt |
| Đặt 1 đêm khi 30 đêm đều mở | 29 đêm khả dụng, 1 đêm liên kết đúng booking |
| Đặt 3 đêm | Khóa đúng 3 đêm; ngày checkout vẫn dùng được cho đơn khác |
| Hai request đồng thời cùng room/đêm | Chỉ một đơn thành công; đơn còn lại không sinh purchase thành công |
| Hai kỳ không giao nhau | Đều có thể thành công cho cùng room |
| Kỳ có 1 đêm đóng hoặc thiếu dữ liệu | Không tạo booking; không đặt một phần; không ghi purchase |
| Retry cùng Idempotency-Key | Cùng đơn/kết quả đã lưu; không trừ lịch lần hai; cùng key khác body bị từ chối |
| Commit hoặc CDP lỗi | Không có booking thành công với lịch chưa cập nhật; rollback lịch và xử lý purchase theo journal |
| Qua ngày mới tại Việt Nam | Bổ sung ngày cuối; giữ trạng thái mọi ngày giao nhau và lịch sử booking |
| Reseed/đổi catalog | Tên, giá, tổng của đơn cũ không đổi |
| Parent/POI bị gửi vào giỏ | Backend từ chối, kể cả gọi trực tiếp bỏ qua UI |
| Đặt phòng xong | Event mang ID room, taxonomy hotel; recommendation phản ánh purchase mới, không gợi ý mua khách sạn cha như dịch vụ còn thiếu |

## 9. Nguồn đã đọc

- [Thiết kế ba service ban đầu](thiet-ke-schema-3-service.md).
- [Mô hình code hiện tại](../../src/data_collection/cdp/models.py), [schema catalog](data-collection/schema.md), [quy tắc mở rộng](data-collection/expand-catalog.md).
- Các tài liệu trong `/home/dangkhoi/Downloads/`: `contract-baseline-v1.1.md`, `hop-dong-tich-hop-backend.md`, `hop-dong-tich-hop-frontend.md`, `hop-dong-tich-hop-cdp.md`, `hop-dong-tich-hop-itinerary-assistant.md`, `product.md`, `recsys-internship-handbook-v3-vi.md`, `ux-research-brief.md`.
- Nội dung Git local `origin/data_contract` tại `0f630a2`: `src/ARCHITECTURE.md`, `src/shared/contracts/openapi.yaml`, các `schemas/catalog.yaml`, `schemas/booking.yaml`, `schemas/recommendations.yaml`, `schemas/itinerary-agent.yaml`, `cdp-clone.openapi.yaml`, `src/cdp_clone/app/infrastructure/tables.py`.
