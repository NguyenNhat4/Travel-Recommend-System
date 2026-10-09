# Search bench 06/10 — query plan F1–F6 và phần còn thiếu của kiến trúc (fuzzy, số khách, dấu thanh, RRF trọng số, rerank offline) trên gold_v5

> **Cập nhật 06/10 chiều:** số trong report này tính trên **`gold_v5`** (tag trên `ca9fb88`): mọi nhãn máy hole D9a–D9e đã được QAnh duyệt,
> 150 nhãn 1 của hole sai loại / dưới sao hạ về 0 theo rubric v4, và lúc chấm **chiếu rubric v4** lên nhãn cũ v1–v3 (164 cặp / 35 câu,
> `metrics.rubric_v4_projection`; `history/2026-10-06-gold-v5-hole-d9-rubric-v4-nhan-1.md`). Bản sáng (commit `0f7cf0a`) tính trên nhãn
> máy chưa duyệt, chưa chiếu: mốc 0,707, F1–F6 0,807. Kết luận không đổi; F4 rõ hơn (+1,6 → +2,4) vì sản phẩm sai loại nay tính 0.

- Ngày chạy và viết: **06/10/2026**. Phục vụ **FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01**, NFR-PERF-01; kiến trúc
  `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` (Phase A, B, D offline).
- Nhánh `fix/search-gold-v4`: code engine + bench ở `0f7cf0a`, gold + chiếu rubric v4 ở `ca9fb88` (tag `gold_v5`). History:
  `history/2026-10-06-search-query-plan-v116-fuzzy-party-tone.md`, `history/2026-10-06-search-bench-ablation-gold-v5.md`,
  `history/2026-10-06-gold-v5-hole-d9-rubric-v4-nhan-1.md`, `history/2026-10-06-search-gold-v5-tag-rescore-baseline.md`. Contract **1.16.0**.
- Run: `2026-10-06-gold-v4-r1` (21 arm, mã trước sửa — chỉ dùng sinh hole D9a và kiểm identity) và **`2026-10-06-gold-v4-r2`** (45 arm
  `APP.e5s.*`, mã cuối — mọi bảng dưới đây), cả hai `sb rescore` trên `gold_v5`. Collection `ProductBench__e5_small` (3.183 unit, hnsw,
  `intfloat/multilingual-e5-small`, 384 chiều), Weaviate bench Docker local, vector truy vấn từ cache embed, **không Cohere, không HTTP**.
- Gold `gold_v5`: 154 câu active, 7.590 nhãn (gold_v4 5.666 + hole D9a–D9e 1.799 nhãn máy đã duyệt + 125 auto_ooc), SHA-256
  `1f903132eca033c596672ff7d1ba04abcb1cd3c97c5797017ca1ddee9a93d7b0`. **Judged@10 = 1,00 cho cả 45 arm.**
- Split `gold/splits/devtest@gold_v4.json` (seed 42, phân tầng slice, dev 77 / test 77 — cùng 154 câu với gold_v5). Hai khối: **v3**
  (131 câu gold_v1–v3) và **v4** (23 câu từ c0673) — báo riêng.
- Win rule của bench (`config/sbench.yaml`): WIN khi Δrecall@10 ≥ 2,0 điểm, p < 0,05 và không slice nào tụt > 3,0; TIE khi |ΔnDCG| < 2,0;
  còn lại in "LOSE". Bảng ghi **"không thắng (lý do)"** thay "LOSE" khi nDCG tăng nhưng trượt một điều kiện (thường là Δrecall < 2 —
  thay đổi chỉ sắp lại thứ tự). Mốc **A** = `APP.e5s.hybrid_norm_nocut` (hybrid + normalize production, cutoff −1).

## 1. Kết luận ngắn

1. **Ứng viên production `F1–F6` (`APP.e5s.hybrid_norm_nocut_f1f6`): nDCG@10 0,818 so mốc 0,711 — WIN (Δrecall +4,79, p < 0,001)**, cả
   khối v3 (+7,9) lẫn v4 (+29,6). Đủ mọi guard Phase A: Forbidden@10 **0,539 → 0**, chiều bay **0,11 → 1,00**, constraint precision **0,79 →
   0,96**, zero-result trong catalog 0. Thành phần: F1 điểm đến + F2 câu không dấu + F3 phủ định + F4 loại sản phẩm (mọi cue) + F5 tuyến
   bay + F6 giá/sao; không cutoff, không party / tone / fuzzy.
2. **Dev / test:** dev **WIN** (+10,0 nDCG, Δrecall +4,98); test ΔnDCG **+11,4**, Δrecall +4,59 (p 0,008) nhưng *không thắng theo luật*
   vì slice `flight_direction` trên test (3 câu) tụt 6,0 — F5 chỉ giữ đúng tuyến hỏi, loại combo vé khứ hồi mà rubric v4 cho 1.
