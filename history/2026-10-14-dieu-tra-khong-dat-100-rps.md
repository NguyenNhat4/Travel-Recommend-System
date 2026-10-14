# Điều tra vì sao staging không chịu được 100 rps

- Ngày: 2026-10-14
- Tác giả: người dùng (Khoa15) / Claude Code
- Nhánh: khoa/stress-staging-2026-10-14
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu điều tra vì sao staging không chịu được 100 rps, sau khi báo cáo stress đọc liên tục đã được commit (`2d28527e`). Kết quả là báo cáo `docs/spec/load-test/2026-10-14-nguyen-nhan-khong-dat-100-rps.md`.

## File thay đổi

- `docs/spec/load-test/2026-10-14-nguyen-nhan-khong-dat-100-rps.md` — thêm: báo cáo điều tra, gồm số liệu server theo route, trần CPU một VM, đường đi của `similar` trong code, độ trễ tới Weaviate, benchmark bộ lọc, chuỗi autohealing, các yếu tố đã loại trừ, và năm giả thuyết với trạng thái.
- `history/2026-10-14-dieu-tra-khong-dat-100-rps.md` — thêm: entry này.

## Quyết định

- Không đổi code, cấu hình, hạ tầng, hay secret. Không chạy thêm tải lên staging, vì staging đang deploy blue/green từ 09:31 (+07).
- Không kết luận nguyên nhân ở mức đã chứng minh. Báo cáo ghi rõ H1 và H5 có bằng chứng; H2 và H3 có bằng chứng gián tiếp; H4 chưa kiểm chứng.
- Đặt tên báo cáo là `2026-10-14-nguyen-nhan-khong-dat-100-rps.md` và ghi rõ nó thay thế vai trò của `2026-10-13-nguyen-nhan-khong-dat-500-rps.md`, file mà đợt 3 tham chiếu nhưng không có trong repo.
- Benchmark bộ lọc `similar` chạy bằng venv tạm ngoài repo (scratchpad). Không đưa vào repo.

## Kiểm tra

- Log `http.request` của VM app theo route, cho các cửa sổ 20 rps (seg005), R1, R2, R9.
- Cloud Monitoring: CPU của cụm DB và các VM trong các cửa sổ run (`mon.py`).
- Log MIG và `compute.autoscalers.resize`: health check, autohealing, tín hiệu CPU của autoscaler.
- Cấu hình: VM template (`e2-standard-2`), health check, cổng và số tiến trình uvicorn trên VM app.
- Đo TCP tới host Weaviate từ container backend: 338–384 ms, chỉ in thời gian.
- Benchmark bộ lọc `similar` (N = 6.026): 38 ms CPU phía client trên máy local, trong đó `uuid5` chiếm 24 ms.
- Chưa chạy: profile CPU theo route trên VM, `SHOW POOLS` của pgbouncer, thống kê DB của leader hiện tại.

## Còn lại / rủi ro

- Kiểm chứng H2, H3, H4 bằng profile (`py-spy`) và test tách riêng `similar` và `products` sau khi deploy xong.
- Đo benchmark bộ lọc trên VM thật.
- Quyết định vận hành: max replica của autoscaler, cấu hình health check, và các hướng xử lý nêu trong báo cáo (cache `similar`, lọc phía Weaviate, async client, nhiều worker uvicorn).
- `ops/loadtest/stress/read.js` (bản trên VM) ghi chú tham chiếu tới `docs/plan/2026-10-13-stress-100-va-2000-rps.md`, file này không có trong repo.
