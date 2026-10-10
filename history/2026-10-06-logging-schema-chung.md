# Schema log chung cho frontend, backend, crawler

- Ngày: 2026-10-06
- Tác giả: Khoa / Claude
- Nhánh: khoa/logging
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Điều tra logging trong Terraform/monitoring cho thấy severity rỗng, metric requests đếm health check, ba app log ba kiểu. Bước 0 của việc triển khai lại log: chốt schema chung và kế hoạch để ba worktree (backend, frontend, crawler) cùng dựa vào. Theo yêu cầu, bỏ qua PRD cho đợt này.

## File thay đổi

- `docs/spec/logging-schema.md` — thêm: trường chung (`ts` +07:00, `ts_utc`, `severity`, `service`, `event`, `request_id`), sự kiện theo service/workflow, quy tắc log body, danh sách không được log
- `docs/plan/2026-10-06-logging-he-thong.md` — thêm: luồng nhánh, phạm vi từng nhánh, rủi ro
- `history/2026-10-06-logging-schema-chung.md` — thêm: entry này

## Quyết định

- Giờ Hà Nội (+07:00) kèm `ts_utc`.
- Có log nội dung request/response nhưng đã làm sạch và cắt 2.048 byte; `/auth/*` request và webhook Stripe không log body.
- Frontend chỉ Next.js (dùng pino); Express bỏ ngoài; nhóm HA để sau.
- PR của từng nhánh vào `khoa/logging`; một PR cuối từ `khoa/logging` vào `release-mvp-v2` sau khi test tích hợp.

## Kiểm tra

- Chỉ là tài liệu, chưa có code để chạy.

## Còn lại / rủi ro

- Làm bốn nhánh: backend, frontend, crawler, monitoring.
- Đo lại chi phí Cloud Logging sau khi chạy thật.