3. **Từng phần (trên mốc A):** F1 **WIN** (+3,3); F3 +4,5 (Δrecall +1,93 — sát ngưỡng; `amenity_negation` 0,303 → 0,762, Forbidden
   0,539 → 0,225); F4 +2,4 (Δrecall +0,80; `taxonomy_collision` 0,641 → 0,859, `dest_type` 0,783 → 0,881); F5 +0,1 TIE nhưng chiều bay
   0,11 → 1,00; F6 +0,7 TIE nhưng constraint precision 0,79 → 0,92; F2 = 0 khi không cutoff (đúng thiết kế). Leave-one-out từ ALL: bỏ F3
   **LOSE** (−5,2), bỏ F4 **LOSE** (−2,1), bỏ F1 −2,0 (TIE sát ngưỡng); bỏ F5 / F6 TIE về nDCG **nhưng làm hỏng guard** (Forbidden 0,210 + chiều
   0,11 / constraint precision 0,79) → cả sáu cần giữ.
4. **Phần mới của kiến trúc đều trung tính trên gold này — giữ tắt:** party −0,6 (bỏ khỏi ALL +0,8), tone 0,0 (gold không có câu lệch kiểu
   dấu), fuzzy −0,6 (0,75) / −1,2 (0,6), F4 chỉ cue mạnh −1,1 so F4 đủ. **RRF trọng số lexical 0,5**: +1,7 trên A, +1,2 trên F1–F6 (0,830;
   TIE cả dev lẫn test, cùng chiều) — ứng viên tinh chỉnh sau. Dense 0,5: −2,8 LOSE. Lexical-only −12,1, dense-only −4,9, hybrid không
   normalize −3,0 so mốc.
5. **Rerank offline `BAAI/bge-reranker-v2-m3` top-30:** trên F1–F6 nDCG **0,857** (+3,9 so F1–F6; dev +3,6, test +4,3) — không thắng theo
   luật vì gần như không đổi recall@10 (chỉ sắp lại). Chi phí CPU ~3,4 s/câu (cold, laptop) → **chỉ offline**; online cần GPU / model nhỏ
   (kiến trúc Phase D).
6. **Cutoff tuyệt đối không dùng được trên e5** (ALL + 0,84: TIE, 7/7 câu ngoài catalog vẫn có kết quả). Thay bằng luật **kết quả yếu
   theo margin** (§3.4 contract, client sở hữu): margin **0,058** chọn trên dev chặn 3/3 câu ngoài catalog (dev) và **4/4 (test)**, gắn weak
   nhầm 7/74 (dev) · 9/73 (test); ngưỡng tạm 0,06 của contract nhầm 10/74 · 12/73.
7. **Hai lỗi engine bench bắt được và đã sửa trong đợt này:** (a) kênh fuzzy đưa cả top-50 vào RRF dù dưới ngưỡng (−7,6 → −0,6 sau sửa);
   (b) parse accuracy bỏ sót 23/154 câu không có `queryPlan` — đo lại đủ 154: taxonomy khối v3 0,924 → **0,992** sau ba sửa parser (cue trong tên
   sản phẩm đúng loại unit, "có <cue> nào", cue "hotel" / "điểm vui chơi").
8. **Regression:** `regression/baseline_v1.json` đặt lại trên `gold_v5` = arm production hôm nay `APP.e5s.hybrid_norm` (nDCG@10 0,711,
   recall@10 0,352); `sb regress check` cùng arm PASS, top-10 đổi 0/154 câu.

## 2. Bảng benchmark (run `2026-10-06-gold-v4-r2`, `gold_v5`, chiếu rubric v4, Judged@10 = 1,00)

Cột: nDCG@10 full; Δ so A (điểm %); win rule so arm cha (cha = A trừ khi ghi "vs …"); nDCG condensed; R@10; nDCG theo khối rubric v3 / v4 và
theo split dev / test; Forbidden@10 (micro, 28 câu có `forbidden_filter`); chiều bay (direction accuracy, 9 câu vé máy bay); constraint
precision (23 câu có ràng buộc); `filter_recall_loss` (số nhãn ≥ 1 bị filter loại); độ trễ engine `SearchProducts` p50 / p95 ms trên
Weaviate local (không phải HTTP, không gồm embed vì cache). Tên arm bỏ tiền tố `APP.e5s.`.


