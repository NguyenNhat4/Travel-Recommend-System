# Tiến trình: bước Think có vòng quay/✓ và tiêu đề; nút gợi ý dạng ↪

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Người dùng muốn khung tiến trình như Pengo: mỗi bước đang làm có vòng quay, xong thì ✓; lời giải thích của AI đọc như
suy nghĩ chứ không như câu trả lời; nút gợi ý (follow-up) cùng phong cách. Phục vụ AC-AGT-09 (bước đang chạy có biểu
tượng chờ, xong có ✓), không lệch PRD.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa: Think thành bước có tiêu đề ("Phân tích
  yêu cầu" vòng đầu, "Đánh giá kết quả" các vòng sau), lời giải thích nằm ở dòng chi tiết; chờ đầu lượt là "Đang phân
  tích yêu cầu…".
- `src/frontend/src/features/itinerary/widget/WidgetProgress.tsx` — sửa: Think dùng cùng dạng bước với việc (✓, tiêu
  đề đậm, chi tiết xám).
- `src/frontend/src/components/assistant/SuggestionChips.tsx` — sửa: nút gợi ý xếp dọc, nền xanh nhạt, biểu tượng ↪.
- `src/frontend/tests/unit/widgetV2.test.ts` — sửa kỳ vọng nhãn/chi tiết của Think.

## Quyết định

- Không hiện query tìm kiếm thô như Pengo ("Đang tìm kiếm cafe ven sông Hương…"): AC-AGT-09 cấm "tên tool/API/query
  thô" trong SSE. Dòng việc vẫn là "Đang tìm <loại> ở <nơi>…". Muốn hiện query thì cần đề xuất lệch PRD.
- Think được phát khi quyết định đã xong nên luôn là ✓; vòng quay trong lúc model nghĩ là dòng chờ sẵn có.
- `SuggestionChips` dùng chung v1/v2 nên đổi kiểu cho cả hai.

## Kiểm tra

- `vitest run`: 85 file, 874 test passed. `tsc --noEmit`: sạch.
- Chưa xem trên trình duyệt.

## Còn lại / rủi ro

- Chưa sửa giọng văn của explanation (vẫn có "Được chứ, mình sẽ…") và Think ở bước respond lặp câu trả lời — đã nêu
  trong phân tích UX, chưa làm.
