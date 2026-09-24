# Review field request/response và AgentState của Itinerary Agent

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Người dùng thấy agent có quá nhiều field (input/output của route và state giữa các node), cần review để
quyết field nào giữ, field nào bỏ. Yêu cầu viết thành một file trong spec agent để review sau.

## File thay đổi

- `docs/spec/agent/field-review.md` — thêm: bảng đề xuất giữ/bỏ/gộp cho request, response, `AgentState`,
  kèm bằng chứng và cột "Quyết định" để trống.
- `docs/spec/agent/README.md` — sửa: thêm dòng mục lục cho `field-review.md`.
- `history/2026-09-24-review-field-agent.md` — thêm: entry này.

## Quyết định

- Bằng chứng lấy từ grep chỗ ghi/đọc trong `src/backend/app` và code assistant của `src/frontend/src`,
  không dựa vào `state-fields.md` (đã lệch: ghi `retry` ghi `errors`, code không còn).
- Tách hai loại ràng buộc: field state là nội bộ, bỏ không cần đề xuất PRD; field contract v1 không được
  xoá (AGENTS.md §3), chỉ có thể để backend trả hoặc FE thôi đọc.
- Kích thước `description`/`attributes` đo trên `cdp.products` của DB local đã seed.

## Kiểm tra

- Không chạy test: chỉ thêm tài liệu, không sửa code.

## Còn lại / rủi ro

- Chờ người dùng điền cột "Quyết định" trong `field-review.md`, rồi mới sửa code theo mục 4 của file đó.
