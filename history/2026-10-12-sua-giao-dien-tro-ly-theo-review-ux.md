# Sửa giao diện trợ lý theo bài review UX trên trình duyệt

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend, agent, docs

## Mục tiêu

Người dùng yêu cầu review widget trợ lý từ góc nhìn UI/UX trên Chrome thật (localhost:3000), rồi yêu cầu "sửa hết". Phục vụ FR-AGT-01/03/04/06, AC-AGT-01 (form), AC-AGT-02 (thẻ vé), AC-AGT-04 (thẻ khách sạn, bản đồ), user-flow §4.2. Các vấn đề review tìm ra:

- Có hai form khác nhau cho cùng một việc. Form ở màn chào chọn sẵn Biên Hòa, 3 ngày, "Nghỉ dưỡng sang trọng", "Gia đình có trẻ nhỏ", và không có ô ngày đi, số người, ngân sách.
- Ô ngày đi của form trong chat tự điền hôm nay (backend `defaults.startDate = today`, frontend hiện `today` khi trống). Người dùng tưởng đã chọn ngày, và hệ thống xếp chuyến bay ngay tối hôm đó. Số người hiện "1" nhưng form không gửi số này.
- Câu yêu cầu dựng từ form ghi ngày dạng ISO ("2026-10-12").
- Thông tin chuyến bay lặp ba lần: dòng chữ "Chặng đi — … · 12/10/2026 · 19:20 · bay thẳng", thẻ vé, và dòng "9G939 · 19:20" trong thẻ.
- Thẻ hoạt động hiện điểm đánh giá hai lần. Nút "Thêm" không nói thêm vào đâu.
- Câu hướng dẫn hàng thẻ khách sạn ghi bấm "Đổi", nhưng nút thật là "Đổi sang khách sạn này".
- Đoạn "Cách mình xếp lịch" khi có ngân sách dài 4 dòng.
- Cột lịch trình lặp thẻ khách sạn kèm ảnh lớn ở mọi ngày.
- Chú thích bản đồ liệt kê mọi loại phương tiện, kể cả loại không có trên tuyến.
- Gợi ý "Enter để gửi · Shift+Enter" vẫn hiện trên điện thoại.
- Dưới 1024px, nút "Xem lộ trình & Bản đồ song song" bấm không có tác dụng (cột phải `hidden lg:flex`).

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetOpening.tsx` — sửa: nút "Thêm thông tin chuyến đi" mở `TripDetailsForm` đủ ô, không chọn sẵn gì, kèm 5 lựa chọn sở thích cố định của AC-AGT-01.
- `src/frontend/src/components/assistant/AssistantTripStarter.tsx`, `src/frontend/tests/unit/assistantTripStarter.test.tsx` — xóa: form chọn nhanh cũ.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: ngày đi không tự điền, kèm hai nút "Thứ 7 này", "Thứ 7 tuần sau" tính từ `startDateMin`. Chưa chọn điểm đến hoặc ngày đi thì nút Xác nhận khóa và có dòng nhắc. Số ngày và số người đang hiện luôn đi trong câu gửi. Ngày viết `dd/mm/yyyy`. Hôm nay tính theo giờ Việt Nam (`vietnamToday`), thay cho giờ UTC. Nhãn "Nơi đi (để thêm vé máy bay)".
- `src/frontend/src/features/itinerary/widget/WidgetFlightCard.tsx` — sửa: dòng chiều chỉ ghi số hiệu, không lặp giờ; giá ghi "/khách × N khách".
- `src/frontend/src/components/common/ProductCard.tsx` — sửa: thẻ compact có `showRatingAndAddress` không hiện điểm lần thứ hai; nút "Thêm" thành "Thêm vào giỏ" (biểu tượng giỏ, `aria-label` có tên sản phẩm).
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: câu hướng dẫn ghi đúng tên nút "Đổi sang khách sạn này".
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — sửa: thẻ khách sạn đầy đủ chỉ ở ngày nhận phòng; các ngày khác là một dòng "Tiếp tục nghỉ tại …".
- `src/frontend/src/components/assistant/ItineraryMap.tsx` — sửa: chú thích chỉ liệt kê phương tiện có trên đường đang vẽ, và chỉ có dòng "Nơi nghỉ", "Sân bay" khi bản đồ có ghim đó.
- `src/frontend/src/features/itinerary/widget/WidgetComposer.tsx` — sửa: dòng gợi ý phím tắt ẩn dưới `sm`.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: nút "Xem lộ trình & Bản đồ song song" ẩn dưới `lg`.
- `src/frontend/tests/unit/tripDetailsForm.test.tsx`, `floatingWidgetOpening.test.tsx`, `widgetBudgetAndFlight.test.tsx`, `widgetNarration.test.tsx`, `widgetDays.test.tsx` — sửa/thêm test cho các hành vi trên.
- `src/backend/app/agents/steps/conversation.py` — sửa: `clarification_form` không tự điền `startDate` (hôm nay) và `destination` (điểm đầu của catalog) khi người dùng chưa nói; ngày đã qua để trống.
- `src/backend/app/agents/steps/narration.py` — sửa: mục "Vé máy bay" mỗi chặng chỉ còn "• Chặng đi — [tên chuyến]"; ngày, giờ, bay thẳng đã có ở thẻ vé.
- `src/backend/app/agents/steps/messages.py` — sửa: `plan_criteria_budget` (vi/en) rút còn một câu.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py`, `test_composition_plan_criteria.py` — sửa/thêm test.
- `src/backend/tests/unit/agents/behavior_snapshot/snapshot.json` — sửa: làm mới từ cassette, không gọi LLM.
- `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/nghiep-vu/hieu-y-dinh-va-hoi-lai.md`, `docs/guide/doc-code-ui-tro-ly.md` — sửa: theo hành vi mới.
- `docs/prd/update/2026-10-12-lich-trinh-ban-do-man-hep.md` — thêm: đề xuất chờ chốt cho chế độ xem lịch trình và bản đồ dưới 1024px.

