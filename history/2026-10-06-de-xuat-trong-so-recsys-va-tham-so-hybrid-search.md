# Đề xuất chốt trọng số điểm RecSys và tham số hybrid search từ kết quả đo 06/10

- Ngày: 2026-10-06
- Tác giả: người dùng / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành (đề xuất chờ chốt)
- Phạm vi: docs, evaluation

## Mục tiêu

Người dùng đồng ý soạn đề xuất từ kết quả đo trong `history/2026-10-06-do-cf-day-du-append-v1-va-sweep-search.md`, để nhóm chốt trước khi sửa engine hoặc config.

## File thay đổi

- `docs/prd/update/2026-10-06-recsys-trong-so-ngan-han-pho-bien.md` — thêm: đề xuất `W_SHORT/W_POP/W_LONG` 0,6/0,25/0,15 → 0,7/0,15/0,15, trạng thái chờ chốt.
- `docs/prd/update/2026-10-06-search-hybrid-min-coverage-rrf.md` — thêm: đề xuất `lexicalMinCoverage` 0,6 → 0,1 và `rrf` 60 → 30 cho `/search` e5-small, trạng thái chờ chốt, phụ thuộc đề xuất e5-small.
- `history/2026-10-06-de-xuat-trong-so-recsys-va-tham-so-hybrid-search.md` — thêm entry này.

## Quyết định

- PRD không ghi giá trị các tham số này:
  - Trọng số engine: FR-REC-04 chỉ nói "trọng số kết hợp".
  - Tham số search: nằm ở spec §2.4 và §10 S9.
- Thay đổi vẫn đổi hành vi người dùng thấy, nên được đưa qua `docs/prd/update/` để nhóm review, theo kết luận của report đo.
- Không sửa `docs/prd/`, spec, code hay config. AGENTS.md §8: chỉ người dùng chốt; chưa chốt thì không sửa source.
- Đề xuất search chỉ áp dụng sau đề xuất e5-small `2026-10-05-fr-src-02-embedding-local-e5-small.md`, và cần gán nhãn các cặp mới vào top-10 trước khi chốt số.
- Khi push gặp PR #108 (F1 lọc điểm đến, F2 cutoff riêng cho câu không dấu, mốc cutoff 0,84, gold_v4) đã merge vào nhánh. Đề xuất và report search ghi thêm phần chồng lấn, kèm điều kiện đo lại trên gold_v4 cùng F1/F2 trước khi chốt.

## Kiểm tra

- Số trong đề xuất chép từ:
  - `src/evaluation/reports/eval-2026-10-06-recsys-append-v1-cf-full.md` §4, §6.
  - `src/evaluation/reports/eval-2026-10-06-search-e5s-hybrid-params.md` §1–2.
- Không chạy test vì không đổi code.

## Còn lại / rủi ro

- Chờ người dùng/nhóm chốt hai đề xuất. Sau khi chốt, sửa source và spec theo mục "Thay đổi source sau khi chốt" của từng đề xuất.
- Phần chốt trọng số còn phải kiểm lại AC-REC-01/02 (P1, P3).
