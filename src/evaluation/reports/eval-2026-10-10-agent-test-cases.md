# Golden dataset — Itinerary Agent

- Commit: `682d8684`
- Chạy lúc: 2026-10-10T12:52:04.639798+00:00
- Model: `gpt-6-luna` · dataMode: `http` · mode: `dataset`
- productCount: 4147
- LangSmith project: `không bật`
- LLM giám khảo: `gpt-6-luna` (finding `[judge]`)

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 18 lượt tính được) |

Latency: p50=5323ms, p95=26080ms, max=26942ms (mục tiêu < 5000ms, không gate).

Tổng 23 lượt, PASS 21, FAIL 2.

## Lượt FAIL

### TC-01 lượt 1 — 'Lên lịch trình 1 ngày tại Hà Nội, bắt đầu từ ngày 2026-10-10, cho 2 người lớn, ngân sách khoảng 1 triệu.'
httpStatus=200 status=NEEDS_CLARIFICATION latency=6662ms
- status='NEEDS_CLARIFICATION', kỳ vọng một trong ['COMPLETED', 'FALLBACK']

### TC-11 lượt 2 — 'Chưa có ngân sách, cứ lên lịch giúp mình.'
httpStatus=200 status=COMPLETED latency=19268ms
- [judge] Lịch không có hai điểm tham quan cùng một nơi hoặc cùng một trải nghiệm (ví dụ hai mục Hòn Thơm, hoặc cáp treo Hòn Thơm cùng vé Sun World Hòn Thơm, hoặc hai vé Water Taxi).: Ngày 1 có cả “Vinpearl Safari Phú Quốc” và “Safari Adventure”, hai mục cùng trải nghiệm Safari.

## Đã loại

Điểm tham quan node `filter` bỏ vì trùng trước khi xếp lịch (AC-AGT-04).

