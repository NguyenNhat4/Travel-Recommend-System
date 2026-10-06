# Chốt tham số hybrid `/search` cho e5-small: `lexicalMinCoverage` 0,6 → 0,1 và RRF `k` 60 → 30 (dùng cùng F1 + F2)

- Ngày: 2026-10-06
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: không đổi câu chữ (`docs/prd/requirements.md` §1.2 không ghi các tham số này). Giá trị đang nằm ở
  `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.4 và mục S9 "chưa benchmark" §10. Đổi chúng làm đổi kết quả tìm kiếm người
  dùng thấy, nên đưa ra để nhóm chốt. **Phụ thuộc** đề xuất đổi model `2026-10-05-fr-src-02-embedding-local-e5-small.md`: chỉ áp dụng khi
  đã đổi model.
- Mã FR/NFR: FR-SRC-01, FR-SRC-02, FR-SRC-03 (dùng cùng F1)

## Lý do

Đo lại 06/10 trên **gold_v4** (154 câu đang dùng, chưa gắn tag) bằng đúng `SearchProducts` của backend. Mốc là arm
`APP.e5s.hybrid_norm_c84` của nhóm Search (cutoff 0,84); F1 / F2 / QP là các cờ của PR #108. Nguồn:
`src/evaluation/reports/eval-2026-10-06-recsys-search-tong-hop.md` phần B1. Nhóm câu:

- **dev / test**: phân công `devtest@gold_v3`. Giá trị A được chọn trên dev.
- **v4new**: 19 câu mới của gold_v4 có đáp án, không dùng khi chọn, nên là tập kiểm tra độc lập.

Δ nDCG@10 so với mốc, điểm ×100, CI95 paired bootstrap 10.000 lượt (**đậm** = CI không chứa 0):

| Cấu hình (cutoff 0,84) | dev (65) | test (63) | v4new (19) | Tổng (147) | condensed tổng | judged@10 |
|---|---|---|---|---|---|---:|
| A = `minCoverage 0,1` + `rrf 30` | **+2,72** | **+1,89** | +0,98 | **+2,14** [+0,81; +3,64] | **+2,17** | 0,858 |
| F1 + F2 (đang có cờ) | **+3,80** | +2,56 | +0,99 | **+2,90** [+1,01; +4,95] | **+3,26** | 0,829 |
| **F1 + F2 + A** | **+5,07** | **+4,06** | +1,17 | **+4,14** [+2,19; +6,24] | **+4,41** | 0,850 |
| F1 + F2 + QP | +2,97 | +3,03 | **+9,03** | **+3,78** [+1,18; +6,53] | **+5,35** | 0,797 |
| F1 + F2 + QP + A | +3,45 | +3,64 | **+8,93** | **+4,24** [+1,60; +7,00] | **+5,49** | 0,799 |

- **A cộng thêm trên F1 + F2:** +1,23 [+0,60; +1,93] tổng, có ý nghĩa riêng ở dev (+1,27) và test (+1,50). Hai cơ chế bổ sung nhau, không
  trùng lặp:
  - F2 nới cho câu không dấu; `minCoverage` thấp vớt thêm ở mọi câu.
  - F1 lọc điểm đến; `rrf 30` kéo `cross_vertical` 0,554 → 0,614.
- **Khi bật QP (F3–F6)**, A chỉ cộng thêm +0,46 [−0,14; +1,15], vì QP đã xử lý phần lớn câu mà A giúp. QP tăng mạnh 19 câu mới (+9) nhưng
  judged@10 giảm còn 0,80 (nhiều kết quả chưa nhãn) và còn đang chờ nhãn lỗ `amenity_negation`.
- **Cutoff:** 0,84 và 0,85 cho kết quả như nhau ở mọi tổ hợp (Δ ≤ 0,23, CI chứa 0). Riêng mốc không bật gì, 0,85 làm 1,4 % câu trong
  catalog trả rỗng, còn 0,84 thì 0 %. Đề xuất theo cutoff **0,84** của nhóm Search.
- Slice: với F1 + F2 + A, `no_diacritics` 0,381 → 0,569, `cross_vertical` 0,556 → 0,614, `named_entity` 0,820 → 0,862, `audience_style`
  0,633 → 0,718. Riêng A (không F1) làm `audience_style` −2,3; F1 bù lại.
- Không thay đổi: 7 câu ngoài catalog vẫn có kết quả ở mọi cấu hình. Cutoff tuyệt đối không giải quyết được, cần cơ chế khác.

Số gold_v3 trước đó (cutoff 0,85, không F1/F2) cùng hướng: A gộp 128 câu +2,48 [+0,29; +4,92] (report phần B2).

## Nội dung đề xuất

**`docs/prd/`:** không đổi.

**`docs/spec/hop-dong-tich-hop-search-recommendation.md`** (sửa sau khi chốt, cùng lúc với đề xuất e5-small):

- §2.4: `lexicalMinCoverage: 0.6, fusion: rrf(60)` → `lexicalMinCoverage: 0.1, fusion: rrf(30)`. Ghi rằng giá trị đo cùng `destFilter: true`,
  `noDiacriticsMode: relax` (cutoff riêng 0,80).
- §10 S9: đổi "chưa benchmark" thành đã đo, trỏ report trên. Giữ `lexicalK` 10 và `lexicalCutoff` 0,50.

Điều kiện chốt:

1. Bật F1 + F2 trên production cùng lúc với thay đổi này.
2. Nếu chốt bật cả QP, A không còn lợi ích có ý nghĩa: có thể giữ A (không hại) hoặc bỏ.
3. Gắn tag `gold_v4` rồi đặt lại `baseline_v1` theo cấu hình được chốt.

## Thay đổi source sau khi chốt

- `src/backend/app/core/config.py`: `search_lexical_min_coverage` 0.6 → 0.1, `search_rrf_k` 60 → 30, cùng với cờ F1/F2 đã chốt (biến môi
  trường trong `.env.example`, và `docs/prd/deployment-plan.md` §2 nếu ghi giá trị).
- Bench: thêm arm `APP.e5s.hybrid_norm_c84_dest_nodia_nc80_mc10_rrf30` (yaml trong `src/evaluation/search_bench/arms/`, cập nhật
  `docs/spec/bench/arms.md`); `sb regress baseline` trên gold_v4 đã gắn tag; test backend `/search`.
