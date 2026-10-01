# Sửa link sản phẩm LLM viết sai cú pháp thay vì bỏ cả lời diễn giải

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người dùng thấy lời dẫn dắt trên LangSmith nhưng giao diện chỉ hiện lịch trình khô (FR-AGT-03). Trace
`01a0f62a-3fa3-7170-9bc3-537b40a13f08` (project `nhat-10-1`, 01/10 06:32 UTC): `narrate` ghi `reason=malformed_link`.
gpt-4o-mini viết `[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (product:e35d…)`, vì tên catalog có ngoặc
vuông. `render` thấy `product:` nằm ngoài link nên bỏ cả bài và dùng `fallback_message`.

Trace còn cho thấy backend đang chạy code trước hai bản vá
`history/2026-10-01-sua-link-san-pham-co-ngoac-vuong.md` và `history/2026-10-01-tham-quan-tu-do-va-goi-nhieu-ngay.md`
(uvicorn chạy từ 11:54, không có `--reload`): tên vẫn còn ngoặc vuông và gói 3 ngày vẫn nằm trong slot.

## File thay đổi

- `src/backend/app/agents/steps/narration.py` — sửa: thêm `_repair_links`, chạy đầu `render`. Tên sản phẩm (gốc hoặc đã bỏ ngoặc) đứng ngay trước `(product:id)` của id trong lịch thì gộp thành link chuẩn; `(product:id)` đứng lẻ của id đã biết thì bỏ đi, và sản phẩm đó vẫn được thêm vào mục "Ngoài ra" để bấm được. Id lạ giữ nguyên nên vẫn bị bác như trước.
- `src/backend/tests/unit/agents/test_narration.py` — sửa: 3 test (ba dạng link sai trong trace, id lẻ của sản phẩm đã biết, id lạ vẫn rơi về bản dựng bằng luật).
- `history/2026-10-01-sua-link-sai-cu-phap-trong-loi-dien-giai.md` — thêm: entry này.

## Quyết định

- Sửa link chỉ khi id có trong lịch hoặc trong các gói kèm theo, nên grounding không đổi: tên luôn thay bằng tên canonical.
- Lỗi cú pháp nhỏ không đáng để bỏ cả bài viết, vì bản dựng bằng luật mất toàn bộ phần diễn giải người dùng cần.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents`: 288 passed.
- Chưa chạy lại trên giao diện: cần khởi động lại backend để nạp code mới.

## Còn lại / rủi ro

- Khởi động lại backend rồi chạy lại hội thoại Phú Quốc; xem trace `narrate` có `reason=llm`.
- Chưa commit.
