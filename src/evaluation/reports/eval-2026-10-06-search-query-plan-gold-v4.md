# Search bench 06/10 — query plan F1–F6 và phần còn thiếu của kiến trúc (fuzzy, số khách, dấu thanh, RRF trọng số, rerank offline) trên gold_v4 + nhãn hole

- Ngày chạy và viết: **06/10/2026**. Phục vụ **FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01**, NFR-PERF-01; kiến trúc
  `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` (Phase A, B, D offline).
- Nhánh `fix/search-gold-v4`, HEAD `a46c424`; code của report ở working tree **chưa commit** —
  `history/2026-10-06-search-query-plan-v116-fuzzy-party-tone.md`, `history/2026-10-06-search-bench-ablation-gold-v5.md`,
  `history/2026-10-06-search-gold-v5-hole-d9a-va-chu-giai-cau.md`. Contract **1.16.0**.
- Run: `2026-10-06-gold-v4-r1` (21 arm, mã trước sửa — chỉ dùng sinh hole D9a và kiểm identity) và **`2026-10-06-gold-v4-r2`** (45 arm
  `APP.e5s.*`, mã cuối — mọi bảng dưới đây). Collection `ProductBench__e5_small` (3.183 unit, hnsw, `intfloat/multilingual-e5-small`,
  384 chiều), Weaviate bench Docker local, vector truy vấn từ cache embed (0 lượt model mới), **không Cohere, không HTTP**.
- Gold: `gold/gold.jsonl` **chưa tag** = `gold_v4` (5.666 nhãn) + **1.924 nhãn máy chưa duyệt** (hole D9a 829 + 56 auto_ooc, D9b 871 + 60,
  D9c 69 + 9, D9d 14, D9e 16; provenance `holes:<đợt>:machine_unreviewed@gold_v5`), 154 câu active, 7.590 nhãn, SHA-256
  `7107a91a9de3b361af706bf0968fc30019c3cc258d801142da9e130eb33ae9e5`. **Judged@10 = 1,00 cho cả 45 arm** (mọi kết quả top-10 đều có nhãn).
- Split `gold/splits/devtest@gold_v4.json` (seed 42, phân tầng slice, dev 77 / test 77). Hai rubric: khối **v3** (131 câu gold_v1–v3) và
  khối **v4** (23 câu từ c0673, sai loại cốt lõi = 0) — báo riêng, không trộn khi trích dẫn.
- Win rule của bench (`config/sbench.yaml`): WIN khi Δrecall@10 ≥ 2,0 điểm, p < 0,05 và không slice nào tụt > 3,0; TIE khi |ΔnDCG| < 2,0;
  còn lại in "LOSE". Bảng ghi **"không thắng (lý do)"** thay "LOSE" khi nDCG tăng nhưng trượt một điều kiện (thường là Δrecall < 2 —
  thay đổi chỉ sắp lại thứ tự). Mốc **A** = `APP.e5s.hybrid_norm_nocut` (hybrid + normalize production, cutoff −1).

## 1. Kết luận ngắn

1. **Ứng viên production `F1–F6` (`APP.e5s.hybrid_norm_nocut_f1f6`): nDCG@10 0,807 so mốc 0,707 — WIN (Δrecall +4,21, p 0,001)**, cả
   khối v3 (+7,0) lẫn v4 (+29,6). Đủ mọi guard Phase A: Forbidden@10 **0,539 → 0**, chiều bay **0,11 → 1,00**, constraint precision **0,79 →
   0,96**, zero-result trong catalog 0. Thành phần: F1 điểm đến + F2 câu không dấu + F3 phủ định + F4 loại sản phẩm (mọi cue) + F5 tuyến
   bay + F6 giá/sao; không cutoff, không party / tone / fuzzy.
2. **Dev / test:** dev **WIN** (+9,3 nDCG, Δrecall +4,84); test ΔnDCG **+10,6**, Δrecall +3,58 (p 0,014) nhưng *không thắng theo luật*
   vì slice `flight_direction` trên test (n = 3) tụt 6,0 — F4 lọc về `flight` loại combo vé khứ hồi mà rubric v4 cho 1.
3. **Từng phần (trên mốc A):** F1 **WIN** (+3,8); F3 +4,5 (Δrecall +1,96 — sát ngưỡng; `amenity_negation` 0,316 → 0,776, Forbidden
   0,539 → 0,225); F4 +1,6 TIE (`taxonomy_collision` 0,641 → 0,859); F5 +0,2 TIE nhưng chiều bay 0,11 → 1,00; F6 +0,7 TIE nhưng constraint
   precision 0,79 → 0,92; F2 = 0 khi không cutoff (đúng thiết kế). Leave-one-out từ ALL: bỏ F1 **LOSE** (−2,1), bỏ F3 **LOSE** (−5,2);
   bỏ F4 / F5 / F6 TIE về nDCG **nhưng làm hỏng guard** (Forbidden 0,065 / 0,210 + chiều 0,11 / constraint precision 0,79) → cả ba cần giữ.
