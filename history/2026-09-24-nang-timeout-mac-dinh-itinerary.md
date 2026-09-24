# Nâng timeout mặc định của Itinerary Agent lên 10 giây

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent

## Mục tiêu

Giá trị mặc định cũ (tool 1 giây, LLM 2 giây, request 5 giây) quá chặt cho model thật và catalog thật, làm request ở
chế độ chạy golden/demo bị timeout dù không lỗi. Ghi lại thay đổi đã nằm trong working tree để lịch sử đầy đủ.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: `itinerary_tool_timeout_seconds`, `itinerary_llm_timeout_seconds`,
  `itinerary_request_timeout_seconds` mặc định đều 10.0 (trước: 1.0, 2.0, 5.0).
- `history/2026-09-24-nang-timeout-mac-dinh-itinerary.md` — thêm: entry này.

## Quyết định

- Các biến `ITINERARY_*_TIMEOUT_SECONDS` vẫn ghi đè được qua môi trường.
- Số mới **vượt** ngân sách SLA của `hop-dong-tich-hop-itinerary-assistant.md` §7.2 (classify 2 giây, toàn request
  mục tiêu 5 giây). Không dùng số đo ở cấu hình mặc định này làm bằng chứng đạt SLA; nhắc lại cảnh báo trong
  `docs/spec/agent/README.md`.

## Kiểm tra

- Không chạy test: chỉ đổi giá trị mặc định của cấu hình.

## Còn lại / rủi ro

- Trước khi đo SLA (NFR hiệu năng) phải đặt lại timeout về ngân sách của spec bằng biến môi trường.