**Mốc truy xuất**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dense_nocut | 0.662 | -4.9 | LOSE | 0.662 | 0.332 | 1.00 | 0.683 | 0.520 | 0.684 | 0.639 | 0.507 | 0.00 | 0.80 | 0 | 28 / 44 |
| hybrid_nocut | 0.681 | -3.0 | LOSE | 0.681 | 0.331 | 1.00 | 0.711 | 0.478 | 0.709 | 0.653 | 0.554 | 0.11 | 0.80 | 0 | 56 / 86 |
| A = hybrid_norm_nocut | 0.711 | +0.0 |  | 0.711 | 0.352 | 1.00 | 0.738 | 0.528 | 0.726 | 0.695 | 0.539 | 0.11 | 0.79 | 0 | 60 / 89 |
| hybrid_norm_nocut_lexonly | 0.589 | -12.1 | LOSE | 0.589 | 0.303 | 1.00 | 0.606 | 0.479 | 0.615 | 0.563 | 0.529 | 0.00 | 0.67 | 0 | 32 / 45 |

**Từng phần trên mốc A (F1–F6 + kênh/knob mới)**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_dest | 0.744 | +3.3 | **WIN** (ΔR@10 +2.3) | 0.744 | 0.375 | 1.00 | 0.774 | 0.542 | 0.755 | 0.733 | 0.525 | 0.11 | 0.78 | 11 | 15 / 83 |
| hybrid_norm_nocut_nodia | 0.711 | +0.0 | TIE | 0.711 | 0.352 | 1.00 | 0.738 | 0.528 | 0.726 | 0.695 | 0.539 | 0.11 | 0.79 | 0 | 60 / 86 |
| hybrid_norm_nocut_neg | 0.756 | +4.5 | không thắng (ΔR@10 +1.93 < 2) | 0.756 | 0.372 | 1.00 | 0.756 | 0.757 | 0.772 | 0.739 | 0.225 | 0.11 | 0.77 | 29 | 59 / 87 |
| hybrid_norm_nocut_tax | 0.735 | +2.4 | không thắng (ΔR@10 +0.80 < 2) | 0.735 | 0.360 | 1.00 | 0.760 | 0.563 | 0.735 | 0.735 | 0.522 | 0.11 | 0.80 | 43 | 60 / 87 |
| hybrid_norm_nocut_tax_strong | 0.724 | +1.3 | TIE | 0.724 | 0.356 | 1.00 | 0.753 | 0.531 | 0.734 | 0.714 | 0.547 | 0.11 | 0.80 | 27 | 58 / 78 |
| hybrid_norm_nocut_route | 0.712 | +0.1 | TIE | 0.712 | 0.348 | 1.00 | 0.736 | 0.555 | 0.731 | 0.693 | 0.429 | 1.00 | 0.76 | 6 | 53 / 76 |
| hybrid_norm_nocut_num | 0.718 | +0.7 | TIE | 0.718 | 0.350 | 1.00 | 0.746 | 0.528 | 0.726 | 0.709 | 0.539 | 0.11 | 0.92 | 100 | 55 / 79 |
| hybrid_norm_nocut_party | 0.704 | -0.6 | TIE | 0.704 | 0.347 | 1.00 | 0.731 | 0.528 | 0.713 | 0.695 | 0.539 | 0.11 | 0.79 | 0 | 58 / 83 |
| hybrid_norm_nocut_tone | 0.711 | +0.0 | TIE | 0.711 | 0.352 | 1.00 | 0.738 | 0.528 | 0.726 | 0.695 | 0.539 | 0.11 | 0.79 | 0 | 60 / 90 |
| hybrid_norm_nocut_fuzzy | 0.705 | -0.6 | TIE | 0.705 | 0.344 | 1.00 | 0.734 | 0.512 | 0.723 | 0.687 | 0.550 | 0.11 | 0.80 | 0 | 66 / 93 |
| hybrid_norm_nocut_fuzzy60 | 0.698 | -1.2 | TIE | 0.698 | 0.339 | 1.00 | 0.730 | 0.487 | 0.715 | 0.681 | 0.575 | 0.00 | 0.80 | 0 | 58 / 88 |
| hybrid_norm_nocut_wrrf | 0.728 | +1.7 | TIE | 0.728 | 0.359 | 1.00 | 0.758 | 0.527 | 0.742 | 0.714 | 0.550 | 0.00 | 0.79 | 0 | 63 / 91 |
| hybrid_norm_nocut_wrrf_d | 0.683 | -2.8 | LOSE | 0.683 | 0.337 | 1.00 | 0.707 | 0.520 | 0.702 | 0.664 | 0.539 | 0.00 | 0.76 | 0 | 65 / 94 |

