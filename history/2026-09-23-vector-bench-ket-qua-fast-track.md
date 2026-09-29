# Kết quả chạy fast-track vbench: chưa chốt được vector DB, và vì sao

- Ngày: 2026-09-23
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/vector-db
- Trạng thái: hoàn thành
- Phạm vi: evaluation
- Tiếp nối: `2026-09-22-vector-bench-fasttrack.md` (phần code, khi đó còn dang dở vì chờ chốt lưới sigma)

## Mục tiêu

Chạy thật fast-track trên catalog do `make demo-db` bung (2.897 search unit, bge-m3) và 1M vector khuếch đại, rồi áp quy tắc chốt §6.

## File thay đổi

- `src/evaluation/vector_bench/config/vbench.yaml` — sửa: `fast.amplify.sigmas` = {0,05 … 0,6} (người chạy chốt 22/09; lưới cũ của spec không đạt trên vector thật).
- `src/evaluation/vector_bench/engines/pgvector.py` — sửa: `ANALYZE items` trước khi build index.
- `src/evaluation/vector_bench/engines/pgvectorscale.py` — sửa: `finalize()` đặt `diskann.force_parallel_workers` = `max_parallel_maintenance_workers`; `index_meta()` ghi lại giá trị đó.
- `src/evaluation/vector_bench/runners/perf.py` — sửa: ghi `status_split` (ok_in_budget · ok_but_late · engine_timeout · skipped_late) và `uncapped_ms`.
- `src/evaluation/vector_bench/fast_report.py` — sửa: thêm dòng "index ANN thật sự dùng" và hai ghi chú đọc số.
- `src/evaluation/vector_bench/README.md` — sửa: bảng lệch spec và mục việc còn mở.
- Kết quả (không commit, `bench_out/` bị ignore): `bench_out/runs/fast-20260922/`.

## Kết quả

Catalog thật (2.897 search unit): cả ba engine **G3 pass, 0 vi phạm filter, A3 = 1,0, count exact 100%**.

| | A1 (cấu hình b) | Index ANN có thật sự chạy? |
|---|---|---|
| Qdrant | 1,0000 | **Không** — `0/2897 vector đã index` (mỗi segment dưới `indexing_threshold` 10 MB) → là brute force |
| pgvector | 0,9920 | Chỉ ở bucket không lọc; `plan_uses_index_rate = 0%` cho query có filter |
| pgvectorscale | 0,7672 | Có (40%) |

1M khuếch đại (σ = 0,5; LID ratio 1,286 PASS; gần trùng 0%):

- **pgvector** (đo đủ, 22,8 phút): A1 = 0,553 → trượt · A3 = 1,0 · B3 = 6,3 phút (nạp 202 s + build 177 s) · C1 đỉnh 10,7 GB · B1 trượt.
- **Qdrant** và **pgvectorscale**: build index 1M vượt khung 35 phút/engine nên bị cắt → không có A1/B1 ở 1M.

`fast-report` kết luận **CHƯA CHỐT**: engine ưu tiên cao hơn chưa đo đủ thì không được nhảy sang engine sau.

## Quyết định

- Lưới sigma mở rộng tới 0,6 (người chạy chốt): hiệu chỉnh chọn 0,6 → trượt LID 1,64 → lùi 0,5 (LID 1,286, qua).
- `ANALYZE` trước build + `diskann.force_parallel_workers`: đo 100k cho thấy mặc định diskann build TUẦN TỰ (202–227 s, 1 lõi); bật cả hai → 4 worker, 79 s. Cấp cho pgvectorscale đúng ngân sách song song mà fasttrack §4 cấp cho pgvector.
- Không chạy lại Qdrant/pgvectorscale với khung lớn hơn (người chạy chốt 23/09).
- Không bật lại container p205 sau khi đo (người chạy chốt 23/09); hai container Postgres đã bật lại.

## Kiểm tra

- `pytest src/evaluation/vector_bench/tests`: 60 passed, 3 skipped.
- Workflow kiểm chứng đối kháng 6 agent trên chính kết quả đo, mỗi kết luận có một agent phản biện độc lập. **Không có lỗi đo**: GT 1M được dựng lại từ đầu cho 18 query (khớp tới 3,6e-7); 250 query exact ở 1M đều recall 1,0 (chứng minh id↔row, filter mask và công thức recall đều đúng ở quy mô 1M); fp16 bị loại trừ bằng số (sai số cosine 2,2e-5 so với khoảng cách hạng 9–10 là 4,0e-4); index phủ đủ 1M dòng (2.730 B/dòng).

## Cách đọc ba con số (đã sửa sau phản biện)

