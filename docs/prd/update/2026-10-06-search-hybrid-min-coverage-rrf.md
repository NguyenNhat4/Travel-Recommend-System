# Chốt tham số hybrid `/search` cho e5-small: `lexicalMinCoverage` 0,6 → 0,1 và RRF `k` 60 → 30

- Ngày: 2026-10-06
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: không đổi câu chữ (`docs/prd/requirements.md` §1.2 không ghi các tham số này). Giá trị đang nằm ở
  `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.4 và mục S9 "chưa benchmark" §10; đổi chúng làm đổi kết quả tìm kiếm người dùng
  thấy, nên đưa ra để nhóm chốt. **Phụ thuộc** đề xuất đổi model `2026-10-05-fr-src-02-embedding-local-e5-small.md` — chỉ áp dụng khi đã đổi
  model; và phải đối chiếu với F1/F2 của nhánh `fix/search` (mục "Quan hệ với F1/F2" dưới) trước khi chốt.
- Mã FR/NFR: FR-SRC-01, FR-SRC-02

## Lý do

Đo bằng đúng code `/search` của backend (hybrid + chuẩn hoá, e5-small, cutoff 0,85) trên gold 131 câu, chọn trên nửa dev, kiểm trên nửa test
(`src/evaluation/reports/eval-2026-10-06-search-e5s-hybrid-params.md`):

| Cấu hình so với hiện tại | nDCG@10 dev (65) | nDCG@10 test (63) | nDCG@10 cả bộ (128) | Kết quả rỗng | Câu không dấu |
|---|---|---|---|---|---|
| `minCoverage 0,1` | +2,59 [−0,53; +6,43] | +1,59 [−0,77; +4,55] | **+2,10** [+0,03; +4,44] | 1,6 % → 0 % | 0,28 → 0,58 |
| `rrf 30` | +0,85 [−0,09; +2,06] | +0,58 [−0,18; +1,45] | **+0,72** [+0,10; +1,45] | không đổi | không đổi |
| **`minCoverage 0,1` + `rrf 30`** | +3,09 [−0,20; +7,05] | +1,84 [−0,73; +4,96] | **+2,48** [+0,29; +4,92] | 1,6 % → 0 % | 0,28 → 0,59 |

- `lexicalMinCoverage` là tỉ lệ từ của truy vấn phải có trong tên sản phẩm thì kết quả BM25 mới được "vớt" vào danh sách. 0,6 chặn gần hết
  câu gõ không dấu / sai chính tả; 0,1–0,2 vớt được mà không làm hỏng các nhóm câu khác (trừ `audience_style` −5,6 điểm, 11 câu).
- `rrf` nhỏ hơn làm thứ hạng đầu của từng nhánh nặng hơn; giúp nhóm câu hỏi nhiều loại sản phẩm (`cross_vertical`) 0,58 → 0,63 — nhóm mà
  e5-small đang kém Cohere 26 điểm.
- Các tham số khác giữ nguyên (đã đo): `candidateK` 200, `lexicalCandidateK` 50, `lexicalK` 10, `lexicalCutoff` 0,50, cutoff 0,85.

Điều kiện trước khi áp dụng: nửa test riêng chưa có CI cắt 0 (63 câu), và cấu hình mới đưa vào top-10 một số sản phẩm chưa gán nhãn
(judged@10 giảm ~1 điểm). Cần gán nhãn các cặp này, chấm lại, rồi mới chốt số.

## Quan hệ với F1/F2 (PR #108, `src/evaluation/reports/eval-2026-10-05-search-e5s-dest-nodia.md`)

Nhóm Search đã thêm hai cơ chế bằng cờ, mặc định tắt: F1 lọc điểm đến suy từ câu (`SEARCH_DEST_FILTER`) và F2 cho câu không dấu với cutoff
riêng 0,80 (`SEARCH_NO_DIACRITICS_*`), trên mốc cutoff tạm **0,84** (arm `*_c84`). Số trong đề xuất này đo **không bật F1/F2**, cutoff
**0,85**, gold_v3, nên chồng lấn:

- `lexicalMinCoverage` thấp và F2 cùng nhắm câu không dấu. Report F2 ghi rằng khi không có cutoff, nới `min_coverage` không đổi top-10. Ở đây,
  với cutoff 0,85, nó có tác dụng: hai kết quả nhất quán, vì tham số chỉ có nghĩa khi cutoff cắt bớt nhánh dense. Cần chọn **một** cơ chế,
  hoặc đo tổ hợp.
- `rrf 30` và F1 cùng giúp `cross_vertical`; filter điểm đến oracle đo ở report của đề xuất này tăng +7,35 nhưng CI chứa 0.

Trước khi chốt: đo lại trên **gold_v4** (đã merge) với cutoff đã chọn cho đề xuất model, so `min_coverage 0,1 + rrf 30` với F1 + F2 và
tổ hợp cả hai trên split dev/test.

## Nội dung đề xuất

**`docs/prd/`:** không đổi.

**`docs/spec/hop-dong-tich-hop-search-recommendation.md`** (đổi sau khi chốt, cùng lúc với đề xuất e5-small):

- §2.4: `lexicalMinCoverage: 0.6, fusion: rrf(60)` → `lexicalMinCoverage: 0.1, fusion: rrf(30)`.
- §10 S9: đổi "chưa benchmark" thành đã đo, trỏ report trên; giữ `lexicalK` 10 / `lexicalCutoff` 0,50.

## Thay đổi source sau khi chốt

- `src/backend/app/core/config.py`: `search_lexical_min_coverage` 0.6 → 0.1, `search_rrf_k` 60 → 30 (và biến môi trường tương ứng trong
  `docs/prd/deployment-plan.md` §2 nếu đang ghi giá trị).
- Bench: `src/evaluation/search_bench/arms/APP.e5s.*.yaml` thêm arm cấu hình mới; gán nhãn cặp mới, `sb rescore`, đặt lại `baseline_v1` +
  `sb regress`; test backend `/search`.
