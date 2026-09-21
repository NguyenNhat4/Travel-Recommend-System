# Tổng hợp thay đổi itinerary, bản đồ và audit hiệu năng ngày 18-09-2026

- Ngày: 2026-09-18
- Tác giả: người dùng / Codex / Antigravity
- Nhánh: data_contract, main
- Trạng thái: hoàn thành
- Phạm vi: frontend, agent, contract

## Mục tiêu

Tổng hợp thay đổi ngày 18-09-2026 về itinerary, AiFloatingWidget, timeline, map/routing, HITL và audit hiệu năng. Trạng thái dang dở và giới hạn môi trường được ghi rõ bên dưới.

### Các thay đổi đã gộp

- Thêm hỗ trợ lưu trú nhiều khách sạn bằng stays[]/multiHotel, dữ liệu catalog Phú Quốc/Đà Nẵng, nhận diện split-stay, tính tổng tiền theo số đêm và hiển thị đủ stay trên map. Card sản phẩm mở tab mới; badge phân loại được ẩn. Khách sạn tương ứng được đưa vào timeline đầu mỗi ngày.
- Đổi nhãn N1/N2 thành “Ngày 1/Ngày 2”; đánh số liên tục từ 1 đến n cho timeline và marker map để hover khớp điểm. Bỏ tiêu đề ngày, subtitle thời gian thực, icon MapPin/Sparkles và chữ “Mở tab mới”.
- Thêm itinerary Đà Lạt 7 ngày với sản phẩm grounded, tọa độ, hoạt động khác nhau và mode đi bộ/xe đạp/ô tô; cập nhật kịch bản xuất phát từ TP.HCM, dùng cửa ngõ Đèo Prenn làm điểm bắt đầu bản đồ. Ghi chú không phải sản phẩm dùng isActivityNote.
- Làm timeline theo giờ, địa điểm, transitInfo và dịch vụ đặt trước; sau đó tinh giản nhãn chặng/buổi và connector, bỏ quick-add, thêm bookmark.
- Nâng cấp ảnh card cho Tata Show, spa, cà phê, chợ, xe sân bay và khách sạn. Chuyển sang visual-first với ảnh lớn, hai ảnh cho khách sạn, không overlay trên ảnh; khóa aspect ratio khi cột co giãn. Gỡ hover/border/shadow trên card timeline và ProductCard.
- Thêm hover card → flyTo/pulse map, badge phương tiện và tooltip. Quy tắc routing: road phải dùng geometry thực tế, không fallback đường thẳng; ferry/cable/flight có thể dùng tuyến cong. Marker gần trùng nhau được tách để không chồng lấp.
- Routing trải qua Valhalla self-host rồi chuyển sang OSRM public. OSM Standard tiles thay CARTO; OSRM dùng car/foot/bike, cache, queue giới hạn và cập nhật kết quả từng chặng; route lỗi/không có geometry chuyển unavailable. Thêm test fixtures và browser regression checks.
- Thêm điều khiển thu nhỏ/mở lại cột chat fullscreen, tự resize Leaflet và animation trượt; thêm HITL ClarificationCard cho điểm đến, số ngày, phong cách và nhóm khách, cùng fixture completed-minimal-clarified theo MVP 1.2.0.
- Audit hiệu năng chỉ đo và đề xuất, không sửa code. Báo cáo đầy đủ các phép đo chính và giới hạn nằm trong phần “Tóm tắt audit” dưới đây.

### Tóm tắt audit

- **Nguồn và phương pháp:** exact checkout không build/typecheck được vì assistant.ts có byte UTF-8 sai và syntax corruption. Runtime/bundle metrics lấy từ temporary snapshot được sửa tối thiểu, không đại diện cho source nguyên trạng. Audit dùng Next.js 16.3.5, React 19.3.0, Node 26.7.0, Chrome; desktop 1440×900 và mobile 390×844. Có năm desktop cold runs mỗi route và ba mobile runs cho Home/Search/Assistant (CPU 4×, latency 150 ms, mạng giới hạn). /register chưa hoàn tất.
- **Chưa đo:** React Profiler, Lighthouse TBT, CPU call tree, object-level heap dominators, map waterfall, API duplicate count và /register.

| Route | LCP desktop | FCP desktop | CLS desktop | Initial JS | Transfer | Ghi chú |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Home | 2,156 ms | 1,692 ms | 0.047 | 666 KB | 5.37 MB | 37 requests; 4 ảnh; mobile long task max 294 ms |
| Search | 2,388 ms | 1,524 ms | 0.537 | 696 KB | 1.73 MB | Mobile CLS 0.884; long task max 289 ms |
| Product | 1,752 ms | 1,604 ms | 0.047 | 666 KB | 1.69 MB | Nặng ảnh |
| Cart | 1,456 ms | 1,456 ms | 0.022 | 682 KB | 1.27 MB | Shared JS cao |
| Checkout | 1,564 ms | 1,456 ms | 0.034 | 689 KB | 1.28 MB | Không tải assistant |
| Booking | 1,692 ms | 1,512 ms | 0.047 | 666 KB | 1.54 MB | Route động |
| Assistant | 1,532 ms | 1,532 ms | 0.164 | 820 KB | 1.32 MB | JS resource median 407.6 ms; mobile CLS 0.934; long task max 301 ms |
| Login | 1,488 ms | 1,488 ms | 0.047 | 686 KB | 1.27 MB | Shared shell chi phối |