4. **Phần mới của kiến trúc đều trung tính trên gold này — giữ tắt:** party −0,4 (bỏ khỏi ALL +0,8), tone 0,0 (gold không có câu lệch kiểu
   dấu), fuzzy −0,5 (0,75) / −1,2 (0,6), F4 chỉ cue mạnh −1,0 so F4 đủ. **RRF trọng số lexical 0,5**: +1,7 trên A, +1,2 trên F1–F6 (TIE
   cả dev lẫn test, cùng chiều) — ứng viên tinh chỉnh sau. Dense 0,5: −2,6 LOSE. Lexical-only −11,8, dense-only −4,4, hybrid không
   normalize −2,9 so mốc.
5. **Rerank offline `BAAI/bge-reranker-v2-m3` top-30:** trên F1–F6 nDCG **0,845** (+3,8 so F1–F6; dev +3,5, test +4,1) — không thắng theo
   luật vì gần như không đổi recall@10 (chỉ sắp lại). Chi phí CPU ~3,4 s/câu (cold, laptop) → **chỉ offline**; online cần GPU / model nhỏ
   (kiến trúc Phase D).
6. **Cutoff tuyệt đối không dùng được trên e5** (ALL + 0,84: TIE, 7/7 câu ngoài catalog vẫn có kết quả). Thay bằng luật **kết quả yếu
   theo margin** (§3.4 contract, client sở hữu): margin **0,058** chọn trên dev chặn 3/3 câu ngoài catalog (dev) và **4/4 (test)**, gắn weak
   nhầm 7/74 (dev) · 9/73 (test); ngưỡng tạm 0,06 của contract nhầm 10/74 · 12/73.
7. **Hai lỗi engine bench bắt được và đã sửa trong đợt này:** (a) kênh fuzzy đưa cả top-50 vào RRF dù dưới ngưỡng (−7,6 → −0,5 sau sửa);
   (b) parse accuracy bỏ sót 23/154 câu không có `queryPlan` — đo lại đủ 154: taxonomy 0,924 → **0,992** sau ba sửa parser (cue trong tên
   sản phẩm đúng loại unit, "có <cue> nào", cue "hotel" / "điểm vui chơi").

## 2. Bảng benchmark (run `2026-10-06-gold-v4-r2`, gold chưa tag 7.590 nhãn, Judged@10 = 1,00)

