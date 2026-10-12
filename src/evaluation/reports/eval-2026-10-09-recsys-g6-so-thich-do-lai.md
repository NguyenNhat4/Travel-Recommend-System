# G6: đo lại RecSys trên dữ liệu event CÓ sở thích chủ đề (lane B2) — đầu vào để chốt lại G2

- Ngày chạy: 2026-10-09
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04; gate G2 (`docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7)
- Plan: `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` lane B2
- Kết quả gốc: `src/evaluation/recsys_bench/theme_study/results/2026-10-09-g6-pref-v1/` (JSON từng cấu hình, `ci_*.json`,
  `append_receipt.json`, `themes.json` — nhãn ẩn, chỉ để chấm); split đóng băng `frozen/split-*-g6pref-v1-asof20261008.json`
- Commit code: `47f1710` (profile seed `g6-pref-v1`), engine = production `6f77e80` (chưa đổi)

## 1. Vì sao có lượt này

Split thật trên bản sao production **không đo được** lợi ích bám sở thích: `seed_histories.plan_trip` bốc điểm đến độc lập
với khách (`eval-2026-10-08-recsys-g2-va-wp4.md` §2.2). Người dùng chốt làm G6 trước: sinh lại lịch sử với sở thích chủ đề
ẩn, đo lại 4 cấu hình, rồi chốt lại G2.

## 2. Dữ liệu G6

| | |
|---|---|
| DB | `vota_g6pref_v1` trên `vota-prodcopy-pg` :55433 — `pg_restore` từ dump bàn giao (catalog **y hệt** prodcopy: 16.740 `cdp.products`, 442 `combo_items` → vector `.npy` vẫn hợp lệ), `TRUNCATE cdp.events`, `DELETE FROM cdp.profiles` (app.* rỗng) |
| Sinh | `append_histories prepare --batch g6pref-v1 --profile g6-pref-v1 --as-of 2026-10-08 --seed 42` → `apply`; artifact sha `60d77c38…`; **5.000 profile, 32.747 event**, event 2024-10-09 … 2026-10-07 |
| Tham số profile (`seed/config.py` §4.3, chờ người dùng chốt) | `THEME_PREF_RATE 0,8` · `THEME_NO_PREF_SHARE 0,30` · mix theo khối lượng bookable · `DEST_THEMES` 15 biển / 16 núi / 10 phố; 7 điểm đến chưa nhãn + "mixed" = không chủ đề |
| Nhãn | **3.496 / 5.000** khách có chủ đề (sidecar `themes.json`, không có trong DB; engine không đọc) |
| Kiểm "dữ liệu có tín hiệu" (SQL trên chuyến đã mua) | Chuyến của khách có chủ đề nằm đúng chủ đề: biển 0,902 · phố 0,890 · núi 0,770 (núi thấp vì thiếu vertical → bốc lại toàn cục, MOCK_DATA_SPEC §4.3). **Hai chuyến liên tiếp cùng chủ đề:** biển 0,820 · phố 0,810 · núi 0,633 so với **0,378** ở khách không sở thích (= xác suất toàn cục) → split nexttrip có tín hiệu để thưởng việc bám sở thích |
| Split (toàn bộ khách) | LLBO 3.003 · temporal 660 · nexttrip 1.552 · coldstart 3.750 |
| Calibration F14 trên G6 | q = 0,8588 / 0,9391 (so 0,8529 / 0,9387 trên prodcopy); mọi lượt **ghim** q = 0,8529 / 0,9387 (`--f14-q`, hằng sẽ ship) |

## 3. Kết quả

Cấu hình: C0 production · C1 P2 · C2 P2 + F14c · C3 P2 + F14c + destCap2 (**tổ hợp đã chốt G3**) · tune: T1 P2 + F7 + destCap2,
T2 P2 + F14d (pop 0,45) + destCap2. Khách giả lập 3 seed (`--syn-target`), cùng `as_of`.

| Cấu hình | LLBO h@4 | temp h@20 | temp destHit | **next h@20** | **next destHit@20** | cold h@4 | theme btw | theme noisy | tgtHit@20 | nextDestHit@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C0 production | 0.5048 | 0.1409 | 0.700 | 0.0767 | 0.6727 | 0.6549 | 0.450 | 0.361 | 0.0014 | 0.3958 |
| C1 P2 | 0.5028 | 0.1439 | 0.708 | 0.0702 | 0.6759 | 0.6544 | 0.453 | 0.402 | 0.0014 | 0.4056 |
| C2 P2+F14c | 0.5028 | 0.1167 | 0.447 | 0.0445 | 0.3911 | 0.6544 | 0.774 | 0.731 | 0.0111 | 0.1569 |
| **C3 P2+F14c+destCap2** | 0.5028 | 0.1182 | 0.706 | 0.0445 | **0.7152** | 0.6541 | 0.759 | 0.725 | 0.0097 | 0.4125 |
| T1 P2+F7+destCap2 | 0.5028 | 0.1136 | 0.700 | 0.0419 | 0.7197 | 0.6547 | 0.757 | 0.715 | 0.0097 | 0.4181 |
| T2 P2+F14d+destCap2 | 0.5028 | 0.1288 | 0.730 | 0.0528 | **0.7429** | 0.6544 | 0.585 | 0.562 | 0.0083 | 0.4208 |

CI ghép cặp so với production (bootstrap 2.000):

| | C3 P2+F14c+destCap2 | T2 P2+F14d+destCap2 | T1 P2+F7+destCap2 |
|---|---|---|---|
| LLBO h@4 | −0,0020 [−0,0040, −0,0003] | −0,0020 [−0,0040, −0,0003] | −0,0020 [−0,0040, −0,0003] |
| LLBO h@20 | −0,0010 [−0,0027, +0,0003] | — | — |
| coldstart h@4 / h@20 | −0,0008 [−0,0027, +0,0011] / −0,0024 [−0,0043, −0,0011] | — | — |
| temporal h@20 | −0,0227 [−0,0364, −0,0091] | −0,0121 [−0,0258, **+0,0000**] | −0,0273 [−0,0409, −0,0136] |
| temporal h@4 | −0,0061 [−0,0167, +0,0045] | — | — |
| **nexttrip h@20** | **−0,0322** [−0,0425, −0,0219] | **−0,0238** [−0,0335, −0,0142] | −0,0348 [−0,0457, −0,0245] |
| nexttrip h@4 | −0,0039 [−0,0097, **+0,0019**] | — | — |
| nexttrip nDCG@10 | −0,0044 [−0,0080, −0,0008] | — | — |
| **nexttrip destHit@20** | **+0,0425** [+0,0213, +0,0631] | **+0,0702** [+0,0522, +0,0896] | +0,0470 [+0,0258, +0,0689] |
| theme `between` | +0,3089 [+0,2822, +0,3333] | +0,1351 [+0,1190, +0,1506] | +0,3073 [+0,2826, +0,3308] |
| theme `noisy_paired` | +0,3634 [+0,3311, +0,3947] | +0,2005 [+0,1814, +0,2189] | +0,3538 [+0,3203, +0,3844] |
| tgtHit@20 (giả lập) | +0,0083 [+0,0014, +0,0167] | — | — |
| nextDestHit@20 (giả lập, between) | +0,0167 [−0,0222, +0,0556] | — | — |

Chia theo nhãn ẩn, C3 so với production trên nexttrip:

| Nhóm | n | hit@20 | destHit@20 |
|---|---:|---|---|
| khách **có** chủ đề | 1.073 | −0,0401 [−0,0522, −0,0279] | **+0,0494** [+0,0261, +0,0736] |
| khách không sở thích | 479 | −0,0146 [−0,0334, +0,0021] | +0,0271 [−0,0126, +0,0710] |

Nhiễu làm mất theme trên cùng khách (`between` → `noisy_paired`): production −0,089 · P2 −0,051 · C3 −0,034.

## 4. Đọc kết quả

1. **Bám sở thích hiện ra ở mức điểm đến, có ý nghĩa thống kê.** Với dữ liệu có sở thích, C3 đưa đúng *điểm đến* của chuyến
   kế tiếp vào list 20 nhiều hơn production +4,3 điểm (+4,9 ở khách có chủ đề); C2 (không cap) thì −28 → **destCap2 là phần
   không thể thiếu**, đúng kết luận 08/10.
2. **Nhưng hit@20 *món* vẫn giảm −0,032 — y hệt trên prodcopy**, và giảm *nhiều hơn* ở khách có chủ đề (−0,040) dù họ được
   đúng điểm đến hơn. Lý do nằm ở bộ sinh: sở thích chỉ ở **mức điểm đến**; *khách sạn nào* trong điểm đến đó vẫn bốc theo
   Zipf (độ phổ biến, `seed_histories.Sampler`), nên công thức nào hạ trọng số pop cũng thua ở bước chọn món trong điểm đến.
   Dữ liệu thật có giống vậy không thì chưa biết — đây là giới hạn của G6 phiên bản này, không phải của engine.
3. **Ở cỡ list khách thật nhìn thấy (k = 4), chi phí món không phân biệt được**: nexttrip h@4 −0,0039 [−0,0097, +0,0019],
   temporal h@4 −0,0061 [−0,0167, +0,0045]. Mức −0,032 là của list 20 (chế độ eval, không cap taxonomy).
4. Luật đóng G2 đề nghị (D1–D5): **D1 không đạt** ở mọi cấu hình (cận dưới CI nexttrip h@20 ≤ −0,014); D2 **đạt** (destHit
   cận dưới > 0, cả ba); D3 đạt trong dung sai 0,01 (LLBO h@4 −0,002, coldstart ≈ 0); D4 đạt (temporal ≥ −0,04); D5 `tgtHit@20`
   đạt, `nextDestHit@20` giả lập chưa phân biệt được.
5. **Núm vặn pop**: T2 (pop 0,45) mua destHit +0,070 và temporal trong nhiễu với giá theme chỉ +0,135 / +0,200 — không đạt
   tiêu chí theme ≥ 0,15 ở `between`. Không có điểm nào trên đường đánh đổi này đạt cả D1 lẫn theme.

## 5. Caveat

1. G6 chỉ cho sở thích ở mức điểm đến; chọn món trong điểm đến vẫn theo độ phổ biến → nexttrip/temporal *món* vẫn thưởng
   pop. Muốn đo "đúng món" cần sở thích ở mức thuộc tính sản phẩm (resort / homestay, giá…) — ngoài phạm vi G6 này.
2. Tham số G6 (p = 0,8; 30 % không sở thích; mix theo khối lượng) chưa được người dùng chốt; kết quả chỉ đổi ở biên độ, không
   đổi chiều (C2 → C3 đã kiểm ở cả prodcopy lẫn G6).
3. Nhãn chủ đề có mặt ở 51 / 58 điểm đến; núi thiếu vertical nên tỷ lệ cùng chủ đề thấp hơn mục tiêu.
4. Mọi số offline trên hai DB nghiên cứu; chưa A/B.
5. Ô khám phá B không đo lại trên G6: nó chỉ chạm khách có chuyến mở (LLBO) và đã có số trên prodcopy
   (`eval-2026-10-08-recsys-g2-va-wp4.md` §4, `--how ulong`); G6 không đổi gì ở nhánh đó.

## 6. Lệnh tái sinh

```bash
# DB (một lần)
docker exec vota-prodcopy-pg createdb -U postgres vota_g6pref_v1
docker exec -i vota-prodcopy-pg pg_restore -U postgres --no-owner --no-privileges -d vota_g6pref_v1 < vota_prodcopy.dump
docker exec vota-prodcopy-pg psql -U postgres -d vota_g6pref_v1 -c "TRUNCATE cdp.events" \
  -c "DELETE FROM cdp.profiles p WHERE NOT EXISTS (SELECT 1 FROM app.users u WHERE u.cdp_user_id = p.cdp_user_id)"
cd src && SEED_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55433/vota_g6pref_v1 PYTHONUTF8=1 \
  python -m data_collection.seed.append_histories prepare --batch g6pref-v1 --profile g6-pref-v1 --as-of 2026-10-08 --seed 42 --out g6/prep && \
  python -m data_collection.seed.append_histories apply --artifact g6/prep/batch.json --receipt g6/receipt.json; cd ..
# Đo (env: ba DSN -> vota_g6pref_v1; PYTHONUTF8=1)
VEC=npy:/đường/dẫn/vec_prodcopy_e5s; AS=2026-10-08T00:00:00+00:00
SYN="--n-syn 80 --scenarios between,open,noisy_paired --syn-seeds 42,7,2026 --syn-target"; SPL="--splits llbo,temporal,nexttrip,coldstart --max-users 0"
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS --profiles P0_prod --scorers F0_prod $SPL $SYN --per-user-out c0.jsonl --out c0.json          # 578 s
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS --profiles P2_confidence --scorers F0_prod,F14c_betweenQuantilePop35 \
  --f14-cal-profile P2_confidence --f14-q 0.8529,0.9387 $SPL $SYN --per-user-out c12.jsonl --out c12.json                                             # 1180 s
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS --profiles P2_confidence --scorers F14c_betweenQuantilePop35 \
  --f14-cal-profile P2_confidence --f14-q 0.8529,0.9387 --dest-cap 2 $SPL $SYN --per-user-out c3.jsonl --out c3.json                                  # 554 s
# tune: thay --scorers F7_betweenMinmaxPop30 / F14d_betweenQuantilePop45 (cùng --dest-cap 2)
python -m src.evaluation.recsys_bench.theme_study.paired_ci --per-user c0.jsonl c12.jsonl c3.jsonl --baseline P0_prod+F0_prod --out ci_vs_prod.json
python -m src.evaluation.recsys_bench split --kind nexttrip --as-of 2026-10-08 --freeze --freeze-path src/evaluation/recsys_bench/frozen/split-nexttrip-g6pref-v1-asof20261008.json
```
