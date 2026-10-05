# Trạng thái Search, CDP và replica — 05/10/2026

- Phục vụ: FR-SRC-01–04, FR-REC-01–02, FR-CDP-01/03, NFR-PERF-01, NFR-REL-02, NFR-SEC-02.
- Đây là bản tổng hợp trạng thái, không thay đổi PRD hay xác nhận đã triển khai staging.

## Đã có

| Phần | Kết quả và bằng chứng |
|---|---|
| Search Day 4–5 local | Báo cáo `src/evaluation/reports/eval-2026-10-05-search-day5-e5s-app.md`: APP e5-small, split dev 66/test 65, regression baseline, F1 smoke 439/439, hub check và đường cong GTE. |
| Báo cáo tuần Search | `src/evaluation/reports/report_week_3_search.md`; phần RecSys ở `report_week_3.md`. Chưa có bằng chứng gửi mentor. |
| RecSys benchmark | Báo cáo e5-small/e5-base và split đóng băng đã có trên nhánh. Không dùng số benchmark cũ để khẳng định chất lượng dữ liệu mới. |
| RecSys latency | `eval-2026-10-05-recsys-web-latency.md`: cloud popular p95 server 37 ms; cold_start_content 1.057 ms, chưa đạt 250 ms. Chưa đo long_term/cross_vertical trên cloud. |
| Dữ liệu hành vi local | `data/seed/seed_report.md`: as_of 2026-09-24, 2.000 profile, 7.145 event. Đây là dữ liệu mô phỏng local, không phải số đếm staging hiện tại. |
| Crawler/seed | Working tree có sửa lịch phòng, mapping combo, hạn chế Chromium trên VM và phân bố vé trong seed; lịch sử 02/10 ghi chi tiết. Push code không đồng nghĩa đã deploy VM. |
| Replica | Có đề xuất `docs/prd/update/2026-10-05-tach-ket-noi-doc-replica.md`, trạng thái chờ chốt. Chưa sửa kết nối runtime. |

## Chưa hoàn thành

- Gate P Search trên cloud; phân tích 10 câu cross_vertical trước khi đổi model production.
- e5-small/384 là lựa chọn benchmark của nhóm; production vẫn theo PRD Cohere v3/1024 cho tới khi đề xuất đổi model được chốt và áp dụng.
- D6a đã tạo pool 466 cặp, chưa gán nhãn; là đợt mở rộng gold tiếp theo, không bắt buộc để đọc báo cáo hiện tại. Nếu làm, cần rescore và đặt lại baseline.
- Rà sâu và bổ sung lịch sử CDP phục vụ RecSys: chưa sinh snapshot bổ sung, chưa ghi staging, chưa đo lại sau làm giàu.
- SSH primary và replica đều trả Connection refused tại cổng 22 trước xác thực. Chưa xác định lỗi VM, SSH service hay mạng; chưa kiểm tra DB/replication lag.
- Chưa triển khai các sửa crawler lên VM; xem các việc migration, combo và index còn lại trong lịch sử 02/10.

## Thứ tự làm tiếp

1. Rà lịch sử local: độ thưa từng khách, số chuyến, độ phủ sản phẩm, chuỗi view/cart/purchase, phân bố thời gian và leakage trong holdout.
2. Phân biệt thiếu thực sự với cạnh bẩn theo spec (2% orphan purchase, 3% thiếu group) và persona không lịch sử; không tự điền các trường này.
3. Chuẩn bị dữ liệu mô phỏng riêng có version trong phạm vi spec đã chốt, kèm catalog hash, cấu hình seed, as_of và báo cáo trước/sau. Nếu cần thay phạm vi/phân bố đã quy định, trình đề xuất trước.
4. Khi kết nối khôi phục: audit snapshot staging trước khi ghi primary; kiểm toàn vẹn và đồng bộ rồi mới đo lại RecSys trên split phù hợp. Giữ nguyên baseline cũ để truy vết.
5. Chốt đề xuất replica trước khi sửa kiến trúc đọc/ghi; bảo toàn role CDP và các lần đọc cần thấy ngay dữ liệu vừa ghi.

## Kiểm tra trước push

- Test liên quan data collection và toàn bộ search bench: 421 passed, 11 skipped, 1 deselected; 1 test lỗi do sandbox cấm socket. Chạy lại riêng test đó ngoài sandbox: 1 passed. Tổng 422 test pass qua hai lượt.
- Bỏ test launcher `test_share_dry_run_writes_launcher_outside_git_and_codes` theo giới hạn môi trường đã ghi trong lịch sử Search; không tuyên bố toàn bộ suite không có ngoại lệ.
- Contract validation: PASS (102 schemas, 70 fixtures; CDP clone 12 schemas, 7 fixtures).
- Chưa chạy DB verify cho các sửa seed trong lần push này do chưa có DB đích phù hợp; không reset DB benchmark đang đóng băng.