Cột: nDCG@10 full; Δ so A (điểm %); win rule so arm cha (cha = A trừ khi ghi "vs …"); nDCG condensed; R@10; nDCG theo khối rubric v3 / v4 và
theo split dev / test; Forbidden@10 (micro, 28 câu có `forbidden_filter`); chiều bay (direction accuracy, 9 câu vé máy bay); constraint
precision (23 câu có ràng buộc); `filter_recall_loss` (số nhãn ≥ 1 bị filter loại — phần lớn là nhãn 1 "đúng nơi sai loại" của rubric v3
#2); độ trễ engine `SearchProducts` p50 / p95 ms trên Weaviate local (không phải HTTP, không gồm embed vì cache). Tên arm bỏ tiền tố `APP.e5s.`.


**Mốc truy xuất**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dense_nocut | 0.664 | -4.4 | LOSE | 0.664 | 0.303 | 1.00 | 0.685 | 0.520 | 0.690 | 0.636 | 0.507 | 0.00 | 0.80 | 0 | 28 / 44 |
| hybrid_nocut | 0.679 | -2.9 | LOSE | 0.679 | 0.300 | 1.00 | 0.709 | 0.478 | 0.707 | 0.650 | 0.554 | 0.11 | 0.80 | 0 | 56 / 86 |
| A = hybrid_norm_nocut | 0.707 | +0.0 |  | 0.707 | 0.316 | 1.00 | 0.734 | 0.528 | 0.724 | 0.691 | 0.539 | 0.11 | 0.79 | 0 | 60 / 89 |
| hybrid_norm_nocut_lexonly | 0.589 | -11.8 | LOSE | 0.589 | 0.277 | 1.00 | 0.606 | 0.479 | 0.613 | 0.565 | 0.529 | 0.00 | 0.67 | 0 | 32 / 45 |

**Từng phần trên mốc A (F1–F6 + kênh/knob mới)**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_dest | 0.746 | +3.8 | **WIN** (ΔR@10 +2.5) | 0.746 | 0.341 | 1.00 | 0.776 | 0.542 | 0.762 | 0.729 | 0.525 | 0.11 | 0.78 | 11 | 15 / 83 |
| hybrid_norm_nocut_nodia | 0.707 | +0.0 | TIE | 0.707 | 0.316 | 1.00 | 0.734 | 0.528 | 0.724 | 0.691 | 0.539 | 0.11 | 0.79 | 0 | 60 / 86 |
| hybrid_norm_nocut_neg | 0.753 | +4.5 | không thắng (ΔR@10 +1.96 < 2) | 0.753 | 0.336 | 1.00 | 0.752 | 0.757 | 0.771 | 0.734 | 0.225 | 0.11 | 0.77 | 29 | 59 / 87 |
| hybrid_norm_nocut_tax | 0.723 | +1.6 | TIE | 0.723 | 0.318 | 1.00 | 0.747 | 0.563 | 0.723 | 0.724 | 0.522 | 0.11 | 0.80 | 278 | 60 / 87 |
| hybrid_norm_nocut_tax_strong | 0.713 | +0.6 | TIE | 0.713 | 0.314 | 1.00 | 0.740 | 0.531 | 0.722 | 0.705 | 0.547 | 0.11 | 0.80 | 248 | 58 / 78 |
| hybrid_norm_nocut_route | 0.709 | +0.2 | TIE | 0.709 | 0.314 | 1.00 | 0.732 | 0.555 | 0.730 | 0.688 | 0.429 | 1.00 | 0.76 | 6 | 53 / 76 |
| hybrid_norm_nocut_num | 0.714 | +0.7 | TIE | 0.714 | 0.314 | 1.00 | 0.742 | 0.528 | 0.724 | 0.703 | 0.539 | 0.11 | 0.92 | 107 | 55 / 79 |
| hybrid_norm_nocut_party | 0.704 | -0.4 | TIE | 0.704 | 0.314 | 1.00 | 0.730 | 0.528 | 0.717 | 0.691 | 0.539 | 0.11 | 0.79 | 0 | 58 / 83 |
| hybrid_norm_nocut_tone | 0.707 | +0.0 | TIE | 0.707 | 0.316 | 1.00 | 0.734 | 0.528 | 0.724 | 0.691 | 0.539 | 0.11 | 0.79 | 0 | 60 / 90 |
| hybrid_norm_nocut_fuzzy | 0.702 | -0.5 | TIE | 0.702 | 0.310 | 1.00 | 0.730 | 0.512 | 0.722 | 0.681 | 0.550 | 0.11 | 0.80 | 0 | 66 / 93 |
| hybrid_norm_nocut_fuzzy60 | 0.695 | -1.2 | TIE | 0.695 | 0.305 | 1.00 | 0.726 | 0.487 | 0.715 | 0.675 | 0.575 | 0.00 | 0.80 | 0 | 58 / 88 |
| hybrid_norm_nocut_wrrf | 0.725 | +1.7 | TIE | 0.725 | 0.323 | 1.00 | 0.754 | 0.527 | 0.740 | 0.709 | 0.550 | 0.00 | 0.79 | 0 | 63 / 91 |
| hybrid_norm_nocut_wrrf_d | 0.681 | -2.6 | LOSE | 0.681 | 0.306 | 1.00 | 0.705 | 0.520 | 0.700 | 0.662 | 0.539 | 0.00 | 0.76 | 0 | 65 / 94 |

**Tổ hợp**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_dest_nodia | 0.746 | +3.8 | **WIN** (ΔR@10 +2.5) | 0.746 | 0.341 | 1.00 | 0.776 | 0.542 | 0.762 | 0.729 | 0.525 | 0.11 | 0.78 | 11 | 14 / 62 |
| hybrid_norm_nocut_qp | 0.784 | +7.7 | **WIN** (ΔR@10 +2.3) | 0.784 | 0.339 | 1.00 | 0.778 | 0.827 | 0.792 | 0.776 | 0.000 | 1.00 | 0.94 | 404 | 45 / 70 |
| F1–F6 (ứng viên) | 0.807 | +9.9 | **WIN** (ΔR@10 +4.2) | 0.807 | 0.358 | 1.00 | 0.804 | 0.824 | 0.817 | 0.797 | 0.000 | 1.00 | 0.96 | 415 | 14 / 52 |
| hybrid_norm_nocut_f1f6_wrrf | 0.819 | +11.2 | **WIN** (ΔR@10 +4.7) | 0.819 | 0.363 | 1.00 | 0.819 | 0.816 | 0.829 | 0.808 | 0.000 | 1.00 | 0.96 | 415 | 14 / 79 |
| ALL | 0.793 | +8.5 | **WIN** (ΔR@10 +3.4) | 0.793 | 0.350 | 1.00 | 0.788 | 0.826 | 0.798 | 0.787 | 0.000 | 1.00 | 0.96 | 385 | 11 / 56 |
| hybrid_norm_nocut_all_c84 | 0.789 | +8.1 | TIE vs ALL | 0.789 | 0.345 | 1.00 | 0.783 | 0.826 | 0.789 | 0.788 | 0.000 | 1.00 | 0.95 | 385 | 11 / 56 |
| hybrid_norm_c84 | 0.692 | -1.5 | TIE | 0.692 | 0.311 | 1.00 | 0.717 | 0.528 | 0.706 | 0.679 | 0.543 | 0.11 | 0.79 | 0 | 55 / 84 |
| hybrid_norm_c84_dest_nodia_nc80 | 0.743 | +3.5 | **WIN** (ΔR@10 +2.0) | 0.743 | 0.336 | 1.00 | 0.773 | 0.542 | 0.756 | 0.730 | 0.529 | 0.11 | 0.78 | 11 | 14 / 67 |
| hybrid_norm_c84_dest_nodia_nc80_qp | 0.804 | +9.7 | **WIN** (ΔR@10 +4.0) | 0.804 | 0.356 | 1.00 | 0.801 | 0.824 | 0.810 | 0.799 | 0.000 | 1.00 | 0.95 | 415 | 11 / 65 |

**Leave-one-out từ ALL (so với ALL)**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_all_minus_dest | 0.772 | +6.5 | LOSE vs ALL | 0.772 | 0.334 | 1.00 | 0.764 | 0.828 | 0.779 | 0.765 | 0.000 | 1.00 | 0.94 | 374 | 48 / 84 |
| hybrid_norm_nocut_all_minus_nodia | 0.793 | +8.5 | TIE vs ALL | 0.793 | 0.350 | 1.00 | 0.788 | 0.826 | 0.798 | 0.787 | 0.000 | 1.00 | 0.96 | 385 | 11 / 62 |
| hybrid_norm_nocut_all_minus_neg | 0.741 | +3.4 | LOSE vs ALL | 0.741 | 0.328 | 1.00 | 0.763 | 0.592 | 0.742 | 0.740 | 0.420 | 1.00 | 0.96 | 356 | 11 / 62 |
| hybrid_norm_nocut_all_minus_tax | 0.787 | +8.0 | TIE vs ALL | 0.787 | 0.351 | 1.00 | 0.791 | 0.765 | 0.802 | 0.772 | 0.065 | 1.00 | 0.90 | 153 | 13 / 66 |
| hybrid_norm_nocut_all_minus_route | 0.785 | +7.7 | TIE vs ALL | 0.785 | 0.344 | 1.00 | 0.786 | 0.777 | 0.783 | 0.787 | 0.210 | 0.11 | 0.97 | 385 | 12 / 66 |
| hybrid_norm_nocut_all_minus_num | 0.789 | +8.2 | TIE vs ALL | 0.789 | 0.350 | 1.00 | 0.784 | 0.826 | 0.802 | 0.777 | 0.000 | 1.00 | 0.79 | 288 | 12 / 62 |
| hybrid_norm_nocut_all_minus_party | 0.801 | +9.3 | TIE vs ALL | 0.801 | 0.357 | 1.00 | 0.797 | 0.826 | 0.814 | 0.787 | 0.000 | 1.00 | 0.96 | 385 | 11 / 61 |
| hybrid_norm_nocut_all_minus_tone | 0.793 | +8.5 | TIE vs ALL | 0.793 | 0.350 | 1.00 | 0.788 | 0.826 | 0.798 | 0.787 | 0.000 | 1.00 | 0.96 | 385 | 13 / 70 |
| hybrid_norm_nocut_all_minus_fuzzy | 0.793 | +8.5 | TIE vs ALL | 0.793 | 0.350 | 1.00 | 0.788 | 0.824 | 0.798 | 0.787 | 0.000 | 1.00 | 0.96 | 385 | 13 / 69 |

**Rerank offline (bge-reranker-v2-m3, top-30)**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_rr | 0.764 | +5.6 | không thắng (ΔR@10 +1.74 < 2) | 0.764 | 0.333 | 1.00 | 0.795 | 0.552 | 0.764 | 0.764 | 0.582 | 0.22 | 0.84 | 0 | 60 / 88 (+rerank CPU ~3.4 s) |
| hybrid_norm_nocut_f1f6_rr | 0.845 | +13.7 | không thắng (ΔR@10 +0.21 < 2) vs F1–F6 (ứng viên) | 0.845 | 0.360 | 1.00 | 0.838 | 0.889 | 0.851 | 0.838 | 0.000 | 1.00 | 0.93 | 415 | 10 / 48 (+rerank CPU ~3.4 s) |
| hybrid_norm_nocut_all_rr | 0.834 | +12.6 | không thắng (ΔR@10 +0.35 < 2) vs ALL | 0.834 | 0.353 | 1.00 | 0.825 | 0.889 | 0.830 | 0.837 | 0.000 | 1.00 | 0.93 | 385 | 11 / 50 (+rerank CPU ~3.4 s) |



**nDCG@10 theo slice** (cột: dense = `dense_nocut`, A, lex = `_lexonly`, F1…F6 = arm một phần, F3–F6 = `_qp`, F1–F6 = ứng viên, ALL, F1–F6+rr):

| slice | n | dense | A | lex | F1 | F2 | F3 | F4 | F5 | F6 | fuzzy | F3–F6 | F1–F6 | ALL | F1–F6+rr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| abbrev_typo | 12 | 0.393 | 0.715 | 0.614 | 0.756 | 0.715 | 0.715 | 0.735 | 0.715 | 0.728 | 0.728 | 0.735 | 0.754 | 0.727 | 0.740 |
| amenity_multi | 10 | 0.837 | 0.896 | 0.838 | 0.892 | 0.896 | 0.896 | 0.904 | 0.896 | 0.896 | 0.896 | 0.904 | 0.899 | 0.899 | 0.956 |
| amenity_negation | 13 | 0.351 | 0.316 | 0.332 | 0.329 | 0.316 | 0.776 | 0.274 | 0.316 | 0.316 | 0.314 | 0.829 | 0.823 | 0.823 | 0.924 |
| amenity_offtaxonomy | 5 | 0.590 | 0.619 | 0.398 | 0.645 | 0.619 | 0.619 | 0.617 | 0.619 | 0.619 | 0.575 | 0.617 | 0.639 | 0.639 | 0.650 |
| amenity_single | 13 | 0.798 | 0.839 | 0.702 | 0.874 | 0.839 | 0.839 | 0.884 | 0.839 | 0.839 | 0.822 | 0.884 | 0.870 | 0.870 | 0.911 |
| audience_style | 11 | 0.768 | 0.617 | 0.412 | 0.757 | 0.617 | 0.617 | 0.615 | 0.617 | 0.617 | 0.617 | 0.615 | 0.740 | 0.644 | 0.805 |
| cross_vertical | 10 | 0.805 | 0.654 | 0.468 | 0.691 | 0.654 | 0.654 | 0.654 | 0.654 | 0.654 | 0.654 | 0.654 | 0.691 | 0.691 | 0.748 |
| dest_type | 12 | 0.827 | 0.744 | 0.600 | 0.819 | 0.744 | 0.744 | 0.790 | 0.725 | 0.744 | 0.744 | 0.808 | 0.845 | 0.809 | 0.808 |
| flight_direction | 6 | 0.721 | 0.822 | 0.802 | 0.822 | 0.822 | 0.822 | 0.754 | 0.908 | 0.822 | 0.784 | 0.908 | 0.908 | 0.908 | 0.908 |
| multi_constraint | 9 | 0.846 | 0.735 | 0.446 | 0.780 | 0.735 | 0.735 | 0.772 | 0.735 | 0.824 | 0.735 | 0.828 | 0.857 | 0.857 | 0.915 |
| named_entity | 18 | 0.820 | 0.818 | 0.754 | 0.884 | 0.818 | 0.818 | 0.841 | 0.818 | 0.818 | 0.813 | 0.841 | 0.891 | 0.883 | 0.883 |
| no_diacritics | 12 | 0.219 | 0.743 | 0.676 | 0.735 | 0.743 | 0.743 | 0.738 | 0.743 | 0.743 | 0.732 | 0.738 | 0.749 | 0.749 | 0.805 |
| out_of_catalog | 7 | – | – | – | – | – | – | – | – | – | – | – | – | – | – |
| parent_child | 11 | 0.684 | 0.698 | 0.552 | 0.699 | 0.698 | 0.698 | 0.708 | 0.698 | 0.698 | 0.698 | 0.708 | 0.690 | 0.677 | 0.837 |
| taxonomy_collision | 5 | 0.659 | 0.641 | 0.491 | 0.665 | 0.641 | 0.771 | 0.859 | 0.641 | 0.641 | 0.632 | 0.868 | 0.877 | 0.882 | 0.835 |


## 3. Guard Phase A và parse accuracy

`sb --run-id 2026-10-06-gold-v4-r2 guards --arms …` (ngưỡng `metrics.guards_proposed` — **đề xuất 06/10, chưa chốt**):

| guard | ngưỡng đề xuất | A | F1–F6 | ALL | F1–F6 + rerank |
|---|---|---|---|---|---|
| forbidden_at_10 (n = 28) | ≤ 0 | 0,539 FAIL | 0,000 PASS | 0,000 PASS | 0,000 PASS |
| forbidden_query_rate | – | 0,929 | 0,000 | 0,000 | 0,000 |
| direction_accuracy (n = 9) | ≥ 1 | 0,111 FAIL | 1,000 PASS | 1,000 PASS | 1,000 PASS |
| filter_pass_rate | ≥ 1 | n/a | 1,000 PASS | 1,000 PASS | 1,000 PASS |
| constraint_precision (n = 23) | ≥ 0,95 | 0,787 FAIL | 0,960 PASS | 0,960 PASS | 0,929 FAIL |
| zero_result_in_catalog (n = 147) | ≤ 0,02 | 0,000 PASS | 0,000 PASS | 0,000 PASS | 0,000 PASS |

Rerank làm constraint precision tụt (0,960 → 0,929: c0481, c0497, c0503, c0531 — cross-encoder đẩy lên sản phẩm khớp ngữ nghĩa nhưng sai
sao/giá) → nếu đưa rerank online phải chạy SAU kiểm ràng buộc, không thay nó.

Parse accuracy (so `queryPlan` với `expected_parse` của `config/query_annotations.yaml`, đủ 154 câu — câu parser không ra gì được chấm
như plan rỗng):

| arm | khối | n | taxonomy | destination | origin | destination_city | must_not | must_not_taxonomies | price_max | price_min | star_min | party_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | v3 | 131 | 0.992 | 0.992 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.977 |
| A | v4 | 23 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.957 | 1.0 | 1.0 | 1.0 | 1.0 |
| A | tất cả | 154 | 0.994 | 0.994 | 1.0 | 1.0 | 1.0 | 0.994 | 1.0 | 1.0 | 1.0 | 0.981 |
| F1–F6 | v3 | 131 | 0.992 | 0.992 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.977 |
| F1–F6 | v4 | 23 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| F1–F6 | tất cả | 154 | 0.994 | 0.994 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.981 |
| ALL | v3 | 131 | 0.992 | 0.992 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| ALL | v4 | 23 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| ALL | tất cả | 154 | 0.994 | 0.994 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

Sai còn lại của F1–F6: c0340 "Công Viên 30/4" (tên POI trần, chú giải kỳ vọng không loại — parser ra attraction yếu), c0355 "Bus Ha Noi to
Cat Ba" (hai địa danh, chú giải chọn Cát Bà); `party_total` sai ở c0136 / c0147 / c0284 chỉ vì arm tắt cờ party nên `queryPlan.party`
không phát (khi cờ bật — ALL — đúng 3/3).

**Độ tin cậy router (không LLM, `queryPlan.confidence`, arm F1–F6):** 59 / 154 câu < 1 (10 câu ≤ 0,5); lý do `long_multi_constraint` 48, `weak_taxonomy_cue` 11, `multi_vertical` 10. nDCG@10 của F1–F6 trên nhóm này 0,770 (n = 59) so 0,832 (n = 88, độ tin cậy 1) — đây là nhóm câu đề xuất LLM fallback nhắm tới (`docs/prd/update/2026-10-06-search-llm-fallback-query-plan.md`, chờ chốt).

## 4. Chọn ngưỡng bằng dữ liệu (chọn trên dev, kiểm trên test)

**Cue loại sản phẩm (task 3 — F4).** Tỷ lệ item nhãn 2 cùng taxonomy với cue, trên câu chỉ nêu một ngành dọc (gold cuối):

| cue | loại | độ mạnh (chốt) | dev: câu · rel2 · giữ % | test: câu · rel2 · giữ % |
|---|---|---|---|---|
| khách sạn | hotel | mạnh | 20 · 460 · 100 | 17 · 327 · 100 |
| chỗ nghỉ | hotel | mạnh | 13 · 334 · 100 | 20 · 504 · 100 |
| phòng | hotel | yếu | 12 · 190 · 100 | 8 · 219 · 100 |
| resort | hotel | mạnh | 5 · 62 · 100 | 3 · 5 · 80 |
| vé máy bay | flight | mạnh | 2 · 6 · 100 | 5 · 29 · 100 |
| nghỉ dưỡng | hotel | yếu | 3 · 56 · 100 | 3 · 60 · 100 |
| combo | combo | mạnh | 1 · 0 · – | 4 · 52 · 88 |
| nơi lưu trú | hotel | mạnh | 4 · 118 · 100 | – |
| điểm vui chơi | attraction | yếu | – | 2 · 58 · 47 |
| safari | attraction | yếu | 1 · 11 · 73 | – |
| vinwonders | attraction | yếu | – | 1 · 6 · 50 |
| grand world | attraction | yếu | 1 · 12 · 100 | – |

Danh từ chỗ nghỉ giữ ≈ 100 % ở cả hai split → mạnh; tên điểm vui chơi / "điểm vui chơi" giữ 47–73 % (combo chứa vé được nhãn 2 theo rubric
v3) → yếu và không cắt khỏi BM25. Dù vậy `_tax_strong` (chỉ lọc khi có cue mạnh) thua F4 đủ 1,0 điểm trên toàn gold (TIE) — cue yếu
"phòng" / "nghỉ dưỡng" lọc đúng nhiều hơn sai → **giữ F4 đủ cue**; bảng mạnh/yếu chỉ khai `queryPlan.taxonomy.strength` cho Agent / router.

**Kết quả yếu (margin so nền, `sb weak-results`, arm F1–F6; nền = trung vị cosine trên cả catalog):**

| margin M (topScore ngưỡng 0,70) | dev: ngoài catalog bị chặn / 3 · trong catalog gắn weak nhầm / 74 | test: … / 4 · … / 73 |
|---|---|---|
| 0,050 | 1 · 3 | 1 · 3 |
| 0,054 | 2 · 6 | 2 · 5 |
| 0,056 | 2 · 7 | 4 · 6 |
| **0,058** | **3 · 7** | **4 · 9** |
| 0,060 (tạm contract) | 3 · 10 | 4 · 12 |
| 0,070 | 3 · 26 | 4 · 25 |

M nhỏ nhất chặn đủ câu ngoài catalog trên dev = **0,058** → test chặn 4/4, nhầm 12 %. Cutoff tuyệt đối 0,84 không chặn câu ngoài catalog
nào (`zero_result_out_of_catalog` = 0 ở ALL + 0,84; topScore câu ngoài catalog 0,853–0,867, trong catalog p10 0,859) → **không dùng cutoff
tuyệt đối trên e5**. Caveat: chỉ 7 câu ngoài catalog; nền tính trên cả catalog, contract lấy trên F đã lọc.

**Kênh fuzzy:** 0,75 (−0,5) tốt hơn 0,6 (−1,2); không slice nào được lợi (lỗi chính tả tên đã do bước normalize xử lý) → giữ tắt
(`SEARCH_FUZZY_K=0`), mặc định ngưỡng 0,75 khi bật.

## 5. Đề xuất cấu hình (người dùng quyết định — chưa đổi mặc định nào)

| cờ / tham số | hôm nay | đề xuất | căn cứ |
|---|---|---|---|
| `SEARCH_DEST_FILTER` (F1) | tắt | **bật** | WIN (+3,8); bỏ khỏi ALL → LOSE |
| `SEARCH_NO_DIACRITICS_MODE` (F2) | off | relax | trung tính khi không cutoff |
| `SEARCH_NEGATION_FILTER` (F3) | tắt | **bật** | +4,5; bỏ khỏi ALL → LOSE (−5,2); Forbidden câu phủ định → 0 |
| `SEARCH_TAXONOMY_FILTER` (F4) | tắt | **bật — cần ý kiến Web** (đổi số đếm tab, `docs/spec/product.md`) | `taxonomy_collision` +21,8; bỏ → Forbidden 0,065 |
| `SEARCH_ROUTE_FILTER` (F5) | tắt | **bật** | chiều bay 0,11 → 1,00; bỏ → Forbidden 0,210 |
| `SEARCH_NUMERIC_FILTER` (F6) | tắt | **bật** | constraint precision 0,79 → 0,92 (0,96 trong tổ hợp) |
| `SEARCH_TAXONOMY_STRONG_ONLY` | tắt | tắt | −1,0 so F4 đủ |
| `SEARCH_PARTY_FILTER` | tắt | tắt | −0,4; gold chỉ 3 câu có số khách |
| `SEARCH_TONE_NORMALIZE` | tắt | tắt (vô hại) | 0,0 — gold không có câu lệch kiểu dấu |
| `SEARCH_FUZZY_K` | 0 | 0 | −0,5 |
| `SEARCH_RRF_LEXICAL_WEIGHT` | 1,0 | 1,0 (thử 0,5 khi có thêm gold) | +1,2 trên F1–F6, TIE dev / test cùng chiều |
| `SEARCH_CUTOFF` | 0,62 (không cắt gì trên e5) | giữ | cutoff tuyệt đối vô dụng trên e5 |
| margin kết quả yếu (client, contract §3.4) | 0,06 | **0,058** | §4 |
| rerank online | không có | không (chỉ offline) | +3,8 nhưng ~3,4 s CPU/câu, constraint precision 0,93 |

Bật cờ production đổi hành vi `/search` hôm nay → cần người dùng chốt (và Web cho F4) trước khi đổi `.env` / `core/config.py`;
cherry-pick `release-mvp-v2` sau đó.

## 6. Nhãn hole (máy, chưa duyệt)

| đợt | nguồn | cặp | câu | auto_ooc | phân bố 0 / 1 / 2 |
|---|---|---:|---:|---:|---|
| D9a | run r1 (21 arm) | 829 | 121 | 56 | 323 / 247 / 259 |
| D9b | run r2 (42 arm, trước sửa fuzzy) | 871 | 140 | 60 | 279 / 307 / 285 |
| D9c | 13 arm chạy lại sau sửa fuzzy | 69 | 36 | 9 | 19 / 22 / 28 |
| D9d | chạy lại sau sửa parser | 14 | 5 | 0 | 0 / 10 / 4 |
| D9e | 3 arm F1–F6 | 16 | 14 | 0 | 0 / 10 / 6 |

Gán bằng agent theo gói slice với `docs/spec/bench/gold-guide.md` + nhãn sẵn có của chính câu làm mốc; đối chiếu luật cho câu phủ định v4 +
vé máy bay: luật khớp gold người 313/322 (97 %), khớp nhãn máy D9a 99/101 và D9b 74/75 (lệch đều do "dòng Tiện ích" ghi tiện ích bị loại
trừ — nhãn máy đúng theo #3/#14). Sửa tay hai điểm: 14 cặp `multi_constraint` hạ 2 → 1 (sao dưới ngưỡng, khớp nhãn người), Pullman Phú
Quốc (c0685) 2 → 0. Agent chỉ ra nhãn cũ nghi sai (không sửa — gold chỉ thêm): c0394 Moscow Hotel Ha Long nhãn 2 cho câu Hà Nội; c0426
Bao Phuc (Cát Bà) nhãn 0 trái quy ước #1; c0439 / c0253 / c0247 có nhãn trước quy ước #3 / #6 mâu thuẫn nhãn mới.

## 7. Caveat khi trích dẫn

- **Nhãn máy chưa duyệt** chiếm 1.924 / 7.590 nhãn (25 %) và toàn bộ phần lấp hole — số chỉ được trích là "trên gold_v4 + nhãn máy chưa
  duyệt" cho tới khi người duyệt và tag `gold_v5`.
- n nhỏ: 13 câu phủ định, 6 câu chiều bay (+ 3 câu bay khác), 5 câu lẫn loại, 7 câu ngoài catalog; mỗi split 77 câu.
- Bảng cue F4, từ vựng tiện ích và ba sửa parser được làm sau khi xem gold (trong mẫu với toàn gold, dù ngưỡng chọn theo dev).
- Không HTTP, không Cohere; độ trễ là engine trên Weaviate local với vector truy vấn đã cache. Rerank: CPU laptop, điểm có cache.
- Danh sách tiện ích catalog của một số khách sạn dừng ở đúng 60 chuỗi (giới hạn nguồn) → F3 có thể không thấy tiện ích bị loại trừ.
- `filter_recall_loss` của F4 cao (278) vì rubric v3 #2 cho 1 điểm "đúng nơi, sai loại" — filter loại các nhãn 1 đó đúng theo ý câu.

## 8. Lệnh tái sinh

```bash
# từ <repo>/src, PYTHONPATH=<repo>/src PYTHONUTF8=1, python = <repo>/.venv-sbench/Scripts/python; Weaviate bench local (config/sbench.yaml)
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 run --arm APP.e5s.hybrid_norm_nocut --arm APP.e5s.hybrid_norm_nocut_f1f6 ... --allow-untagged
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 rescore --allow-untagged
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 compare APP.e5s.hybrid_norm_nocut APP.e5s.hybrid_norm_nocut_f1f6 [--split dev|test]
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 guards --arms APP.e5s.hybrid_norm_nocut,APP.e5s.hybrid_norm_nocut_f1f6
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 weak-results --arm APP.e5s.hybrid_norm_nocut_f1f6 --split dev --top-grid 0.7 --margin-grid 0.05,0.054,0.056,0.058,0.06,0.07
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 gold holes --arms <45 arm> --tag D9x   # hole còn lại: 0
```

Bảng §2 sinh từ `per_query@untagged.parquet` / `results@untagged.json` của từng arm + dòng verdict của `sb compare`; split từ
`devtest@gold_v4.json`.
