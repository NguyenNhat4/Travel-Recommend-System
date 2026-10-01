# Sửa link sản phẩm hiện thô trong chat khi tên catalog có ngoặc vuông

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, frontend

## Mục tiêu

Sau `history/2026-10-01-narrate-loi-dien-giai-lich-trinh-va-sua-doi-ngay.md`, lời diễn giải lịch trình Phú Quốc hiện thô
`[[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)](product:e35d…)` thay vì nút bấm (screenshot người dùng).
Nguyên nhân: tên catalog có dấu ngoặc vuông. `render` thay nhãn link bằng tên canonical nên ngoặc vuông nằm lồng trong
nhãn; regex link ở backend (`PRODUCT_LINK`) và frontend (`parseAssistantText`) không cho phép `[` `]` trong nhãn, nên
không nhận ra link. Phục vụ FR-AGT-03, FR-AGT-04.

## File thay đổi

- `src/backend/app/agents/steps/narration.py` — sửa: thêm `_label(product)` bỏ `[` `]` khỏi tên khi dựng link (`_link`, dùng cho `render` và `fallback_message`) và khi gửi tên cho LLM (`narration_input`).
- `src/backend/tests/unit/agents/test_narration.py` — sửa: thêm test tên có ngoặc vuông (link nhận ra được, không còn `[[`, bản dựng bằng luật cũng đúng, LLM nhận tên đã bỏ ngoặc) và test nhãn LLM tự viết có ngoặc lồng thì rơi về bản dựng bằng luật.
- `src/frontend/src/components/assistant/inlineBold.tsx` — sửa: regex link chịu được một tầng ngoặc vuông trong nhãn và bỏ ngoặc khi hiển thị, để tin nhắn đã lưu trước bản vá vẫn hiện đúng.
- `src/frontend/tests/unit/inlineBold.test.ts` — sửa: thêm test với đúng chuỗi trong screenshot.
- `history/2026-10-01-sua-link-san-pham-co-ngoac-vuong.md` — thêm: entry này.

## Quyết định

- Sửa gốc ở backend: nhãn link không bao giờ chứa ngoặc vuông. Tên vẫn lấy từ dữ liệu, chỉ bỏ ký tự `[` `]` nên vẫn đúng spec §5 mục 2.
- Frontend chịu thêm một tầng ngoặc chỉ để hiển thị đúng tin nhắn cũ trong lịch sử; không dựa vào đó cho tin nhắn mới.
- Backend `PRODUCT_LINK` giữ nguyên (không nhận ngoặc lồng), nên nhãn LLM tự viết có ngoặc lồng vẫn bị từ chối và dùng bản dựng bằng luật.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents`: 278 passed.
- `src/frontend`: `npx vitest run` 44 file, 405 test pass; eslint file đã sửa sạch; `npm run typecheck` chỉ còn lỗi `.next/types` sẵn có.
- Chưa thử lại trên trình duyệt với hội thoại Phú Quốc.

## Còn lại / rủi ro

- `plain_links` ở backend (dùng khi đưa lịch sử cho LLM) vẫn không đổi được link cũ có ngoặc lồng thành tên thường; chỉ ảnh hưởng tin nhắn đã lưu trước bản vá, LLM vẫn đọc được.
- Chưa commit.
