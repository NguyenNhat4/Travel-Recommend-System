# Bổ sung phạm vi giám sát container và crawler

- Ngày: 2026-09-30
- Trạng thái: đã chốt trong hội thoại; không cập nhật PRD theo yêu cầu người dùng

## Phạm vi

Ghi nhận phạm vi đã được người dùng chốt để mở rộng monitoring staging nhằm phát hiện container dịch vụ dừng, crawler one-shot exit lỗi/OOM và watcher mất heartbeat.

## Quyết định

- Không sửa nội dung PRD; phần triển khai được thực hiện theo phạm vi đã chốt trong hội thoại.
- Giữ nguyên semantics crawler one-shot; không bật `restart=always`.
- Dùng Docker event watcher + Ops Agent file receiver + Terraform log-based metrics/alerts.

## File thay đổi

- `history/2026-09-30-crawler-container-monitoring-alerts.md`

## Kiểm tra

- Đã đọc `docs/prd/README.md`, `docs/prd/deployment-plan.md`, `docs/prd/test-plan.md`, `history/README.md`, monitoring plan và history liên quan.
- Đã kiểm tra working tree: không có thay đổi chưa commit trước khi tạo proposal.
- Chưa chạy Terraform apply; chưa có runtime acceptance evidence.

## Việc còn lại

Đã triển khai artifact và workflow CD riêng; còn chờ chạy workflow/VM runtime và review Terraform plan trước apply staging.
