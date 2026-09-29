# Plan pipeline: bỏ hướng Airflow, thêm CP7 cảnh báo và CP8 SLA

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: docs (data)

## Mục tiêu

Người yêu cầu quyết định không dùng Airflow cho pipeline dữ liệu. Thay vào đó, học cách Airflow giải quyết từng vấn đề
rồi tự làm bằng code. Cập nhật plan theo quyết định này và thêm hai phần còn thiếu: cảnh báo khi lỗi và SLA.

## File thay đổi

- `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` — sửa:
  - đổi tiêu đề;
  - thay dòng "Bước sau: DAG Airflow" bằng quyết định không dùng Airflow và lý do;
  - thêm mục tiêu "biết ngay khi lượt lỗi hoặc không chạy";
  - thêm CP7 (cảnh báo, tương đương `on_failure_callback`) và CP8 (SLA: hạn xong trong ngày, bước chậm, catalog cũ);
  - thêm bảng "Đối chiếu với Airflow";
  - bỏ câu "bọc `@task` Airflow" ở CP4 và ở cuối mục Kiến thức;
  - thêm rủi ro về cảnh báo dồn và giới hạn của SLA dựa trên cron tick.

## Quyết định

- Không dùng Airflow. Lý do: một job mỗi ngày, khoảng 7 nguồn, VM 2 CPU / 4 GB; scheduler, webserver và database
  metadata của Airflow nặng hơn nhu cầu.
- CP7 luôn ghi `alerts.jsonl` và hiện cảnh báo trên monitor; phần này không chạm PRD.
- Kênh gửi cảnh báo ra ngoài (Telegram, email hoặc webhook) còn **chờ người yêu cầu chốt**. Kênh nào cũng cần secret
  mới trong `docs/prd/deployment-plan.md` §2, nên phải có đề xuất trong `docs/prd/update/` được chốt trước khi code phần gửi.
- Ngưỡng SLA trong plan (`sla.finishBy` 19:00, `sla.slowFactor` 3, `sla.maxCatalogAgeHours` 48) là đề xuất của agent,
  chưa được người yêu cầu xác nhận.
- CP7 không phụ thuộc CP6, có thể làm trước CP6.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy test.

## Còn lại / rủi ro

- CP6, CP7, CP8 chưa code.
- Chốt kênh gửi cảnh báo ra ngoài và ngưỡng SLA.
- SLA dựa trên cron tick không bắt được lỗi VM hoặc cron chết; cần heartbeat bên ngoài, chưa có trong plan.
