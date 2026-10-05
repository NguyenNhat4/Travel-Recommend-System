# Đồng bộ danh sách prewarm và câu latency cold với gold_v4

- Ngày: 2026-10-05
- Tác giả: tqanh123 / Claude Code
- Nhánh: `feat/gold-v4`
- Trạng thái: hoàn thành
- Phạm vi: evaluation, backend (dữ liệu prewarm + test)
- Phục vụ: FR-SRC-01, NFR-PERF-01 (đo latency đường nóng), test-plan §2.5

## Mục tiêu

Rebase commit gold_v4 (`history/2026-10-05-gold-v4a-tao-gold-v4.md`) lên `origin/bench_search_recomSys` mới nhất trước khi mở PR thì hai test đỏ: danh sách prewarm của backend phải bằng tập câu gold active, và câu "cold" của bench latency không được nằm trong gold. Gold_v4 thêm 23 câu active nên cả hai phải đồng bộ lại theo quy ước đã ghi trong chính các file đó ("sinh lại khi gold đổi tag"; "muốn thêm câu thì thêm vào cold").

## File thay đổi

- `src/backend/data/search_prewarm_queries.txt` — sửa: sinh lại cho gold_v4 — header `# gold_v4 721f164d… 2026-10-05 — 154 câu …`, thân là 154 câu gold active theo thứ tự `gold.jsonl` (131 câu cũ giữ nguyên thứ tự + 23 câu mới). Backend nạp sẵn thêm 23 vector truy vấn lúc khởi động.
- `src/backend/tests/unit/application/test_search_prewarm.py` — sửa: `test_frozen_prewarm_list_is_well_formed` nhận `gold_vN` bất kỳ và lấy số câu từ header thay vì cố định `gold_v1` / 131 — file phải sinh lại mỗi lần gold đổi tag nên test không được ghim một tag.
- `src/evaluation/search_bench/config/latency_queries.yaml` — sửa: câu cold "vé máy bay đi Côn Đảo" trùng câu gold_v4 `c0721` → thay bằng "vé máy bay đi Quy Nhơn" (cùng dạng câu vé bay chỉ có điểm đến, không có trong gold, không có trong nhóm prewarmed).
- `history/2026-10-05-prewarm-latency-theo-gold-v4.md` — entry này.

## Quyết định

- Giữ nguyên định dạng và thứ tự cũ của file prewarm (thứ tự `gold.jsonl`); sha trong header là sha của `gold.jsonl` hiện tại — khớp blob khi người dùng tag `gold_v4` trên commit có file này (test `test_prewarm_list` chỉ kiểm sha khi tag đã có).
- Đổi câu cold thay vì đổi câu gold: gold đã import, đổi chữ câu gold phải dựng lại pool. Report latency cũ (`eval-2026-10-01-search-cloud-latency.md`) đo trên bộ cold có câu Côn Đảo — so sánh nhóm cold với report đó lệch 1 / 25 câu.

## Kiểm tra

- `pytest evaluation/search_bench/tests`: 386 passed, 11 skipped (trước sửa: 2 failed — `test_prewarm_list_matches_gold_active_of_its_tag`, `test_latency_queries_prewarmed_in_gold_and_cold_outside`).
- `pytest backend/tests/unit/application/test_search_prewarm.py`: 5 passed (test mới chạy được cả với file `gold_v1` cũ lẫn file `gold_v4`).

## Còn lại / rủi ro

- Backend đang chạy ở môi trường nào thì lần khởi động sau nạp sẵn thêm 23 câu (23 lượt embed Cohere).
