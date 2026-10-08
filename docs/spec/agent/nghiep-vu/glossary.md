# Glossary — thuật ngữ Itinerary Agent

Mỗi thuật ngữ một dòng định nghĩa. Cột "Chi tiết" trỏ tới file duy nhất mô tả đầy đủ.

## Hội thoại

| Thuật ngữ | Nghĩa | Chi tiết |
|---|---|---|
| <a id="luot"></a>Lượt (turn) | Một tin nhắn của người dùng và đúng một response của trợ lý; chạy một lần qua graph | [vong-doi-mot-luot.md](vong-doi-mot-luot.md) |
| <a id="response"></a>Response | Kết quả của lượt: `COMPLETED`, `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK`, hoặc lỗi | [vong-doi-mot-luot.md](vong-doi-mot-luot.md) |
| <a id="intent"></a>Intent (`TripIntent`) | Chuyến đi đã biết: điểm đến, số ngày, ngày đi, số người, ngân sách, nơi đi, sở thích, nhịp độ | [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md) |
| <a id="constraints"></a>Constraints | Ràng buộc ngoài intent: bắt buộc/loại trừ loại sản phẩm, trần giá và số sao khách sạn, tiện ích, tên bắt buộc, sản phẩm bị bỏ | [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md) |
| <a id="truong-bat-buoc"></a>Trường bắt buộc | `destination`, `days`, `startDate`, `party`; thiếu thì chưa tìm sản phẩm | [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md) |
| <a id="hoi-gop"></a>Hỏi gộp | Một câu hỏi duy nhất mỗi hội thoại về ngày đi, số người, ngân sách, nơi đi | [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md) |
| <a id="form-goi-y"></a>Form gợi ý (`clarificationForm`) | Form điền sẵn 6 ô, gửi kèm câu hỏi khi hỏi bằng chữ chưa đủ | [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md) |
| <a id="chip"></a>Chip sửa tay (`intentOverride`) | Giá trị người dùng sửa trực tiếp trên UI; thắng giá trị LLM trích | [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md) |
| <a id="guardrail"></a>Guardrail | Luật tất định chặn chèn lệnh, tin rác ở đầu vào và câu cấm ở đầu ra; không gọi LLM | [../langgraph-nodes.md](../langgraph-nodes.md) |
| <a id="previous_selection"></a>Sản phẩm đã cho xem (`previous_selection`) | id, tên, loại của chỗ ở và hoạt động trong lịch gần nhất; nguồn duy nhất để đổi món | [sua-lich-qua-nhieu-luot.md](sua-lich-qua-nhieu-luot.md) |
| <a id="ghi-chu-luot"></a>Ghi chú lượt (`note`) | Câu tóm tắt nghĩa của tin trợ lý, dựng bằng luật, đưa cho LLM ở lượt sau thay cho cả bài | [sua-lich-qua-nhieu-luot.md](sua-lich-qua-nhieu-luot.md) |

## Sản phẩm và truy xuất

| Thuật ngữ | Nghĩa | Chi tiết |
|---|---|---|
| <a id="taxonomy"></a>Taxonomy (loại) | `hotel`, `attraction`, `golf`, `combo`, `flight`; ba loại đầu xếp được vào lịch | [xep-lich.md](xep-lich.md) |
| <a id="tool-plan"></a>Tool plan | Danh sách 1–5 lời gọi tool do LLM planner lập, đã được code kiểm và bù | [tim-ung-vien.md](tim-ung-vien.md) |
| <a id="nguon"></a>Search / Recommendation / Similar | Ba nguồn sản phẩm: tìm theo câu, gợi ý cá nhân hoá, sản phẩm tương tự sản phẩm đã xem | [tim-ung-vien.md](tim-ung-vien.md) |
| <a id="goi-y-truy-xuat"></a>Gợi ý truy xuất (`search_hints`) | Cụm ngữ nghĩa code thêm vào query để kéo sản phẩm hợp yêu cầu vào top-10 | [tim-ung-vien.md](tim-ung-vien.md) |
| <a id="hau-kiem"></a>Hậu kiểm | Lọc lại kết quả tool theo intent và constraints sau khi truy xuất | [tim-ung-vien.md](tim-ung-vien.md) |
| <a id="candidate"></a>Ứng viên (candidate) | Sản phẩm thật còn lại sau hậu kiểm; chỉ ứng viên mới được xếp vào lịch | [tim-ung-vien.md](tim-ung-vien.md) |
| <a id="drop_summary"></a>`drop_summary` | Vì sao từng loại không còn ứng viên; dùng để nói lý do thật | [tim-ung-vien.md](tim-ung-vien.md) |
| <a id="grounding"></a>Grounding | Mọi sản phẩm, giá, `productId` trong câu trả lời phải đến từ kết quả tool của lượt; kiểm ở `finalize` | [dien-giai-va-kiem-tra.md](dien-giai-va-kiem-tra.md) |

## Lịch trình