- **P0 — Build:** assistant.ts invalid UTF-8/syntax làm build thất bại và typecheck báo TS1490/TS1002/TS1128/TS1005. Cần sửa source rồi đo lại trên exact checkout.
- **P1 — Client shell:** route analyzer đo raw client JS 666–820 KB và CSS dùng chung 96,963 bytes; Providers/AppShell kéo assistant và UI chung vào nhiều route. Đề xuất thu hẹp client boundary và lazy-load assistant/map.
- **P1 — Mobile responsiveness:** long task tối đa Home/Search/Assistant là 294/289/301 ms. Chưa có call tree để quy trách nhiệm; typewriter, shared shell, assistant state và Leaflet chỉ là giả thuyết.
- **P1 — Layout shift:** Search/Assistant CLS desktop 0.537/0.164, mobile 0.884/0.934. Ảnh không có intrinsic dimensions và Google Fonts là giả thuyết, chưa có layout-shift attribution.
- **P1 — Payload ảnh Home:** median 5.37 MB; hero tải ảnh Unsplash 2000 px. Đề xuất ảnh responsive có dimensions và lazy-load gallery.
- **P1 — Heap:** sau CDP GC, heap đo từ 3.28 MB lên 5.69 MB ở sample cuối của 20 chu kỳ mở/đóng; đây là nghi vấn retention, chưa chứng minh leak vì không có dominator/retainer snapshot.
- **P2 — Map:** effect dựng marker/route và OSRM cache 6 giây; chưa đo cost bằng itinerary deterministic nên cần profile trước khi tối ưu.
- ESLint có 9 warnings; đây là code evidence, không chứng minh render dư. Với output standalone, báo cáo khuyến nghị dùng standalone server entrypoint thay vì next start. Gzip/duplicate chunk attribution chưa đo.

## File thay đổi

- `src/frontend/src/types/travel.ts` — thêm multi-hotel, transit mode và thông tin slot.
- `src/frontend/src/data/catalog.ts` — thêm khách sạn/điểm đến và cập nhật ảnh sản phẩm.
- `src/frontend/src/services/assistant.ts` — planner Đà Lạt, intent đa khách sạn, dữ liệu timeline và transit mode.
- `src/frontend/src/services/routeGeometry.ts` — route providers, geometry, cache/timeout và OSRM/Valhalla handling.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — stays, timeline, card visuals, chat collapse, HITL và trạng thái map.
- `src/frontend/src/components/assistant/ItineraryMap.tsx` — marker, số thứ tự, route, tiles, transit, resize và interaction.
- `src/frontend/src/components/common/ProductCard.tsx` — mở tab mới, ExternalLink, ẩn taxonomy và bỏ hover.
- `src/frontend/.env.example` — cấu hình OSRM public.
- `src/frontend/tests/routeGeometry.test.ts`, `src/frontend/tests/e2e/routes.spec.ts`, `src/frontend/tests/fixtures/route-geometry.osrm.json`, `src/frontend/tests/fixtures/route-geometry.valhalla.json` — tests/fixtures routing.
- `src/shared/mocks/itinerary-agent/completed-minimal-clarified.json` — fixture HITL.

## Quyết định

- Giữ dữ liệu sản phẩm và giá gắn với catalog; mọi hoạt động không có sản phẩm được phân biệt bằng ghi chú hoạt động. Hỗ trợ ngược dữ liệu stay cũ khi thêm stays[].
- Road route không được vẽ đường giả khi provider unavailable; phương tiện không thuộc road routing dùng tuyến cong riêng. OSRM public có queue/cache để hạn chế request và được coi là giải pháp demo/best-effort.
- Các thay đổi hình ảnh ưu tiên ảnh đúng ngữ cảnh, tỷ lệ ổn định và không phủ nội dung lên ảnh. Timeline ưu tiên thời gian/địa điểm rõ nhưng bỏ nhãn lặp.
- Runtime audit dùng temporary snapshot vì checkout nguyên trạng không build được; số đo snapshot không được xem là hiệu năng đã xác minh của exact source. Không có optimization nào được áp dụng trong audit.
- Kết quả kiểm tra dưới đây là kết quả đã ghi nhận khi thực hiện các thay đổi; không chạy lại trong lần tổng hợp này.

## Kiểm tra

- Các lần kiểm tra ghi nhận typecheck/build pass; routeGeometry tests lần lượt 6/6, 7/7, 8/8 và 15/15 theo từng thời điểm/provider. Đà Lạt có smoke check bảy ngày, 21 slot có tọa độ và 10 lượt sản phẩm bookable.
- HITL typecheck và kiểm tra fixture với mẫu completed-minimal pass. Một thay đổi đánh số marker ghi rõ typecheck chưa chạy lại.
- Một số browser E2E/full API tests chưa chạy do thiếu Chromium hoặc sandbox không cho bind server/IPC (EPERM). Contract validator có lần lỗi do catalog/fixture dirty thiếu priceUnit, ngoài thay đổi routing.
- Audit exact source build/typecheck fail do invalid UTF-8/syntax trong assistant.ts; temporary snapshot build/typecheck pass. React Profiler, CPU call tree, dominator snapshot và /register chưa đo/chưa hoàn tất.

## Còn lại / rủi ro

- Phần xác minh browser E2E cho route geometry còn dang dở do giới hạn môi trường; ferry/cable/flight cần provider hoặc geometry riêng.
- Các entry Valhalla/OSRM ghi E2E bị giới hạn môi trường. Valhalla cần self-host; OSRM public không có SLA, nên production cần provider có SLA hoặc self-host và giới hạn lưu lượng.
- Audit yêu cầu sửa assistant.ts trước khi đo lại exact source, sau đó chạy React/CPU profiling, heap dominator/retainer, /register và map scenario deterministic. Kết quả audit không chứng minh leak hay mức cải thiện Before/After.