## Quyết định

- Xem lịch trình và bản đồ dưới 1024px là mở rộng phạm vi: `user-flow.md` §4.2 mục 4 ghi giao diện mobile ngoài phạm vi. Vì vậy chỉ viết đề xuất (AGENTS.md §8); trước mắt ẩn nút không có tác dụng.
- Không chuyển panel sang bên phải dù linh vật ở góc phải: bố cục toàn màn hình của PRD đặt chat bên trái, chuyển sang phải thì khi mở rộng chat sẽ nhảy sang trái.
- Gộp form màn chào vào `TripDetailsForm` không lệch PRD: PRD không mô tả form chọn nhanh; AC-AGT-01 mô tả một form có đủ các ô.
- Bỏ tự điền ngày đi/điểm đến ở backend vì spec đã ghi "Agent không tự điền `startDate` khi người dùng không nói ngày". Số ngày (1) và số người (2) vẫn có gợi ý vì stepper luôn hiện một số; form gửi đúng số đang hiện.
- Không thêm tổng tiền vé ở client: spec ghi Web không tính lại tiền; tổng vé đã có ở khối "Ngân sách dự tính".
- Đổi nhãn "Thêm" thành "Thêm vào giỏ" theo ghi chú nút đặt của user-flow §4.2 ("[Thêm vào giỏ] [Đặt ngay]").
- Thẻ khách sạn: chỉ sửa câu hướng dẫn. Phần còn lại đang nằm trong đề xuất chờ chốt `2026-10-12-the-khach-san-chon-mot-cham.md`.
- Định dạng tiền đã thống nhất (₫) sau khi kiểm code. Trên ảnh chụp, ₫ của font Inter trông giống "đ", nên không phải lỗi.

## Kiểm tra

- Test viết trước và fail trên code cũ: `tripDetailsForm` (2 fail), `widgetNarration` (2), `widgetDays` (1), `test_composition_plan_criteria` + `test_itinerary_runtime` (2).
- Frontend: `tsc --noEmit` sạch; `vitest run` 79 file, 831/831 passed. `eslint` trên các file sửa: 0 lỗi, 2 cảnh báo `react-hooks/exhaustive-deps` ở `ItineraryMap.tsx` đã có ở HEAD.
- Backend (`WEAVIATE_URL` cổng đóng, `SEARCH_PREWARM=false`, `HF_HUB_OFFLINE=1`): `pytest src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract` 2789 passed, 2 skipped.
- Snapshot hành vi: replay từ cassette, 0 lượt cassette miss. Lần 1 (câu chữ): 10 kịch bản đổi, chỉ ở dòng vé, câu tiêu chí và phần đuôi bị cắt của lịch sử hội thoại. Lần 2 (form): 22 kịch bản đổi, chỉ ở `clarificationForm.defaults.startDate` (39 lượt) và `destination` (16 lượt), giờ là null.
- Trình duyệt: review ban đầu trên Chrome thật (Claude in Chrome), có tái hiện bằng DOM rằng bản đồ có kích thước 0×0 ở 625px. Lần kiểm tra sau khi sửa dừng giữa chừng vì người dùng đang gõ trên cùng tab. Backend :8000 chạy không có `--reload` từ 14:59, nên chưa xác nhận trên trình duyệt phần backend.

## Còn lại / rủi ro

- Khởi động lại backend rồi thử lại trên trình duyệt: form màn chào, ô ngày trống và nút chọn nhanh, thẻ vé, thẻ hoạt động, cột lịch trình, chú thích bản đồ.
- Chờ chốt `docs/prd/update/2026-10-12-lich-trinh-ban-do-man-hep.md`.
- Câu "bên phải" trong lời trợ lý (`narrate_outro`, prompt narrate) chưa đổi, vì nằm trong đề xuất trên.
- 5 nhãn sở thích ở `WidgetOpening.tsx` lặp lại `preferences.PREFERENCES` của backend. Đổi danh sách thì phải sửa cả hai chỗ.
- Chưa commit theo yêu cầu người dùng.
