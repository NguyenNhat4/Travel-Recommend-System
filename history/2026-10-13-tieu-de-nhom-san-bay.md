# Tiêu đề nhóm gợi ý sân bay ở /flights

- Ngày: 2026-10-13
- Tác giả: người dùng (yêu cầu) / Claude Haiku 5.5 (thực hiện)
- Nhánh: khoa/flight-hotels-combos-design
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Ô Điểm đi và Điểm đến ở `/flights` đều là sân bay, nên tiêu đề nhóm gợi ý không còn nhắc "thành phố". Đổi "Thành phố hoặc sân bay phổ biến" và "Sân bay khớp" thành "Sân bay phổ biến". Nhóm "Trong nước" giữ nguyên.

## File thay đổi

- `src/frontend/src/features/flights/airports/airportOptions.ts` — sửa: `POPULAR_TITLE = 'Sân bay phổ biến'`; bỏ `MATCH_TITLE`; nhóm khi đang gõ dùng cùng tiêu đề; sửa chú thích.
- `src/frontend/tests/unit/airportOptions.test.ts` — sửa: bỏ import `MATCH_TITLE`, kỳ vọng tiêu đề mới.
- `src/frontend/tests/unit/landingSearchSheet.test.tsx` — sửa: kỳ vọng nhóm "Sân bay phổ biến", "Trong nước".
- `docs/spec/ui-dia-diem-san-bay-va-khach-san-noi-tieng.md` — sửa: §4.1 và §4.2 dùng tiêu đề mới.
- `history/2026-10-13-tieu-de-nhom-san-bay.md` — thêm: entry này.

Không đổi PRD: FR-SRC-03 không nêu tiêu đề nhóm. Bản đề xuất đã lưu trữ giữ nguyên nội dung đã chốt.

## Quyết định

- Khi đang gõ, nhóm kết quả khớp cũng mang tiêu đề "Sân bay phổ biến", theo đúng yêu cầu "thay thế cho … Sân bay khớp". Nếu muốn tên khác cho kết quả khớp (ví dụ "Kết quả khớp"), đổi một hằng số.
- Nhãn ô "Điểm đi" và "Điểm đến" giữ nguyên, vì các test và spec đã dùng; chỉ tiêu đề nhóm đổi.

## Kiểm tra

- `npx vitest run` cho `airportOptions`, `landingSearchSheet`, `flightsPage`, `flightAirports`: 51 test, pass.
- `npx tsc --noEmit`: exit 0.
- `npx eslint` trên các file TypeScript đã chạm: exit 0.
- Chụp lại trên stack thật (Postgres từ snapshot, FastAPI, Next dev): `/flights` ở trạng thái trống và đang gõ "Đà" đều hiện "SÂN BAY PHỔ BIẾN".

## Còn lại / rủi ro

- Cần người dùng xác nhận tiêu đề "Sân bay phổ biến" cho kết quả khi đang gõ.
