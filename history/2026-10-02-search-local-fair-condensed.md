# So 5 model embedding local trên cùng thang đo (condensed-deep)

- Ngày: 2026-10-02
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành
- Phạm vi: evaluation
- Phục vụ: FR-SRC-01..04, AC-SRC-01

## Mục tiêu

Report Day 4–5 xếp e5-base đứng đầu với khoảng cách 6–11 điểm nDCG, nhưng chỉ e5-base có Judged@10 = 1,000; bốn model local còn lại thiếu 20–28% nhãn top-10 và bị tính rel = 0 cho phần đó. Người dùng yêu cầu so 5 model local trên cùng một thang đo, không bù thêm nhãn.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-02-search-local-fair.md` — thêm: report condensed-deep cho 5 model local, giải thích ba cách chấm (full, condensed nông, condensed-deep), paired bootstrap 10 cặp, slice, tập con kiểm chứng 18 câu, giới hạn, xếp hạng khuyến nghị và script tái sinh (phụ lục).
- `history/2026-10-02-search-local-fair-condensed.md` — entry này.

## Quyết định

- Dùng condensed-deep (Sakai 2007): mỗi model xếp hạng cả 3.183 vector bằng cosine chính xác, giữ sản phẩm đã có nhãn gold_v3, lấy top-10 → mọi model Judged = 1,0 trên cùng tập ứng viên. Không bù nhãn, không đổi gold.
- Dùng lại `metrics.recall_at_k/ndcg_at_k/mrr_at_k`, `paired_bootstrap` (1.000 lần, seed 42) và `win_verdict` với `win_rule` của `config/sbench.yaml` để số so được với bench.
- Script để ở phụ lục report, không thêm lệnh vào `search_bench` (chưa được yêu cầu).
- Kết luận: e5-small, e5-base, BGE-M3, GTE hòa thống kê; e5-large-instruct kém có ý nghĩa so với e5-small và BGE-M3. Khuyến nghị e5-small/384 (chi phí thấp nhất), e5-base dự phòng. Không đổi engine, không sửa PRD (FR-SRC-02 vẫn Cohere v3; đổi cần đề xuất `docs/prd/update/`).

## Kiểm tra

- Script chạy trên `vsf2`: top-10 tính lại khớp `per_query.parquet` của run `20261002-day5-local-ranking` **131/131 câu ở cả 5 model**; bảng full trùng report Day 4–5 §5.
- Không chạy test suite (không đổi code trong `src/evaluation/search_bench`).

## Còn lại / rủi ro

- Condensed-deep có thiên lệch có lợi cho model ngoài pool; chênh +1,3 đến +1,6 điểm của e5-small/BGE so với e5-base không được coi là thắng.
- Chưa đo e5-small qua pipeline APP/HTTP end-to-end; chưa có latency API cho NFR-PERF-01.
- Report Day 4–5 vẫn giữ xếp hạng cũ; report này bổ sung, không sửa report cũ.
