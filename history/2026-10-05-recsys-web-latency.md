# Đo latency `/recommendations` trên Web (cloud) và backend local

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành (chưa đo nhánh cá nhân hoá có lịch sử trên cloud)
- Phạm vi: evaluation
- Phục vụ: NFR-PERF-01, FR-REC-01; lịch 10 ngày Day 7 (latency p95 `/recommendations` trên cloud)

## Mục tiêu

Người dùng được giao đo latency RecSys trên Web; chọn đo cả cloud và local.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-05-recsys-web-latency.md` — thêm: 3 đường (Web đã đăng nhập trên cloud, khách vãng lai cloud, 60 khách
  cá nhân hoá backend local), cách đo, cách đọc.
- `history/2026-10-05-recsys-web-latency.md` — thêm: entry này.

## Quyết định

- Trang chủ chỉ gọi `/recommendations` khi đã đăng nhập → số "Web" là đường đã đăng nhập; số khách vãng lai chỉ là mốc API.
- Cloud đã đăng nhập: người dùng tự đăng nhập trong khung trình duyệt; agent chỉ chạy `fetch` đo trong tab (không nhập mật khẩu trên site thật).
- Web local không đo: bản production cần Redis, người dùng chọn không tải image. Thay bằng `/internal/recommendations` trên backend local.
- Backend local dùng biến môi trường riêng trong scratchpad (DB bench 55433, Weaviate bench `ProductBench`, khoá Cohere / Weaviate Cloud ghi đè
  rỗng hoặc giả để không gọi dịch vụ ngoài); khoá JWT dev tạo bằng `make jwt-keys` (`secrets/`, đã gitignore).

## Kiểm tra

- Cloud đã đăng nhập: 55/55 HTTP 200, phiên `authenticated`; server p50 / p95 35 / 37 ms, client 264 / 531 ms.
- Cloud khách vãng lai: 55/55 OK; server 9 / 12 ms, client 251 / 625 ms.
- Local 60 khách: 180/180 OK; server 72 / 86 ms.
- Cloud đã đăng nhập, nhánh cá nhân hoá (`cold_start_content`, 1 event sau khi người dùng xem một sản phẩm): 40/40 OK; server p50 / p95
  820 / 1.057 ms (min 814), client 918 / 1.450 ms → **không đạt NFR-PERF-01**.

## Còn lại / rủi ro

- Đo nhánh `long_term` / `cross_vertical` trên cloud (persona P1–P3 hoặc IAP + service token).
- Nhánh cá nhân hoá trên cloud ~0,8–1,1 s: cần `stageMs` cho `/recommendations` rồi tối ưu (Weaviate cùng vùng, bỏ mask, cache vector) — owner chưa có.
- `.claude/launch.json` (cấu hình chạy backend / web local trỏ script trong scratchpad) tạo ở gốc repo, chưa gitignore — không commit.