| Thuật ngữ | Nghĩa | Chi tiết |
|---|---|---|
| <a id="compose"></a>Compose | Bước xếp lịch bằng luật, không LLM | [xep-lich.md](xep-lich.md) |
| <a id="slot"></a>Slot | Một dòng trong ngày: một sản phẩm, hoặc một dòng không gắn sản phẩm (`TRANSFER`) | [xep-lich.md](xep-lich.md) |
| <a id="buoi"></a>Buổi (`SlotTime`) | `MORNING`, `NOON`, `AFTERNOON`, `EVENING`; có khung giờ chỉ khi khớp với giờ bay | [xep-lich.md](xep-lich.md#theo-gio-bay) |
| <a id="cho-o"></a>Chỗ ở (stay) | Tối đa 2 khách sạn cho `days − 1` đêm (tối thiểu 1), mỗi khách sạn một đoạn đêm liền nhau (`stays[]`, `fromNight`) | [xep-lich.md](xep-lich.md) |
| <a id="hoat-dong-ca-ngay"></a>Hoạt động cả ngày | Hoạt động ≥ 360 phút; đứng một mình trong ngày | [xep-lich.md](xep-lich.md) |
| <a id="goi-nhieu-ngay"></a>Gói nhiều ngày | Tour/vé từ 2 ngày; không xếp vào slot, chỉ trả kèm để cân nhắc | [xep-lich.md](xep-lich.md) |
| <a id="tham-quan-tu-do"></a>Tham quan tự do | Điểm `ticketed = false`, hoặc điểm tham quan/golf không có giá; tính 0 đ | [xep-lich.md](xep-lich.md) |
| <a id="cua-so-gio"></a>Cửa sổ giờ (`day_windows`) | Các buổi còn dùng được ở ngày đến/ngày về theo giờ bay | [xep-lich.md](xep-lich.md#theo-gio-bay) |
| <a id="transfer"></a>`TRANSFER` | Dòng di chuyển sân bay ở ngày đến và ngày về | [xep-lich.md](xep-lich.md#theo-gio-bay) |
| <a id="moc"></a>Mốc (anchor) | Medoid của các hoạt động rõ vị trí; hoạt động gần mốc được chọn trước | [xep-lich.md](xep-lich.md#gom-theo-khoang-cach) |
| <a id="muc-khoang-cach"></a>Mức khoảng cách (band) | Khoảng cách chia theo bậc 2 km; cùng mức thì giá quyết định | [xep-lich.md](xep-lich.md#gom-theo-khoang-cach) |
| <a id="ro-vi-tri"></a>Rõ vị trí | Có toạ độ và không phải toạ độ tâm thành phố | [xep-lich.md](xep-lich.md#gom-theo-khoang-cach) |
| <a id="quang-duong-chuyen"></a>Quãng đường của chuyến | Tổng km đường chim bay: ngày 1 từ điểm đầu tới khách sạn, ngày giữa từ khách sạn đêm trước qua các điểm tới khách sạn đêm đó, ngày cuối từ khách sạn tới điểm cuối | [xep-lich.md](xep-lich.md#gom-theo-khoang-cach) |
| <a id="doi-khach-san"></a>Đổi khách sạn | Chuyển khách sạn một lần giữa chuyến (chuyến từ 5 ngày, mỗi khách sạn ≥ 2 đêm), tính thêm 15 km vào chi phí; ngày đổi có dòng `CHANGE_STAY` | [xep-lich.md](xep-lich.md#gom-theo-khoang-cach) |
| <a id="lich-vua-ngan-sach"></a>Lịch vừa ngân sách | Mọi giá biết được và tổng tiền (gồm vé máy bay) không vượt ngân sách; có ngân sách thì chỉ chọn trong các lịch này, không lịch nào vừa thì lấy lịch rẻ nhất | [xep-lich.md](xep-lich.md#gom-theo-khoang-cach) |
| <a id="phuong-an-khac"></a>Phương án khác (`STAY_OPTIONS`) | Tối đa 3 cách chọn khách sạn khác, ghi "thêm X ₫ → bớt Y km" hoặc "bớt X ₫ → đi thêm Y km"; chọn bằng "lấy phương án N" | [xep-lich.md](xep-lich.md#gom-theo-khoang-cach) |

## Vé máy bay

| Thuật ngữ | Nghĩa | Chi tiết |
|---|---|---|
| <a id="tuyen-chuyen"></a>Tuyến / chuyến | Tuyến là cặp thành phố (không đặt được); chuyến là chuyến bay cụ thể dưới tuyến | [ve-may-bay.md](ve-may-bay.md) |
| <a id="chang-bay"></a>Chặng bay (leg) | Một vé trong lịch: `OUTBOUND`, `RETURN` hoặc `ROUND_TRIP` | [ve-may-bay.md](ve-may-bay.md) |
| <a id="noi-di"></a>Nơi đi (`origin`) | Thành phố khởi hành; không bắt buộc, cần để có vé | [ve-may-bay.md](ve-may-bay.md) |

## Câu trả lời

| Thuật ngữ | Nghĩa | Chi tiết |
|---|---|---|
| <a id="narrate"></a>Narrate | LLM viết lời cho lịch đã dựng; code điền tên, giá và các mục hệ thống | [dien-giai-va-kiem-tra.md](dien-giai-va-kiem-tra.md) |
| <a id="placeholder"></a>Placeholder giá | `[[price:<id>]]`, `[[total]]`, `[[budget]]`; LLM viết, code điền số | [dien-giai-va-kiem-tra.md](dien-giai-va-kiem-tra.md) |
| <a id="ban-dung-bang-luat"></a>Bản dựng bằng luật | Câu trả lời không qua LLM, dùng khi LLM lỗi hoặc bài viết vi phạm | [dien-giai-va-kiem-tra.md](dien-giai-va-kiem-tra.md) |
| <a id="fallback"></a>`FALLBACK` | Status khi có sản phẩm mà không dựng được lịch; trả danh sách theo loại | [vong-doi-mot-luot.md](vong-doi-mot-luot.md) |
| <a id="finalize"></a>Finalize | Cửa ra chung: kiểm contract, grounding, câu cấm; lưu hội thoại | [dien-giai-va-kiem-tra.md](dien-giai-va-kiem-tra.md) |
| <a id="warning"></a>Warning | Cảnh báo kèm response (`PRODUCT_DROPPED_*`, `FLIGHT_*`, …) | [dien-giai-va-kiem-tra.md](dien-giai-va-kiem-tra.md) |
