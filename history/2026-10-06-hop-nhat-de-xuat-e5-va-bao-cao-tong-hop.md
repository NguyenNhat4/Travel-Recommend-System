# Hợp nhất đề xuất e5-small, đo lại đề xuất search trên gold_v4 cùng F1/F2/QP, gộp báo cáo tổng hợp RecSys + Search

- Ngày: 2026-10-06
- Tác giả: người dùng / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu ba việc:

1. Gộp hai đề xuất đổi model e5-small bị trùng, xoá một bản.
2. Gộp RecSys và Search thành một báo cáo lớn, chi tiết.
3. Đo lại đề xuất search sau khi PR #108 được merge: gold_v4, F1/F2/QP, mốc cutoff 0,84.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-06-recsys-search-tong-hop.md` — thêm. Gồm:
  - Tóm tắt.
  - Phần A RecSys: nguyên văn report RecSys 06/10.
  - Phần B1: đo lại search trên gold_v4.
  - Phần B2–B3: nguyên văn report search 06/10.
  - Phần C: đề xuất và việc tiếp.
  - Phụ lục 1–6: script.
- `src/evaluation/reports/eval-2026-10-06-recsys-append-v1-cf-full.md` — xoá, gộp vào báo cáo tổng hợp phần A.
- `src/evaluation/reports/eval-2026-10-06-search-e5s-hybrid-params.md` — xoá, gộp vào báo cáo tổng hợp phần B2–B3.
- `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md` — sửa (hợp nhất). Bổ sung:
  - So e5-small với Cohere cùng thang trên pipeline APP: Δ condensed +0,42, TIE.
  - Bằng chứng RecSys; kích thước vector.
  - Câu chữ thay thế PRD chi tiết: architecture, data-model, project-brief, implementation-plan.
  - `SEARCH_CUTOFF` 0,84 kèm bằng chứng gold_v4; `lexicalCutoff` 0,50.
  - Rủi ro; các file source còn nhắc Cohere.
- `docs/prd/update/2026-10-05-doi-embedding-e5-small.md` — xoá. Đây là bản trùng, chưa từng commit; nội dung đã gộp vào bản trên.
- `docs/prd/update/2026-10-06-search-hybrid-min-coverage-rrf.md` — sửa: viết lại theo số gold_v4. Đề xuất dùng A cùng F1 + F2, cutoff 0,84; nêu điều kiện khi bật QP.
- `docs/prd/update/2026-10-06-recsys-trong-so-ngan-han-pho-bien.md` — sửa: trỏ nguồn sang báo cáo tổng hợp.
- `history/2026-10-05-de-xuat-prd-embedding-e5-small.md` — thêm dòng "Bị thay thế bởi" (entry chưa từng commit, nay commit cùng).
- `history/2026-10-06-hop-nhat-de-xuat-e5-va-bao-cao-tong-hop.md` — thêm entry này.
- Working tree, **không commit** vì hai file đang có thay đổi dở của người dùng: `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` (dòng 166) và `src/evaluation/reports/report_week_3_search.md` (dòng 91). Tham chiếu tới bản đề xuất đã xoá được đổi sang bản hợp nhất; tham chiếu cũ chỉ nằm trong phần chưa commit.

## Quyết định

- Giữ bản `fr-src-02` vì đã commit (nhóm Search) và được plan trỏ tới. Bản local chỉ đóng góp các phần bản kia thiếu.
- Cutoff e5 chọn 0,84 thay 0,85 của bản local: trên gold_v4, hai giá trị như nhau ở mọi tổ hợp, nhưng ở mốc không bật cờ thì 0,85 làm 1,4 % câu trả rỗng còn 0,84 là 0 %. Trùng mốc nhóm Search đang dùng.
- Cách chia câu khi đo lại (gold_v4 chưa có tag và chưa có split riêng):
  - Dùng phân công `devtest@gold_v3` cho 131 câu cũ.
  - Tách 19 câu mới có đáp án thành nhóm `v4new`, không dùng khi chọn tham số.
  - Chạy với `allow_untagged`.
- Đề xuất search viết lại theo kết quả B1: A bổ sung cho F1 + F2, không trùng; khi bật QP thì A gần như không cộng thêm.
- Report cũ được xoá, không giữ song song, theo yêu cầu "một báo cáo lớn". History 06/10 trước đó vẫn trỏ đường dẫn cũ (không sửa entry cũ); entry này ghi việc thay thế.

## Kiểm tra

- `search_v4.py` (Phụ lục 6), commit `a46c424`: 20 cấu hình (10 × cutoff 0,84 / 0,85) × 154 câu; chạy xong, 0 lỗi.
- Số chính: F1 + F2 + A so với mốc c84, tổng 147 câu +4,14 [+2,19; +6,24]; test +4,06 [+1,09; +7,41].
- A cộng thêm trên F1 + F2: +1,23 [+0,60; +1,93]. Trên F1 + F2 + QP: +0,46 [−0,14; +1,15].
- Kiểm báo cáo:
  - Không còn placeholder.
  - Heading trong code block không bị hạ cấp.
  - 6 phụ lục đủ.
  - `grep` không còn tham chiếu tới bản đề xuất đã xoá trong các file sẽ commit.
- Không chạy test vì không đổi code.

## Còn lại / rủi ro

- gold_v4 chưa gắn tag; split dev/test riêng cho gold_v4 chưa có.
- QP cần gán nhãn lỗ trước khi chốt.
- Ba đề xuất vẫn chờ người dùng/nhóm chốt.
