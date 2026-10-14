# Tiến trình: số ứng viên đã xem, số orc chọn và lý do chọn

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, frontend, evaluation

## Mục tiêu

Người dùng muốn tiến trình nói rõ tìm được bao nhiêu ứng viên, chọn bao nhiêu và vì sao chọn. Việc chọn thẻ do orc (LLM)
quyết trong quyết định respond (`cards`); code chỉ kiểm (ref có trong kết quả lượt, không trùng, ≤ 10 mỗi loại) và đếm.
Phục vụ AC-AGT-09 ("code đếm riêng tìm thấy/đủ điều kiện/orc chọn/hiển thị", Think do LLM viết); không lệch PRD,
không đổi contract (`ActivityData.counts` đã có).

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa: Think của quyết định respond mang `counts` do code tính (số sản phẩm đã tra
  trong lượt, số thẻ orc chọn hiện); `PROMPT`: explanation khi respond có thẻ nêu tiêu chí chọn.
- `src/frontend/src/features/itinerary/widget/widgetProgressView.ts` — sửa: Think có số chọn hiện thành bước "Chọn gợi ý"
  với dòng "Chọn N trong M ứng viên đã xem." và lý do.
- `src/backend/tests/unit/agents/test_orc_loop.py`, `src/frontend/tests/unit/widgetV2.test.ts` — thêm test.
- `src/evaluation/agent/assistant_v2_cases.py` — sửa: ghi và in Think (kèm số chọn/đã xem) của từng lượt.

## Quyết định

- "Ứng viên đã xem" = số sản phẩm khác nhau orc đã tra trong lượt (registry), không cộng số của từng lời gọi để lượt gọi
  trùng (cache) không bị đếm hai lần.

## Kiểm tra

- `pytest test_orc_loop.py test_assistant_v2_contract.py test_assistant_v2_use_case.py`: 22 passed.
- `vitest run`: 85 file, 876 test passed; `tsc --noEmit`: sạch.
- LLM thật, backend local cổng 8001, `alias-saigon`, `ten-pool-hotels` ×3: 6/6 có Think "Chọn" với số (3/40, 3/60,
  10/20) và tiêu chí, ví dụ "Chọn vài trải nghiệm khác nhau trong thành phố: tìm hiểu lịch sử, ngắm toàn cảnh và vui
  chơi cùng gia đình."

## Còn lại / rủi ro

- `alias-saigon` vẫn 2/3 lượt lấy thêm một trang, lý do model ghi: "mới xem một phần catalog nên chưa đủ".
- Giọng Think chưa đều: còn "Bạn muốn…", lẫn "tôi"/"mình".
