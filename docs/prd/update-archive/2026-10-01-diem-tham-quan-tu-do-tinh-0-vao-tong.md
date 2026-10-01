# Điểm tham quan tự do tính 0 đ vào tổng chi phí lịch trình

- Ngày: 2026-10-01
- Người đề xuất: nhatnm / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: nhatnm, 2026-10-01 (hai điểm cần chốt cùng: theo phương án đề xuất — không loại trừ theo tag, có cảnh báo `FREE_ENTRY_ASSUMED`)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (Tiêu chuẩn Grounding, dòng "Backend tự tính tổng tiền")
- Mã FR/NFR: FR-AGT-02 (tính toán chi phí dự kiến)

## Lý do

Lịch trình có điểm tham quan không có giá thì panel lịch trình luôn ghi "Chi phí sản phẩm: Chưa tính được", dù mọi mục
có vé đều có giá. Ví dụ thật (LangSmith project `nhat-10-1`, thread `45befb6c-93d3-4c26-91eb-302df12381dc`, lượt
"2 người lớn, 5 triệu", Phú Quốc 3 ngày): khách sạn và 3 điểm có vé cộng được 4.260.300 ₫, nhưng 3 bãi biển (Bãi Dài,
Starfish Beach, Bãi tắm Sao) có `unitPrice = null` nên `estimatedTotal = null`, `budgetStatus = UNKNOWN`. Người dùng không biết
lịch trình có nằm trong ngân sách 5 triệu hay không.

Người dùng đã xác nhận các điểm này là nơi vào tự do. Ngày 01/10/2026 người dùng cũng đã chốt rằng điểm tham quan/golf
không có giá được diễn giải là "tham quan tự do" (`history/2026-10-01-tham-quan-tu-do-va-goi-nhieu-ngay.md`), nhưng chỉ
ở lời diễn giải; tổng tiền vẫn `null` vì PRD cấm coi giá thiếu là 0. Đề xuất này đưa quyết định đó vào phép tính tổng.

Catalog hiện có 299/610 điểm tham quan và 1/6 sản phẩm golf không có giá. Khách sạn, vé máy bay, combo đều có giá.

## Nội dung đề xuất

`docs/prd/architecture.md` §3, Tiêu chuẩn Grounding:

> - **Backend tự tính tổng tiền;** giá thiếu thì tổng là `null` kèm cảnh báo, không coi thiếu giá là 0.

→

> - **Backend tự tính tổng tiền.** Điểm tham quan tự do — điểm tham quan hoặc golf có `ticketed = false`, hoặc không có
>   giá — tính 0 đ vào tổng và hiển thị là "tham quan tự do", không hiển thị là có giá 0 đ. Mục khác thiếu giá (khách sạn,
>   vé máy bay, combo...) thì tổng là `null` kèm cảnh báo, không coi thiếu giá là 0.

## Điểm cần người dùng chốt cùng

- **Tour và dịch vụ có trả phí nhưng không có giá.** Trong 299 điểm không có giá có 7 "Tour đi thuyền", 1 "Chèo bè" và
  vài bảo tàng tỉnh có thể thu vé nhỏ. Đề xuất: giữ đúng luật "tham quan tự do" đã chốt ngày 01/10 (không loại trừ theo
  tag), để lời diễn giải và tổng tiền dùng chung một luật. Nếu muốn loại trừ thì chốt danh sách tag bị loại.
- **Cảnh báo kèm tổng.** Đề xuất thêm cảnh báo `FREE_ENTRY_ASSUMED` khi tổng có điểm tham quan tự do: "Tổng coi các điểm
  tham quan tự do là không mất vé; một số nơi có thể thu phí tại chỗ." `warnings[].code` là chuỗi tự do trong contract nên
  không đổi kiểu.

## Thay đổi source sau khi chốt

- `src/backend/app/domain/itinerary/planning.py` — `_known_cost` trả 0 cho điểm tham quan tự do; chuyển luật
  `_free_to_visit` từ `agents/steps/narration.py` vào domain để lời diễn giải và tổng tiền dùng chung.
- `src/backend/app/agents/steps/narration.py`, `messages.py` — dùng luật chung; câu chi phí `cost_UNKNOWN` bỏ ý "vì lịch có
  điểm tham quan tự do".
- `src/backend/app/agents/steps/composition.py` — cảnh báo `FREE_ENTRY_ASSUMED`.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — mô tả `estimatedTotal` (chỉ mô tả, không đổi kiểu); sinh lại
  `src/frontend/src/types/api.gen.ts`.
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — slot điểm tham quan tự do ghi "Tham quan tự do";
  `WidgetPlanPanel.tsx` — sửa tooltip "Chưa tính được".
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.2, `docs/spec/hop-dong-tich-hop-frontend.md` (bảng `warnings[]`),
  `docs/spec/agent/langgraph-nodes.md` — cập nhật quy tắc tính tổng.
- Test: `src/backend/tests/unit/` cho `totals` (lịch có bãi biển không giá → có tổng; khách sạn không giá → `null`),
  `test_narration.py`, test frontend của panel.