**Tổ hợp**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_dest_nodia | 0.744 | +3.3 | **WIN** (ΔR@10 +2.3) | 0.744 | 0.375 | 1.00 | 0.774 | 0.542 | 0.755 | 0.733 | 0.525 | 0.11 | 0.78 | 11 | 14 / 62 |
| hybrid_norm_nocut_qp | 0.796 | +8.6 | **WIN** (ΔR@10 +2.9) | 0.796 | 0.382 | 1.00 | 0.792 | 0.827 | 0.804 | 0.788 | 0.000 | 1.00 | 0.94 | 166 | 45 / 70 |
| F1–F6 (ứng viên) | 0.818 | +10.7 | **WIN** (ΔR@10 +4.8) | 0.818 | 0.400 | 1.00 | 0.817 | 0.824 | 0.826 | 0.810 | 0.000 | 1.00 | 0.96 | 177 | 14 / 52 |
| hybrid_norm_nocut_f1f6_wrrf | 0.830 | +11.9 | **WIN** (ΔR@10 +5.1) | 0.830 | 0.403 | 1.00 | 0.832 | 0.816 | 0.838 | 0.821 | 0.000 | 1.00 | 0.96 | 177 | 14 / 79 |
| ALL | 0.803 | +9.2 | **WIN** (ΔR@10 +3.6) | 0.803 | 0.388 | 1.00 | 0.800 | 0.826 | 0.807 | 0.799 | 0.000 | 1.00 | 0.96 | 161 | 11 / 56 |
| hybrid_norm_nocut_all_c84 | 0.801 | +9.0 | TIE vs ALL | 0.801 | 0.385 | 1.00 | 0.797 | 0.826 | 0.801 | 0.800 | 0.000 | 1.00 | 0.95 | 161 | 11 / 56 |
| hybrid_norm_c84 | 0.695 | -1.6 | TIE | 0.695 | 0.347 | 1.00 | 0.720 | 0.528 | 0.707 | 0.683 | 0.543 | 0.11 | 0.79 | 0 | 55 / 84 |
| hybrid_norm_c84_dest_nodia_nc80 | 0.742 | +3.1 | không thắng (ΔR@10 +1.96 < 2) | 0.742 | 0.372 | 1.00 | 0.772 | 0.542 | 0.752 | 0.733 | 0.529 | 0.11 | 0.78 | 11 | 14 / 67 |
| hybrid_norm_c84_dest_nodia_nc80_qp | 0.817 | +10.6 | **WIN** (ΔR@10 +4.8) | 0.817 | 0.400 | 1.00 | 0.816 | 0.824 | 0.822 | 0.812 | 0.000 | 1.00 | 0.95 | 177 | 11 / 65 |

**Leave-one-out từ ALL (so với ALL)**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_all_minus_dest | 0.783 | +7.3 | TIE vs ALL | 0.783 | 0.374 | 1.00 | 0.777 | 0.828 | 0.791 | 0.776 | 0.000 | 1.00 | 0.94 | 150 | 48 / 84 |
| hybrid_norm_nocut_all_minus_nodia | 0.803 | +9.2 | TIE vs ALL | 0.803 | 0.388 | 1.00 | 0.800 | 0.826 | 0.807 | 0.799 | 0.000 | 1.00 | 0.96 | 161 | 11 / 62 |
| hybrid_norm_nocut_all_minus_neg | 0.751 | +4.1 | LOSE vs ALL | 0.751 | 0.367 | 1.00 | 0.775 | 0.592 | 0.751 | 0.752 | 0.420 | 1.00 | 0.96 | 132 | 11 / 62 |
| hybrid_norm_nocut_all_minus_tax | 0.782 | +7.1 | LOSE vs ALL | 0.782 | 0.378 | 1.00 | 0.785 | 0.765 | 0.786 | 0.778 | 0.065 | 1.00 | 0.90 | 146 | 13 / 66 |
| hybrid_norm_nocut_all_minus_route | 0.795 | +8.4 | TIE vs ALL | 0.795 | 0.383 | 1.00 | 0.798 | 0.777 | 0.792 | 0.798 | 0.210 | 0.11 | 0.97 | 161 | 12 / 66 |
| hybrid_norm_nocut_all_minus_num | 0.799 | +8.8 | TIE vs ALL | 0.799 | 0.389 | 1.00 | 0.795 | 0.826 | 0.811 | 0.787 | 0.000 | 1.00 | 0.79 | 67 | 12 / 62 |
| hybrid_norm_nocut_all_minus_party | 0.811 | +10.0 | TIE vs ALL | 0.811 | 0.397 | 1.00 | 0.809 | 0.826 | 0.823 | 0.799 | 0.000 | 1.00 | 0.96 | 161 | 11 / 61 |
| hybrid_norm_nocut_all_minus_tone | 0.803 | +9.2 | TIE vs ALL | 0.803 | 0.388 | 1.00 | 0.800 | 0.826 | 0.807 | 0.799 | 0.000 | 1.00 | 0.96 | 161 | 13 / 70 |
| hybrid_norm_nocut_all_minus_fuzzy | 0.803 | +9.2 | TIE vs ALL | 0.803 | 0.391 | 1.00 | 0.800 | 0.824 | 0.808 | 0.798 | 0.000 | 1.00 | 0.96 | 161 | 13 / 69 |