| Case | Lượt | Bỏ | Trùng với | Do |
|---|---|---|---|---|
| TC-01 | 3 | [Times City Hà Nội] - Vé vào cửa Thủy Cung Vinpearl Aquarium (`f9f554d8`) | [Times City Hà Nội] - Vé vào cửa trực tiếp Thuỷ cung Vinpearl Aquarium (`355d3530`) | llm |
| TC-01 | 3 | [VinWonders Wave Park] Vé vào cửa tiêu chuẩn Công viên Sóng (`aedb38c4`) | [VinWonders Wave Park] [HSSV] Vé vào cửa tiêu chuẩn Công viên Sóng + Voucher Ẩm thực 50.000 VNĐ (`8502838d`) | llm |
| TC-01 | 3 | Lotte World Aquarium Hà Nội (`a01082a3`) | [Times City Hà Nội] - Vé vào cửa trực tiếp Thuỷ cung Vinpearl Aquarium (`355d3530`) | llm |
| TC-01 | 3 | [VinWonders Wave Park & Water Park] Vé vào cửa tiêu chuẩn 2 công viên (`b5831ac0`) | [VinWonders Wave Park & Water Park] [HSSV] Vé vào cửa tiêu chuẩn 2 công viên + Voucher Ẩm thực 50.000 VNĐ (`4d92c636`) | llm |
| TC-01 | 3 | [VinWonders Wave Park & Water Park] Vé vào cửa tiêu chuẩn 2 công viên + Set đồ ăn 100.000 VNĐ (`81b22ec5`) | [VinWonders Wave Park & Water Park] [HSSV] Vé vào cửa tiêu chuẩn 2 công viên + Voucher Ẩm thực 50.000 VNĐ (`4d92c636`) | llm |
| TC-01 | 3 | [VinWonders Wave Park & Water Park] Vé vào cửa 2 Công viên + Buffet 250.000 VNĐ (`3a49e0b5`) | [VinWonders Wave Park & Water Park] [HSSV] Vé vào cửa tiêu chuẩn 2 công viên + Voucher Ẩm thực 50.000 VNĐ (`4d92c636`) | llm |
| TC-01 | 3 | Vé Hạng Cổ Loa / Tặng Voucher Ẩm thực / Quà lưu niệm (`0d926cc0`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| TC-01 | 3 | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | Vé Thuyền Gondola / 1 chiều (Kèm Chụp Ảnh) (`798716fc`) | llm |
| TC-01 | 3 | Vé Hạng Cổ Loa / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`8d849029`) | Vé Thuyền Gondola / 1 chiều (Kèm Chụp Ảnh) (`798716fc`) | llm |
| TC-01 | 3 | Vé Hạng Thăng Long / Trải nghiệm Aquafield & Set Ẩm thực (`d65600c7`) | Vé Hạng Thăng Long / Tặng Voucher Ẩm thực / Quà lưu niệm (`aefa524b`) | llm |
| TC-01 | 3 | Vé Hạng Thăng Long / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`5463024a`) | Vé Thuyền Gondola / 1 chiều (Kèm Chụp Ảnh) (`798716fc`) | llm |
| TC-01 | 3 | Vé Hạng Cổ Loa / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`c5cb2efb`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| TC-01 | 3 | Vé Hạng Văn Lang / Trải nghiệm chèo thuyền Gondola & Voucher Ẩm thực (`83d01deb`) | Vé Thuyền Gondola / 1 chiều (Kèm Chụp Ảnh) (`798716fc`) | llm |
| TC-01 | 3 | Vé Hạng Thăng Long / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`37c3940f`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| TC-01 | 3 | Vé Hạng Văn Lang / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`3443cb1f`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| TC-01 | 3 | Vé Hạng Lạc Hồng / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`3409adbc`) | Vé Thuyền Gondola / 1 chiều (Kèm Chụp Ảnh) (`798716fc`) | llm |
| TC-01 | 3 | Vé Hạng Lạc Hồng / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`9943ca95`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Aquafield & Set Ẩm thực (`fa2f9126`) | llm |
| TC-01 | 4 | Vé Hạng Cổ Loa / Tặng Voucher Ẩm thực / Quà lưu niệm (`0d926cc0`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| TC-01 | 4 | Vé Hạng Thăng Long / Tặng Voucher Ẩm thực / Quà lưu niệm (`aefa524b`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| TC-01 | 4 | Vé Hạng Văn Lang / Tặng Voucher Ẩm thực / Quà lưu niệm (`e3a1d3bf`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| TC-01 | 4 | Vé Hạng Cổ Loa / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`8d849029`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | llm |
| TC-01 | 4 | Vé Hạng Thăng Long / Trải nghiệm Aquafield & Set Ẩm thực (`d65600c7`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| TC-01 | 4 | Vé Hạng Thăng Long / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`5463024a`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | llm |
| TC-01 | 4 | Vé Hạng Cổ Loa / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`c5cb2efb`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| TC-01 | 4 | Vé Hạng Văn Lang / Trải nghiệm Aquafield & Set Ẩm thực (`cd1bbb38`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| TC-01 | 4 | Vé Hạng Thăng Long / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`37c3940f`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| TC-01 | 4 | Vé Hạng Văn Lang / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`3443cb1f`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| TC-01 | 4 | Vé Hạng Lạc Hồng / Trải nghiệm Aquafield & Set Ẩm thực (`196bed3f`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| TC-01 | 4 | Vé Hạng Lạc Hồng / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`3409adbc`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | llm |
| TC-01 | 4 | Vé Hạng Lạc Hồng / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`9943ca95`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| TC-11 | 2 | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (`e35d0af0`) | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (`f540ef2f`) | rule |
| TC-11 | 2 | [Grand World Phú Quốc] - Bảo Tàng Gấu Teddy Bear Museum (`1801ef95`) | [Grand World Phú Quốc] - Bảo Tàng Gấu Teddy Bear Museum (`bceffc48`) | rule |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`94948214`) | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`f58f09c9`) | rule |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`86b3bb5a`) | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`f58f09c9`) | rule |
| TC-11 | 2 | [Phu Quoc Passport] - Vinpearl Safari + VinWonders + Tour Grand World + Water Taxi + Show diễn (2 ngày) (`c21a8139`) | [Phu Quoc Passport] - VinWonders + Vinpearl Safari + Tour Grand World + Water Taxi + Show diễn (2 ngày) (`35c8a7d8`) | rule |
| TC-11 | 2 | [03 ngày không giới hạn] - VinWonders + Vinpearl Safari + Tour Grand World + Tặng Voucher Ẩm Thực (`8901290b`) | [03 ngày không giới hạn] - Vinpearl Safari + VinWonders + Tour Grand World + Tặng Voucher Ẩm Thực (`86f0c87f`) | rule |
| TC-11 | 2 | [Ưu đãi Venice All-in-one] - Thuyền Water Taxi + Bảo Tàng Gấu - Grand World Phú Quốc (`89e1a07f`) | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (`f540ef2f`) | llm |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Junior Zoo Keeper - Workshop nhân viên vườn thú nhí (`b6533809`) | [Vinpearl Safari Phú Quốc] - Junior Zoo Keeper - Workshop nhân viên vườn thú nhí (Khu Rùa Con) (`733c5417`) | llm |
| TC-11 | 2 | [Workshop nhí] - Teddy Junior Adventure - Nhà thám hiểm Bảo Tàng Gấu (`9f34cb20`) | [Grand World Phú Quốc] - Bảo Tàng Gấu Teddy Bear Museum (`bceffc48`) | llm |
| TC-11 | 2 | [Workshop Nhí] - Lớp học Junior Zoo Keeper + Hành trình Safari Passport + Bộ quà tặng (`59e41cb5`) | [Vinpearl Safari Phú Quốc] - Junior Zoo Keeper - Workshop nhân viên vườn thú nhí (Khu Rùa Con) (`733c5417`) | llm |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`f58f09c9`) | Vinpearl Safari Phú Quốc (`1f4564f5`) | llm |
| TC-11 | 2 | [Safari Passport] - 10 trạm khám phá Vinpearl Safari + Đóng dấu hộ chiếu + Bộ quà tặng độc quyền (`e137ef0d`) | [Safari Adventure] - 05 trạm tương tác động vật + Đóng dấu hộ chiếu (`4d74e680`) | llm |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa + Mũ Thú độc quyền + Tặng Voucher Ẩm Thực (`ff6e5a68`) | Vinpearl Safari Phú Quốc (`1f4564f5`) | llm |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Tour Night Safari + BBQ trong rừng (`b38c926e`) | [Vinpearl Safari Phú Quốc] - Tour Night Safari (`a750db7b`) | llm |
| TC-11 | 2 | hòn Thơm (`903db93c`) | Cáp Treo Hòn Thơm (`fdb01f88`) | llm |