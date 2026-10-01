# Bench: test đối chiếu danh sách prewarm của backend với gold active

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation (search_bench tests)

## Mục tiêu

PR cache + prewarm của backend (`feat/search-embed-cache`, contract 1.12.0) đóng băng 131 câu gold active vào
`src/backend/data/search_prewarm_queries.txt` (header `# gold_v1 <sha256 gold.jsonl> <ngày>`). Evaluation được phụ thuộc
backend, không ngược lại, nên phép kiểm "file prewarm = gold active của tag" đặt ở search bench.

## File thay đổi

- `src/evaluation/search_bench/tests/test_prewarm_list.py` — thêm: đọc file prewarm (skip nếu chưa có trên nhánh — PR cache
  chưa gộp), kiểm header, sha256 blob `gold.jsonl` ở tag khớp header, tập câu (sau gộp khoảng trắng) = gold active, không trùng.

## Quyết định

- Skip thay vì fail khi thiếu file: nhánh bench chưa chứa PR cache; sau khi gộp `release-mvp-v2` về, test tự chạy thật.
- So theo `canonical` (gộp khoảng trắng) đúng khoá cache của backend; không fold hoa/thường/dấu.

## Kiểm tra

- Trên nhánh này: `pytest evaluation/search_bench/tests/test_prewarm_list.py` → 1 skipped (đúng thiết kế).
- Chép tạm file từ worktree PR2 vào `src/backend/data/` rồi chạy lại → **1 passed** (131 câu = gold active của `gold_v1`,
  sha `e47b0d6a…`); đã xoá bản chép, cây làm việc sạch.

## Còn lại / rủi ro

- Gold đổi tag (`gold_v2`) thì phải sinh lại file prewarm ở backend; test này sẽ fail để nhắc.