**Rerank offline (bge-reranker-v2-m3, top-30)**

| arm | nDCG@10 | Δ vs A (điểm) | win rule (vs cha) | nDCG cond. | R@10 | Judged@10 | nDCG v3 | nDCG v4 | nDCG dev | nDCG test | Forbidden@10 | Chiều bay | Constraint prec. | filter_recall_loss | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_norm_nocut_rr | 0.769 | +5.8 | không thắng (ΔR@10 +1.75 < 2) | 0.769 | 0.370 | 1.00 | 0.801 | 0.552 | 0.768 | 0.771 | 0.582 | 0.22 | 0.84 | 0 | 60 / 88 (+rerank CPU ~3.4 s) |
| hybrid_norm_nocut_f1f6_rr | 0.857 | +14.6 | không thắng (ΔR@10 +0.15 < 2) vs F1–F6 (ứng viên) | 0.857 | 0.402 | 1.00 | 0.853 | 0.889 | 0.862 | 0.853 | 0.000 | 1.00 | 0.93 | 177 | 10 / 48 (+rerank CPU ~3.4 s) |
| hybrid_norm_nocut_all_rr | 0.846 | +13.5 | không thắng (ΔR@10 +0.51 < 2) vs ALL | 0.846 | 0.393 | 1.00 | 0.839 | 0.889 | 0.841 | 0.851 | 0.000 | 1.00 | 0.93 | 161 | 11 / 50 (+rerank CPU ~3.4 s) |



**nDCG@10 theo slice** (cột: dense = `dense_nocut`, A, lex = `_lexonly`, F1…F6 = arm một phần, F3–F6 = `_qp`, F1–F6 = ứng viên, ALL, F1–F6+rr):

| slice | n | dense | A | lex | F1 | F2 | F3 | F4 | F5 | F6 | fuzzy | F3–F6 | F1–F6 | ALL | F1–F6+rr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| abbrev_typo | 12 | 0.369 | 0.717 | 0.606 | 0.750 | 0.717 | 0.717 | 0.744 | 0.717 | 0.730 | 0.733 | 0.744 | 0.765 | 0.738 | 0.752 |
| amenity_multi | 10 | 0.837 | 0.896 | 0.835 | 0.892 | 0.896 | 0.896 | 0.904 | 0.896 | 0.896 | 0.896 | 0.904 | 0.899 | 0.899 | 0.956 |
| amenity_negation | 13 | 0.339 | 0.303 | 0.330 | 0.320 | 0.303 | 0.762 | 0.274 | 0.303 | 0.303 | 0.301 | 0.829 | 0.823 | 0.823 | 0.924 |
| amenity_offtaxonomy | 5 | 0.590 | 0.619 | 0.398 | 0.645 | 0.619 | 0.619 | 0.617 | 0.619 | 0.619 | 0.575 | 0.617 | 0.639 | 0.639 | 0.650 |
| amenity_single | 13 | 0.798 | 0.839 | 0.685 | 0.874 | 0.839 | 0.839 | 0.884 | 0.839 | 0.839 | 0.822 | 0.884 | 0.870 | 0.870 | 0.911 |
| audience_style | 11 | 0.768 | 0.617 | 0.412 | 0.757 | 0.617 | 0.617 | 0.615 | 0.617 | 0.617 | 0.617 | 0.615 | 0.740 | 0.644 | 0.805 |
| cross_vertical | 10 | 0.805 | 0.654 | 0.468 | 0.691 | 0.654 | 0.654 | 0.654 | 0.654 | 0.654 | 0.654 | 0.654 | 0.691 | 0.691 | 0.748 |
| dest_type | 12 | 0.840 | 0.783 | 0.629 | 0.831 | 0.783 | 0.783 | 0.881 | 0.757 | 0.783 | 0.783 | 0.900 | 0.938 | 0.891 | 0.894 |
| flight_direction | 6 | 0.721 | 0.822 | 0.802 | 0.822 | 0.822 | 0.822 | 0.754 | 0.908 | 0.822 | 0.784 | 0.908 | 0.908 | 0.908 | 0.908 |
| multi_constraint | 9 | 0.832 | 0.730 | 0.427 | 0.773 | 0.730 | 0.730 | 0.761 | 0.730 | 0.824 | 0.730 | 0.828 | 0.857 | 0.857 | 0.915 |
| named_entity | 18 | 0.826 | 0.831 | 0.766 | 0.878 | 0.831 | 0.831 | 0.874 | 0.831 | 0.831 | 0.827 | 0.874 | 0.913 | 0.905 | 0.919 |
| no_diacritics | 12 | 0.219 | 0.743 | 0.674 | 0.733 | 0.743 | 0.743 | 0.738 | 0.743 | 0.743 | 0.726 | 0.738 | 0.749 | 0.749 | 0.805 |
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

