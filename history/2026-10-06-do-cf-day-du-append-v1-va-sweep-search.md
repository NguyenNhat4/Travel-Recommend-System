# Đo đầy đủ RecSys (engine + toàn bộ CF) trên append-v1 và sweep tham số hybrid search e5-small

- Ngày: 2026-10-06
- Tác giả: người dùng / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Người dùng yêu cầu đo lại đầy đủ, chi tiết các thuật toán CF sau khi làm giàu lịch sử. Bộ dữ liệu người dùng chọn là append-v1 (7.003 profiles), đo trên đủ 4 đề thi. Kết quả phải có bảng so sánh tất cả arm với nhau, đo mọi thứ đo được, và làm thêm các việc search có thể làm ngay. Tiếp nối phần "Đo lại RecSys" của `src/evaluation/reports/eval-2026-10-05-cdp-append-recsys-handoff.md`, vốn bàn giao cho tqanh123; người dùng chọn tự làm.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-06-recsys-append-v1-cf-full.md` — thêm: kết luận, bảng tổng, ablation, grid, caveat, bảng chi tiết từng split (metric, Δ vs engine/mpd có CI, ma trận so cặp, phân khúc), bảng chéo split, override, gate, lệnh tái sinh, phụ lục script.
- `src/evaluation/reports/eval-2026-10-06-search-e5s-hybrid-params.md` — thêm: sweep `min_coverage`, `rrf_k`, `candidate_k`, `lexical_candidate_k`, `lexical_k`, cutoff; CI so cặp các ứng viên; thử filter điểm đến oracle cho `cross_vertical`; phụ lục script.
- `history/2026-10-06-do-cf-day-du-append-v1-va-sweep-search.md` — thêm entry này.
- Runtime ignored (không commit):
  - `bench_out/recsys-append-20261005/vec_append_e5-small.{npy,ids.json,meta.json}` và `catalog-texts.json`.
  - `bench_out/recsys-append-20261005/runs/20261005-append-v1-*` (v5, cf-funnel, cf-raw, ablate-noexcl, gate, nodecay, grid-*, mmr*).
  - `bench_out/recsys-append-20261005/sanity.json`.

## Quyết định

- Đọc trước khi chạy:
  - Report enriched-v1, eval-v2, append handoff, ablation exclusion, algos-v1.
  - `docs/guide/recsys-append-v1-snapshot.md`.
  - `algos_v1.yaml`, plan 10 ngày.
  - History 05/10: enriched, audit CDP.
- Mã phục vụ: FR-REC-01..04, FR-CDP-01/03, FR-SRC-01..04, NFR-PERF-01.
- Không sửa code, config, schema, contract hay PRD. Không ghi primary/staging.
- DB evaluation local `vota_append_eval_20261005` (cổng 55433) đã dựng sẵn từ snapshot. Container `wt-seed-postgres-1` đang tắt nên đã khởi động lại; volume giữ nguyên.
- Vector e5-small cho catalog 14.702 (3.393 search unit):
  - Tái dùng vector enriched-v1 chỉ khi text trùng hệt (2.787); embed mới 606 bằng model cache offline. Guide cấm mặc định tái dùng vector catalog 30/09, nên mỗi vector dùng lại đều đối chiếu text.
  - Kiểm chéo cosine trên 20 text = 1,000.
- Gate G1/G2 đo bằng run pool engine (như `make recsys-gate-run`). So sánh trên pool mask chỉ ghi là thông tin tham khảo (684/774 temporal), vì pool mask cho MMR tập ứng viên khác — đúng errata của spec algos.
- G2 dùng `--tie-tolerant`: 3/9.856 khách lệch thứ tự vì hoà điểm, tập món trùng 100 %.
- So cặp arm nhiều seed dùng trung bình 3 seed của từng khách.
- Grid `W_SHORT/W_POP` giữ `W_LONG` 0,15. Điểm tốt nhất (0,7/0,15) chỉ ghi là đề xuất; đổi engine phải qua `docs/prd/update/` (quy trình M6).
- Search: chọn trên dev, kiểm trên test; mốc là cutoff 0,85 theo đề xuất PRD e5-small đang chờ chốt. Các giá trị đề xuất (`min_coverage` 0,1–0,2, `rrf_k` 30) chưa áp dụng.

## Kiểm tra

- Split đóng băng: 4/4 run khớp hash (llbo `4ec0301b4ffc`, temporal `a4aded77730c`, nexttrip `e99465fef982`, coldstart `0cfc3dfb4b47`). `vectorsMissing 0` mọi run.
- Gate:
  - G1 PASS 774/774, 1835/1835, 4021/4021, 5231/5231.
  - G2 PASS (chế độ bỏ qua hoà điểm).
  - `star_blend_a1 ≡ content_profile` PASS 100 %.
  - engine/mpd/most_popular trùng ids giữa run v5, cf-funnel, cf-raw 100 %.
- `recsys_bench sanity`: 2 FAIL do cách nạp, không phải lỗi dữ liệu.
  - `lifecycle_recomputed`: cột snapshot profile demo cũ được tính ở ngày nạp cũ.
  - `messy_edges`: tỉ lệ bị pha loãng vì 5.000 khách append sạch.
  - Các kiểm tra còn lại PASS. Chi tiết ở report §5.
- Số chính hit@20, engine vs mpd:
  - LLBO +14,00 [+12,63; +15,42].
  - temporal +7,49 [+4,91; +10,08].
  - nexttrip +1,96 [+0,65; +3,27].
  - coldstart +46,93 [+45,54; +48,35].
- Không CF nào vượt engine ở hit@20. `ials` thắng NDCG@10 LLBO (+10,87) nhờ khách có target trong giỏ.
- Grid 0,7/0,15:
  - NDCG@10 tăng: temporal +2,68, LLBO +1,17, coldstart +19,98.
  - Hit@20 của list 20 món giảm ở LLBO: −1,84.
- Search: `min_coverage 0,1 + rrf_k 30` gộp 128 câu +2,48 [+0,29; +4,92] nDCG@10; test riêng +1,84 [−0,73; +4,96].
- Không chạy unit test vì không sửa code. Không chạy `validate_contract.py` vì không đổi contract hay mock.

## Còn lại / rủi ro

- p95 ms trong report RecSys bị nhiễu do 4–8 tiến trình chạy song song; không dùng để so latency.
- Đề xuất trọng số engine (`W_SHORT` 0,7 / `W_POP` 0,15) và tham số search (`min_coverage`, `rrf_k`) cần đề xuất PRD/spec và người dùng chốt trước khi sửa code.
- Search: các cấu hình mới đưa lên top-10 sản phẩm chưa có nhãn (judged@10 giảm khoảng 1 điểm), cần gán nhãn trước khi chốt.
- Nexttrip vẫn là khoảng trống: engine 0,080 trên trần 0,947.
- Tín hiệu giỏ bỏ dở (`ials`) chưa được engine khai thác.
- Script tổng hợp chỉ nằm trong phụ lục report, không đưa vào `src/`.
- Chưa commit/push.