1. **A1(1m) = 0,553 KHÔNG phải kết luận chất lượng của pgvector.** Khuếch đại chép metadata từ seed sang cả ~345 bản sao, nên filter chọn nguyên cụm: dòng khớp thứ 10 nằm ở hạng 7.806 (b10) và 39.488 (b1) trong thứ tự không lọc, sâu gấp 53× và 32× so với kỳ vọng nếu metadata độc lập; 37% query b10 và 63% query b1 có dòng khớp thứ 10 nằm ngoài hạng 20.000, tức không lần chạy nào với `max_scan_tuples = 20000` trả đủ k được. Trên catalog thật cùng bộ sinh filter, tỷ lệ này là 1,0–1,5. Dữ liệu khuếch đại đã vượt xa mục tiêu "giữ tương quan metadata ↔ vector" của chính fasttrack §3. Ngoài ra A1(1m) trộn nhiều đường thực thi: 427/1000 query đi nhánh exact, và planner còn chọn plan không-HNSW cho nhiều query còn lại. Chỉ bucket b100 (0,748) là số ANN sạch. **Hệ quả: ngưỡng A1 ≥ 0,95 ở 1M của §6 mâu thuẫn với §3 ("số 1M không dùng cho chất lượng tìm kiếm"); không nên dùng A1(1m) làm cổng cho tới khi có vector 1M thật (đối chứng Wikipedia-vi ở §7).**
2. **B1 trượt vì lý do đơn giản, không cần nói tới quá tải:** P99 một client, engine rảnh, cấu hình (b) ở 1M đã là 975 ms — gấp ~10 lần ngưỡng 100 ms; 348/1000 query vượt 100 ms khi không có đồng thời nào. Sức chứa thật ~45 QPS (đo: engine trả kết quả đúng 37,7 query/s ở mức 100 QPS, 44,7 ở mức 200), tải đề nghị 100 QPS ⇒ quá tải gấp đôi. Ba con số phải nói đúng: "8.884 timeout" gộp ba thứ (3.942 engine thực sự hết hạn · 1.594 không bao giờ được gửi vì đã quá hạn khi tới lượt · 3.348 engine trả ĐÚNG nhưng đã chờ ~968 ms trong hàng đợi client); "goodput 1,3 QPS" không phải thông lượng của engine (engine trả đúng 37,7/s); P99 = 1000 ms là trần kẹp, latency thật p50 1.668 ms, p99 2.436 ms.
3. **A1 ở catalog không so được ANN với ANN.** Qdrant 1,0 là brute force (chưa build HNSW), pgvector 1,0 ở b01/b1/b10 là plan exact của planner; chỉ b100 của pgvector (0,968 ở ef=40; 0,992 ở ef=100) và toàn bộ số của pgvectorscale mới là ANN thật. A1 = 0,767 của pgvectorscale là tính chất thật của SBQ 1 bit/chiều + `query_rescore` mặc định 50 — đã dựng lại bằng numpy trên đúng vector và filter đó, không đụng SQL (b10 dest_tax 0,6167 mô hình so với 0,6167 đo). Tham số quyết định là `query_rescore` chứ không phải `query_search_list_size` (sweep 100→400 chỉ đổi a1_min 0,0028); muốn đạt 0,95 ở catalog cần rescore khoảng 900–1200.

## Còn lại / rủi ro

- **Chưa chốt được engine.** Muốn chốt: chạy lại `vb fast --engines qdrant,pgvectorscale` với `fast.max_minutes_per_engine` ≥ 90 (Qdrant cần ~45 phút cho 1M, pgvectorscale ~35–40).
- **Dữ liệu 1M cần sửa trước khi A1(1m) có nghĩa.** Hai cách: (a) đối chứng Wikipedia-vi thật (§7); (b) sửa bước kế thừa metadata của §3 để filter không chọn nguyên cụm (ví dụ gán lại destination/taxonomy độc lập với seed cho một phần bản sao). Nên thêm chỉ số chẩn đoán "hạng không lọc của dòng khớp thứ k" vào `stats.json` của amplify — chính chỉ số này phát hiện ra vấn đề.
- Ngưỡng A1 ≥ 0,95 ở 1M (§6) và câu "không dùng cho chất lượng" (§3) mâu thuẫn nhau; cần chốt lại với người viết spec.
- Chưa sửa con số "~5.000 vector" trong `docs/vector_bench/VECTOR_DB_SELECTION.md` §2 thành 2.897 (ngoài thư mục được phép sửa).
- pgvectorscale: cân nhắc thêm `query_rescore` vào sweep nếu muốn đánh giá công bằng khả năng recall của diskann.