**Độ tin cậy router (không LLM, `queryPlan.confidence`, arm F1–F6):** 59 / 154 câu < 1 (10 câu ≤ 0,5); lý do `long_multi_constraint` 48, `weak_taxonomy_cue` 11, `multi_vertical` 10. nDCG@10 của F1–F6 trên nhóm này 0,770 (n = 59) so 0,850 (n = 88, độ tin cậy 1) — đây là nhóm câu đề xuất LLM fallback nhắm tới (`docs/prd/update-archive/2026-10-06-search-llm-fallback-query-plan.md`, chờ chốt).

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
v3) → yếu và không cắt khỏi BM25. Dù vậy `_tax_strong` (chỉ lọc khi có cue mạnh) thua F4 đủ 1,1 điểm trên toàn gold (TIE) — cue yếu
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

**Kênh fuzzy:** 0,75 (−0,6) tốt hơn 0,6 (−1,2); không slice nào được lợi (lỗi chính tả tên đã do bước normalize xử lý) → giữ tắt
(`SEARCH_FUZZY_K=0`), mặc định ngưỡng 0,75 khi bật.

## 5. Đề xuất cấu hình (người dùng quyết định — chưa đổi mặc định nào)

| cờ / tham số | hôm nay | đề xuất | căn cứ |
|---|---|---|---|
| `SEARCH_DEST_FILTER` (F1) | tắt | **bật** | WIN (+3,3); bỏ khỏi ALL −2,0 (TIE sát ngưỡng) |
| `SEARCH_NO_DIACRITICS_MODE` (F2) | off | relax | trung tính khi không cutoff |
| `SEARCH_NEGATION_FILTER` (F3) | tắt | **bật** | +4,5; bỏ khỏi ALL → LOSE (−5,2); Forbidden câu phủ định → 0 |
| `SEARCH_TAXONOMY_FILTER` (F4) | tắt | **bật — cần ý kiến Web** (đổi số đếm tab, `docs/spec/product.md`) | +2,4; `taxonomy_collision` +21,8; bỏ khỏi ALL → LOSE (−2,1), Forbidden 0,065 |
| `SEARCH_ROUTE_FILTER` (F5) | tắt | **bật** | chiều bay 0,11 → 1,00; bỏ → Forbidden 0,210 |
| `SEARCH_NUMERIC_FILTER` (F6) | tắt | **bật** | constraint precision 0,79 → 0,92 (0,96 trong tổ hợp) |
| `SEARCH_TAXONOMY_STRONG_ONLY` | tắt | tắt | −1,1 so F4 đủ |
| `SEARCH_PARTY_FILTER` | tắt | tắt | −0,6; gold chỉ 3 câu có số khách |
| `SEARCH_TONE_NORMALIZE` | tắt | tắt (vô hại) | 0,0 — gold không có câu lệch kiểu dấu |
| `SEARCH_FUZZY_K` | 0 | 0 | −0,6 |
| `SEARCH_RRF_LEXICAL_WEIGHT` | 1,0 | 1,0 (thử 0,5 khi có thêm gold) | +1,2 trên F1–F6, TIE dev / test cùng chiều |
| `SEARCH_CUTOFF` | 0,62 (không cắt gì trên e5) | giữ | cutoff tuyệt đối vô dụng trên e5 |
| margin kết quả yếu (client, contract §3.4) | 0,06 | **0,058** | §4 |
| rerank online | không có | không (chỉ offline) | +3,9 nhưng ~3,4 s CPU/câu, constraint precision 0,93 |

Bật cờ production đổi hành vi `/search` hôm nay → cần người dùng chốt (và Web cho F4) trước khi đổi `.env` / `core/config.py`;
cherry-pick `release-mvp-v2` sau đó.

## 6. Nhãn hole (máy, QAnh đã duyệt)

| đợt | nguồn | cặp | câu | auto_ooc | phân bố 0 / 1 / 2 |
|---|---|---:|---:|---:|---|
| D9a | run r1 (21 arm) | 829 | 121 | 56 | 374 / 196 / 259 |
| D9b | run r2 (42 arm, trước sửa fuzzy) | 871 | 140 | 60 | 372 / 214 / 285 |
| D9c | 13 arm chạy lại sau sửa fuzzy | 69 | 36 | 9 | 25 / 16 / 28 |
| D9d | chạy lại sau sửa parser | 14 | 5 | 0 | 0 / 10 / 4 |
| D9e | 3 arm F1–F6 | 16 | 14 | 0 | 0 / 10 / 6 |

