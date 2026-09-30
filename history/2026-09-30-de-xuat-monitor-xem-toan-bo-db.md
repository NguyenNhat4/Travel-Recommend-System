# Đề xuất: monitor xem toàn bộ DB `vota`, có liên kết giữa các bảng

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người yêu cầu: "không cần giứoi hạn, tôi sẽ thêm đang nhập sau, tôi muốn toàn bộ DB hiển thị, có móc nối,..". Lệch PRD
(NFR-SEC-02 cấm đọc trực tiếp vùng CDP nhạy cảm bằng SQL; NFR-SEC-01; `deployment-plan.md` §5 không có công cụ này) → đề xuất
và chờ chốt (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-09-30-monitor-xem-toan-bo-db.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-09-30-de-xuat-monitor-xem-toan-bo-db.md` — thêm: entry này.

## Quyết định

- Đã đọc `docs/prd/deployment-plan.md` §5, `docs/prd/requirements.md` NFR-SEC-01..03, DDL `db/vota_schema.sql` và
  `db/migrations/*` (bảng, khoá ngoại, cột nhạy cảm), endpoint hiện có của `src/data_collection/monitor.py`.
- Đề xuất vẫn che cột bí mật (`password_hash`, `token_hash`, …) dù người yêu cầu nói không giới hạn: NFR-SEC-01 cấm trả bí mật.
- Nêu rõ rủi ro monitor public chưa đăng nhập; khuyến nghị giới hạn IP firewall trong lúc chờ đăng nhập.

## Kiểm tra

- Chưa sửa code.

## Còn lại / rủi ro

- Chờ người yêu cầu chốt. Chưa commit.
