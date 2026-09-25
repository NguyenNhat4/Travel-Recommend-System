# Chuyển job Trip.com trên release MVP v1 sang cào mới rồi nạp DB

- Ngày: 2026-09-24
- Tác giả: Đăng Khôi / Codex
- Nhánh: `codex/fresh-trip-catalog-release-mvp-v1`
- Trạng thái: hoàn thành
- Phạm vi: data, deployment

## Mục tiêu

Người dùng muốn nhánh riêng từ `release-mvp-v1`, chạy tự động trên Ubuntu VM console: cào dữ liệu mới từ nguồn, lấy JSON phòng/giá Trip.com ở các mốc 14/30/60 ngày, chuẩn hóa sáu biến thể sản phẩm rồi nạp ngay vào Postgres. Không dùng `products.jsonl`, interim hay snapshot cũ để làm dữ liệu cào.

## File thay đổi

- `src/data_collection/run_fresh_catalog_vm.sh` — thêm: entrypoint trỏ normalizer/DB helper về repo release và gọi crawler Trip.com ở checkout cạnh bên; đọc cấu hình ngoài Git; khởi động Postgres Docker khi đích là local.
- `src/data_collection/cron_hotels_daily.sh` — sửa: thay job chỉ ghi staging bằng entrypoint cào mới và nạp DB.
- `src/data_collection/run_daily_docker.sh` — sửa: lệnh `run` chạy luồng cào mới; luồng `daily.py` giữ dưới `legacy-run`; log mới riêng, giữ 30 ngày.
- `src/data_collection/README.md` — sửa: giải thích nguồn dữ liệu mới, hai checkout, cron, Docker Postgres, trạng thái phòng, retention và cách tránh chạy song song job cũ.
- `history/2026-09-24-trip-catalog-fresh-release-mvp-v1.md` — thêm: quyết định và kiểm tra của task.

## Quyết định

- Phục vụ FR-CAT-01/03/04 và NFR-REL-01: sáu biến thể thuộc schema 13 trường; giá/trạng thái đến từ lần hỏi nguồn hiện tại. `docs/prd/project-brief.md` §4.2 cho phép nạp snapshot theo kỳ. Không đổi OpenAPI hay DDL.
- Dùng bước chuẩn hóa và helper DB hiện hành của repo này. Crawler Trip.com tách ở repo `tripcom-hotel-crawler` theo yêu cầu ghép hai cách cào; trên VM cần checkout cả hai nhánh. Không gọi lại seed snapshot hay `make demo-db-reset`.
- Chuyển lệnh cron quen thuộc `run_daily_docker.sh run` sang luồng cào mới để tránh vô tình dùng `daily.py` giữ interim cũ. Lệnh `legacy-run` vẫn có thể gọi thủ công; không lên lịch nó song song trên cùng DB.
- Docker chỉ quản lý Postgres local; collector cần Chromium chạy trên host trong Xvfb. Giá HTML/SSR không đủ, nên lấy JSON phòng động. Kết quả chỉ được upsert khi kiểm tra coverage; phòng mới được thêm, lỗi mạng không suy diễn là hết phòng.

## Kiểm tra

- `bash -n` ba shell script mới/sửa: PASS.
- `run_daily_docker.sh run --status` với env file và log trong `/tmp`: PASS; đầu ra đi qua entrypoint mới, báo lượt kế tiếp full.
- Normalizer của repo này trên interim mẫu cào mới: 132 sản phẩm, đủ hotel/property, hotel/room, flight/route, flight/flight, attraction, combo; đúng 13 trường.
- Helper `data_collection.seed.database` và `parse_combos` từ repo này import được bằng Python `vsf2`.
- Bộ test của checkout `tripcom-hotel-crawler`: 126 PASS; `git diff --check` ở hai repo: PASS.
- Chưa chạy lượt full mới trên VM/VPS thật hoặc ghi vào DB của người dùng; cần cấu hình URL DB và cron trên VM.

## Còn lại / rủi ro

- Phải push cả nhánh này và nhánh `codex/fresh-catalog-crawlingissue` của repo `tripcom-hotel-crawler`, triển khai hai checkout trên VM và tạo `/etc/vota/fresh-catalog.env` quyền 600.
- Nếu cron `cron_daily.sh` hoặc `legacy-run` vẫn chạy trên cùng DB, nó có thể nạp lại giá từ interim cũ; cần thay lịch bằng một dòng `run_daily_docker.sh run`.
- API phòng Trip.com có thể bị chặn hoặc thiếu một trong ba mốc; job trả mã lỗi để thử lại, không coi thiếu phản hồi là hết phòng.
