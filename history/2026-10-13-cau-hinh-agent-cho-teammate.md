# Bàn giao cấu hình agent giống local cho teammate

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành (cấu hình và hướng dẫn; sửa cassette CI là phần riêng chưa hoàn thành)
- Phạm vi: môi trường, docs

## Mục tiêu

Người dùng hỏi các biến teammate cần thêm để chạy giống local và báo PR #196 fail.
Phục vụ FR-AGT-01/06/07, AC-AGT-06/09, NFR-REL-01. Đối chiếu env trên đĩa với code và Docker Compose;
không xuất secret hoặc thay mặc định model/PRD.

## File thay đổi

- `docker-compose.yml` — sửa: truyền ITINERARY_USE_LLM và ITINERARY_LLM_TEMPERATURE vào backend,
  giữ mặc định true/0 khi không cấu hình.
- `.env.example` — sửa: chú thích model chung cho các bước ngoài orchestrator; không đổi giá trị mẫu.
- `docs/guide/2026-10-13-cau-hinh-agent-giong-local.md` — thêm: bộ biến không bí mật theo Settings local,
  provider, nguồn dữ liệu, working memory, frontend và khác biệt Docker/CI.
- `history/2026-10-13-cau-hinh-agent-cho-teammate.md` — thêm: entry này.

## Quyết định

- Settings local ngày 13/10 hiện dùng gpt-6-luna cho model chung và orchestrator, reasoning none/low,
  temperature 1.0, data inprocess, timeout tool/LLM/request 20/30/90, TTL 86400.
  Đây là giá trị Settings/.env đọc lúc kiểm; không xác minh process backend đang phục vụ vì status local
  không kết nối được từ lượt kiểm. Không dùng giá trị gpt-6.1-sol của .env.example để gọi là cấu hình local.
- Model chung ưu tiên Gemini nếu có key; provider riêng của orchestrator không đổi luật chọn model chung.
- Compose trước sửa không có hai biến USE_LLM/TEMPERATURE, nên .env có giá trị vẫn không truyền vào container.
  Bổ sung passthrough để hiện thực settings đã có; không lệch PRD hoặc thêm nhánh graph.
- Cấu hình trace tuỳ chọn; không thêm khoá debug Phần B chưa được chốt.
- Không gọi model trong task cấu hình này. Baseline CI cần 63 hội thoại/191 lượt thử với API api.openai.com;
  đang hỏi người dùng cho phép gửi dữ liệu thử nghiệm và phí API trước phần ghi lại.

## Kiểm tra

- Đọc Settings chọn lọc chỉ in giá trị cấu hình không bí mật và boolean có key/kết nối; không in key/DSN.
- Trước sửa, `docker compose config --format json` với env override USE_LLM=false/TEMPERATURE=1.0:
  hai biến đều NOT_FORWARDED.
- Sau sửa, cùng thao tác: PASS, backend nhận false/1.0.
- Đối chiếu cả 12 biến không bí mật trong block hướng dẫn với JSON cấu hình Compose: PASS.
  Output config đầy đủ giữ trong process kiểm tra, không in chuỗi kết nối/API key.
- git diff --check: PASS. Không thêm test mirror hai dòng passthrough; kiểm trực tiếp cấu hình Compose đã render.
- PR #196 head bed00a6f được xác nhận qua gh pr view. Đọc CI trực tiếp:
  backend run 38344625825 / job 115123030029 có 2 failed, 2971 passed, 40 skipped, 3 xfailed;
  đúng hai test snapshot `test_each_turn_matches_the_recorded_behavior`, `test_every_llm_payload_is_in_the_cassette`.
  Frontend quality/E2E/Docker và crawler checks/build đều pass ở head đó.
  Log /tmp/pr-196-backend-ci.log. Connector GitHub và trình duyệt chưa đăng nhập trả 404;
  đọc được bằng CLI với tài khoản đã cấu hình. Không suy ra các biến mới chữa được lỗi cassette.

## Còn lại / rủi ro

- Cần ghi lại cassette bằng model/tool thật, đọc diff và kiểm offline, không đổi hash/xoá/skip test để che thay đổi.
- Cần kiểm CI lại trên commit sau cùng, giữ PR draft trong khi snapshot chưa đạt.
- Không triển khai, đổi secret hoặc gửi hướng dẫn trực tiếp cho teammate; tài liệu ở repo để người dùng chia sẻ.
