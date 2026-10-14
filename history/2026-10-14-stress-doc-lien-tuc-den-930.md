# Stress đọc liên tục trên stress-gen-1 đến 09:30 ngày 14/10

- Ngày: 2026-10-14
- Tác giả: người dùng (Khoa15) / Claude Code
- Nhánh: release-mvp-v2
- Trạng thái: dang dở (run đang chạy đến 09:30 +07)
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu: đặt stress trên VM `stress-gen-1` và sinh tải liên tục từ 00:10 đến 09:30 để lấy số liệu. Tải phù hợp với VM sinh tải, không cố định RPS. Phạm vi chỉ đọc (ẩn danh, không ghi dữ liệu, không gọi LLM, không gọi Stripe).

## File thay đổi

- `docs/spec/load-test/` — thêm báo cáo sẽ viết khi run kết thúc (chưa có tại thời điểm ghi entry này).
- Trên VM `stress-gen-1` (không nằm trong repo): `~/stress/common.js`, `~/stress/read.js` (bản từ `ops/loadtest/stress/` của worktree `claude/stress-test-design-a749f4`), `~/stress/loop.sh`, `~/stress/health.sh`; kết quả ở `~/runs/`.
- `history/2026-10-14-presort-va-cache-trang-catalog.md` — ghi riêng cho thay đổi code.

## Quyết định

- Dùng lại VM `stress-gen-1` (e2-standard-2, 2 vCPU, 7,8 GiB, k6 v2.3.0 đã có) thay vì tạo VM mới. VM được bật lại lúc 00:05.
- Calibration 200 rps trong 60 giây trên staging: dừng sau ~10 giây vì `http_req_failed` 13,9% (156/1124), p95 29,5 s, vượt ngưỡng dừng khẩn 5%. Tức là 1 VM HEALTHY không chịu được 200 rps. Đây là dữ liệu có ích, không phải lỗi của máy sinh tải: 800/800 VU đều bận, chỉ ~23 iter/s hoàn thành.
- Chạy liên tục ở **20 rps** (mức an toàn dưới trần ~35 rps đã đo cho một VM). Lý do: ở 200 rps run tự dừng ngay; 20 rps cho bản ghi trạng thái ổn định qua đêm (autoscaler, autohealing, độ trễ theo thời gian). RATE là một biến, đổi được ở `loop.sh`.
- `loop.sh` chạy theo đoạn 30 phút. Nếu đoạn dừng sớm (ngưỡng dừng khẩn) thì nghỉ 10 phút rồi chạy tiếp, không dồn tải vào staging đang lỗi. Hết giờ thì dừng ở 09:30 +07 (epoch 1791945000).
- `health.sh` lấy mẫu `/health/ready` và `/api/v1/products?limit=20` mỗi 60 giây vào `~/runs/health.csv`.
- Giữ `CACHE_BUST` bật (mặc định), nên mọi request đi thẳng tới origin.
- Autoscaler `vota-ha-app` đang ở `utilizationTarget 0.55` (đã đặt tay từ 0.9 trong run R9; repo vẫn ghi 0.9). Chưa đổi lại. Quyết định đổi về 0.9 là của người dùng.
- Cổng `preflight.sh` yêu cầu ≥ 2 VM HEALTHY trong 15 phút liên tục. Tại thời điểm chạy, MIG chỉ có 1 VM HEALTHY (`vota-ha-app-v7j4`), `vota-ha-app-z2wq` đang bị xoá. Cổng này chưa đạt. Run chạy theo yêu cầu trực tiếp của người dùng; người dùng biết rõ trạng thái này.
- Đặt một nhắc việc một lần lúc 09:35 (cron phiên, `d36f8dd6`) để thu thập số liệu và viết báo cáo. Nhắc việc chỉ chạy khi phiên Claude Code còn mở. Nếu phiên đã đóng thì số liệu vẫn còn trên VM.

## Kiểm tra

- Mốc thời gian đã đối chiếu: 00:05 +07 = 17:05 UTC; epoch 09:30 +07 = 1791945000 = 02:30 UTC 14/10.
- Segment 1 (`seg001`) bắt đầu 17:10:19 UTC, rate=20, dur=1800s, MAX_VUS=200. Mẫu health đầu: `/health/ready` 200 (0,21 s), `/products` 200 (0,17 s).
- Calibration `cal-200` (xem Quyết định): dừng sớm do abortOnFail, đúng như thiết kế.

## Còn lại / rủi ro

- Báo cáo cuối và bảng số liệu sẽ được viết khi run kết thúc, vào `docs/spec/load-test/2026-10-14-stress-doc-lien-tuc.md`. Entry này sẽ được cập nhật trạng thái khi đó (không sửa nội dung cũ, chỉ thêm kết quả vào báo cáo).
- Staging đang chạy bản cũ (chưa deploy presort và cache). Số liệu trong đêm là của bản cũ.
- Rủi ro: 1 VM và `z2wq` đang bị xoá làm staging có thể đổi trạng thái giữa đêm; autohealing có thể đẩy VM ra khỏi cân bằng tải. Health sampler sẽ ghi lại.
- Rủi ro: tải đọc liên tục 20 rps trong 9 giờ có thể kích hoạt autoscaler scale-out và đổi chi phí. Chưa có ngân sách được đặt cho việc này.