Sau khi gán, pass rubric v4 (đề xuất v4 §4.1–4.2) hạ 150 nhãn 1 sai loại / dưới sao về 0 (D9a 51, D9b 93, D9c 6) và QAnh
chấp nhận mọi dòng (`history/2026-10-06-gold-v5-hole-d9-rubric-v4-nhan-1.md`) → tag `gold_v5`. Gán bằng agent theo gói slice với `docs/spec/bench/gold-guide.md` + nhãn sẵn có của chính câu làm mốc; đối chiếu luật cho câu phủ định v4 +
vé máy bay: luật khớp gold người 313/322 (97 %), khớp nhãn máy D9a 99/101 và D9b 74/75 (lệch đều do "dòng Tiện ích" ghi tiện ích bị loại
trừ — nhãn máy đúng theo #3/#14). Sửa tay hai điểm: 14 cặp `multi_constraint` hạ 2 → 1 (sao dưới ngưỡng, khớp nhãn người), Pullman Phú
Quốc (c0685) 2 → 0. Agent chỉ ra nhãn cũ nghi sai (không sửa — gold chỉ thêm): c0394 Moscow Hotel Ha Long nhãn 2 cho câu Hà Nội; c0426
Bao Phuc (Cát Bà) nhãn 0 trái quy ước #1; c0439 / c0253 / c0247 có nhãn trước quy ước #3 / #6 mâu thuẫn nhãn mới.

## 7. Caveat khi trích dẫn

- **Nhãn máy** chiếm 1.799 / 7.590 nhãn (24 %) và toàn bộ phần lấp hole; QAnh duyệt hàng loạt sau pass rubric v4 (không soát từng cặp).
  Chiếu rubric v4 lúc chấm đổi 164 nhãn cũ v1–v3 (158 nhãn 1 + 6 nhãn 2, 35 câu) thành 0 — tắt `metrics.rubric_v4_projection` để so số
  kiểu cũ; `allowed_variants` là chú giải máy (rà 06/10: sửa c0078, c0724 bỏ `attraction`, không đổi số).
- n nhỏ: 13 câu phủ định, 6 câu chiều bay (+ 3 câu bay khác), 5 câu lẫn loại, 7 câu ngoài catalog; mỗi split 77 câu.
- Bảng cue F4, từ vựng tiện ích và ba sửa parser được làm sau khi xem gold (trong mẫu với toàn gold, dù ngưỡng chọn theo dev).
- Không HTTP, không Cohere; độ trễ là engine trên Weaviate local với vector truy vấn đã cache. Rerank: CPU laptop, điểm có cache.
- Danh sách tiện ích catalog của một số khách sạn dừng ở đúng 60 chuỗi (giới hạn nguồn) → F3 có thể không thấy tiện ích bị loại trừ.
- `filter_recall_loss` của F4 cao (278) vì rubric v3 #2 cho 1 điểm "đúng nơi, sai loại" — filter loại các nhãn 1 đó đúng theo ý câu.

## 8. Lệnh tái sinh

```bash
# từ <repo>/src, PYTHONPATH=<repo>/src PYTHONUTF8=1, python = <repo>/.venv-sbench/Scripts/python; Weaviate bench local (config/sbench.yaml)
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 run --arm APP.e5s.hybrid_norm_nocut --arm APP.e5s.hybrid_norm_nocut_f1f6 … 
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 rescore 
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 compare APP.e5s.hybrid_norm_nocut APP.e5s.hybrid_norm_nocut_f1f6 [--split dev|test]
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 guards --arms APP.e5s.hybrid_norm_nocut,APP.e5s.hybrid_norm_nocut_f1f6
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 weak-results --arm APP.e5s.hybrid_norm_nocut_f1f6 --split dev --top-grid 0.7 --margin-grid 0.05,0.054,0.056,0.058,0.06,0.07
python -m evaluation.search_bench --run-id 2026-10-06-gold-v4-r2 gold holes --arms <45 arm> --tag D9x    # hole còn lại: 0
```

Bảng §2 sinh từ `per_query@untagged.parquet` / `results@untagged.json` của từng arm + dòng verdict của `sb compare`; split từ
`devtest@gold_v4.json`.

## 9. Cấu hình production 06/10 (người dùng chốt) — đo lại trên `gold_v5`

Người dùng chốt 06/10: **e5-small** (đề xuất FR-SRC-02 đã áp dụng, `docs/prd/update-archive/2026-10-05-fr-src-02-embedding-local-e5-small.md`),
**F1, F2, F3, F5, F6 bật, F4 tắt** (F4 đổi số đếm tab của Web), `SEARCH_CUTOFF` 0,84 + cutoff câu không dấu 0,80, **LLM fallback** thêm vào
(đề xuất đã áp dụng, mặc định `off`). Arm `APP.e5s.prod_f12356` = đúng mặc định mới của `core/config.py`; `_nocut` = cùng cờ, cutoff −1.
Cùng run `2026-10-06-gold-v4-r2`, `gold_v5` + chiếu rubric v4.

| arm | nDCG@10 | R@10 | Judged@10 | nDCG v3 | nDCG v4 | dev | test | Forbidden@10 | Chiều bay | Constraint prec. | ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| production hôm qua `hybrid_norm` (cờ tắt, cutoff 0,62) | 0.711 | 0.352 | 1.00 | 0.738 | 0.528 | 0.724 | 0.691 | 0.539 | 0.11 | 0.79 | 55 / 84 |
| **production mới `prod_f12356`** | **0.798** | **0.391** | 0.999 | 0.799 | 0.789 | 0.810 | 0.785 | 0.065 | 1.00 | 0.91 | 12 / 54 |
| `prod_f12356_nocut` | 0.797 | 0.389 | 1.00 | 0.798 | 0.789 | 0.808 | 0.785 | 0.065 | 1.00 | 0.91 | 12 / 53 |
| F1–F6 có F4, cutoff 0,84 (`hybrid_norm_c84_dest_nodia_nc80_qp`) | 0.817 | 0.400 | 1.00 | 0.816 | 0.824 | 0.822 | 0.812 | 0.000 | 1.00 | 0.95 | 11 / 65 |

Win rule: production mới vs `hybrid_norm` **WIN** (Δrecall +3,82, p 0,003, slice kém nhất `no_diacritics` −1,0); dev ΔnDCG +8,4 / test +9,0 (mỗi
nửa "không thắng" vì một slice nhỏ tụt > 3: `parent_child` −3,6 dev, `flight_direction` −6,0 test); `_nocut` vs `prod_f12356` TIE (cutoff 0,84
không đổi gì đo được); F1–F6 có F4 vs production mới **TIE** (ΔnDCG +1,9 < 2). Judged@10 0,999: một cặp chưa nhãn (c0078 "đường bay tới Huế" →
khách sạn Huế, sai loại cốt lõi theo rubric v4 nên nhãn sẽ là 0 = như chưa nhãn; không tạo gold mới cho một cặp).

**Cái giá của F4 tắt — guard Phase A:** Forbidden@10 0,000 → **0,065** (c0697 "khách sạn ở Grand World", c0706 "combo vé máy bay và khách
sạn Đà Lạt", c0709 "khách sạn Vinpearl ở Nha Trang", c0088 "voucher golf tại Hội An" — sản phẩm sai loại cốt lõi lọt top-10) và constraint
precision 0,96 → **0,91** (FAIL ngưỡng đề xuất 0,95). Nếu Web đồng ý cách đếm tab, bật F4 trả lại cả hai guard (+1,9 nDCG).

**Regression:** `regression/baseline_v1.json` đặt lại = `APP.e5s.prod_f12356` (nDCG@10 0,798, recall@10 0,352 → 0,391); `sb regress check` PASS.

**LLM fallback — đo 06/10 chiều (gpt-4o-mini):** cache 155 câu gold nạp bằng `prewarm_llm_hypotheses` (0 lỗi, 240 s), bench phát lại
(`cache_only`). Arm `APP.e5s.prod_f12356_llm` (ngưỡng 0,75, mặc định) kích hoạt **10** câu; `_llm100` (ngưỡng 1,0) kích hoạt **59** câu. Cả hai:
**0 trường được nhận, top-10 đổi 0/154, nDCG@10 0,798 = production** (TIE tuyệt đối). Lý do: trên 59 câu độ tin cậy thấp, LLM trùng plan luật
về loại 59/59 và điểm đến 58/59; phần "thêm" chỉ là số khách ở 2 câu (c0147, c0284 — cờ party tắt nên không áp) và một tiện ích bị loại
trừ bịa ở c0214 ("phòng không hút thuốc" là yêu cầu dương → `smokingRoom` bị kiểm catalog từ chối, `invalid_value`); 7 lượt `destination`
bị từ chối `not_flight` (LLM điền thành phố đến cho câu không phải vé máy bay). Lý do độ tin cậy thấp chủ yếu là `long_multi_constraint`
(48) — câu dài mà luật vẫn parse đúng, nên trigger hiện tại gọi LLM khi không cần. **Kết luận:** trên gold này LLM fallback không có lợi
cũng không gây hại (kiểm catalog chặn đúng giá trị sai); giữ `off` cho production, có thể bật `shadow` để thu câu thật trước khi xét `on`;
nên siết trigger (bỏ `long_multi_constraint` khỏi lý do kích hoạt) trước khi đo lại.
