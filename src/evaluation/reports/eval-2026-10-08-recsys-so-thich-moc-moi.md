# Đo lại mốc RecSys bám sở thích trên engine production (WP0.4)

- Ngày chạy: 2026-10-08
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04 (`docs/prd/requirements.md` §1.3), AC-REC-02
- Plan: `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` WP0
- Báo cáo nghiên cứu gốc (số cần đối chiếu): `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` §4.2
- Kết quả gốc của lượt này: `src/evaluation/recsys_bench/theme_study/results/2026-10-08-wp0-wp3/` (`wp0_800_*.json`)

## 1. Câu hỏi của WP0

Số bước 1–2 của nghiên cứu 08/10 chạy trên working tree của `bench_search_recomSys` — engine đó **chưa có** `9b703ba`
(cap lặp chỉ giới hạn trọng số vector; "hôm nay" theo giờ VN; parser `usingDate` dùng chung). Nhánh bàn giao
`feat/recSys_update` dựng từ `release-mvp-v2` @ `6f77e80` nên **đã có**. Câu hỏi: bảng §4.2 của báo cáo cuối còn dùng được
trên engine này không, hay phải đo lại toàn bộ nghiên cứu?

## 2. Môi trường

| | |
|---|---|
| Commit | `d25ff4a` (nhánh `feat/recSys_update`, base `release-mvp-v2` @ `6f77e80`) + thay đổi WP0–WP2 của lượt này |
| `ENGINE_RULES_VERSION` | `2026-10-02-trip-ended`; `W_SHORT/W_POP/W_LONG` = 0,7 / 0,15 / 0,15 |
| Dữ liệu | `vota_prodcopy` — bản sao chỉ-đọc production 08/10 01:49, nạp từ `vota_prodcopy.dump` của gói bàn giao (`pg_restore`, Postgres 16.15) |
| Kiểm dữ liệu sau nạp | `cdp.products` 16 740 · `cdp.events` 40 158 · `cdp.profiles` 7 005 · `catalog.combo_items` 442 · `catalog.product_meta` 3 991 search unit / 3 254 recommendable — khớp `HUONG-DAN.txt` |
| Vector | `vec_prodcopy_e5s.npy` của gói bàn giao (3 991 × 384, `intfloat/multilingual-e5-small` rev `614241f622f53c4eeff9890bdc4f31cfecc418b3`, `catalog-text-v2`). Cả 18 dòng `sha256sum -c SHA256SUMS`: OK |
| `as_of` | `2026-10-08T00:00:00+00:00` |
| Mẫu | 800 khách đầu theo id mỗi split — **cùng cỡ mẫu với bảng cũ**, để chênh lệch chỉ do engine (LLBO 800, temporal 775 = toàn bộ, nexttrip 800); khách giả lập seed 7, `--n-syn 80` |
| Weaviate | không gọi (đo bằng `--vec npy:`); env trỏ `127.0.0.1:59999` để chắc chắn không chạm cloud |

## 3. Parity giữa `profile_variants` và `build_profile`

`profile_variants.py` được viết lại trong lượt này (plan WP0.3): bản cũ tính tuổi chuyến, `ends_on`,
`purchased_taxonomies` và `bought_units` trên event **còn lại sau cap**, tức luật trước `9b703ba`; engine của nhánh này
tính bốn thứ đó trên **mọi** event. Parity cũng được mở rộng từ 3 lên 8 phép so:

| Phép so | Kết quả (200 khách LLBO) |
|---|---|
| `set(trips)`, `u_long`, `active_trip.trip_id` (bản cũ có) | 0 lệch |
| `bought_units`, `n_events`, `strategy` | 0 lệch |
| Từng `Trip`: `age_days`, `ends_on`, `ended`, `purchased_taxonomies`, `destination`, `len(events)` | 0 lệch |
| Vector từng chuyến `Trip.vec` | 0 lệch |

`parity_mismatch_llbo200 = 0`, `parity_mismatch_by_field = {}` trong cả 4 file kết quả. Nói cách khác: với mọi công tắc
tắt, bản viết lại **là** `build_profile` của engine, nên chênh lệch giữa P0 và P1/P2/P4 chỉ còn do đúng ba công tắc.

## 4. Bảng mốc mới so với bảng cũ

Dòng `↳ 08/10 (engine cũ)` lấy thẳng từ `results/2026-10-08/*.json` của bàn giao. Ô trống = cấu hình đó không có số split
thật trong JSON bàn giao (báo cáo cuối §4.2 ghi chú ¹: split thật của P0+F7 chạy ở worktree khác, chỉ còn cột theme).

<!-- bảng sinh bằng: python -m src.evaluation.recsys_bench.theme_study.tables metrics p1_a.json p1_b.json
     --baseline-dir src/evaluation/recsys_bench/theme_study/results/2026-10-08 -->

| Cấu hình | LLBO h@20 | LLBO nDCG@10 | LLBO h@4 | temp h@20 | temp nDCG@10 | temp h@4 | next h@20 | next nDCG@10 | next h@4 | theme between | theme noisy | theme open |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P0_prod+F0_prod | 0.8363 | 0.525 | 0.5737 | 0.1587 | 0.0954 | 0.1135 | 0.0737 | **0.0168** | **0.0163** | 0.438 | 0.373 | 0.767 |
| ↳ 08/10 (engine cũ) | 0.8363 | 0.525 | 0.5737 | 0.1587 | 0.0954 | 0.1135 | 0.0737 | 0.016 | 0.015 | 0.438 | 0.373 | 0.767 |
| P0_prod+F7_betweenMinmaxPop30 | 0.8363 | 0.525 | 0.5737 | 0.129 | 0.0895 | 0.1058 | 0.0387 | 0.01 | 0.0075 | 0.776 | 0.447 | 0.767 |
| ↳ 08/10 (engine cũ) | | | | | | | | | | 0.776 | 0.447 | 0.767 |
| P2_confidence+F0_prod | 0.8363 | 0.5221 | 0.5725 | 0.1548 | 0.0929 | 0.1123 | 0.0675 | **0.016** | **0.0187** | 0.431 | 0.404 | 0.767 |
| ↳ 08/10 (engine cũ) | 0.8363 | 0.5221 | 0.5725 | 0.1548 | 0.0929 | 0.1123 | 0.0675 | 0.0151 | 0.0175 | 0.431 | 0.404 | 0.767 |
| P2_confidence+F7_betweenMinmaxPop30 | 0.8363 | 0.5221 | 0.5725 | 0.1303 | 0.0884 | 0.1058 | 0.0275 | **0.0091** | **0.0075** | 0.763 | 0.666 | 0.767 |
| ↳ 08/10 (engine cũ) | 0.8363 | 0.5221 | 0.5725 | 0.1303 | 0.0884 | 0.1058 | 0.0275 | 0.0083 | 0.0063 | 0.763 | 0.666 | 0.767 |
| P2_confidence+F13a_betweenCenter | 0.8363 | 0.5221 | 0.5725 | 0.1213 | 0.0835 | 0.0994 | 0.025 | **0.0079** | **0.0075** | 0.772 | 0.744 | 0.767 |
| ↳ 08/10 (engine cũ) | 0.8363 | 0.5221 | 0.5725 | 0.1213 | 0.0835 | 0.0994 | 0.025 | 0.0071 | 0.0063 | 0.772 | 0.744 | 0.767 |
| P2_confidence+F14_betweenQuantilePop30 | 0.8363 | 0.5221 | 0.5725 | 0.1239 | 0.0874 | 0.1045 | 0.0262 | **0.0081** | **0.0075** | 0.782 | 0.723 | 0.767 |
| ↳ 08/10 (engine cũ) | 0.8363 | 0.5221 | 0.5725 | 0.1239 | 0.0874 | 0.1045 | 0.0262 | 0.0073 | 0.0063 | 0.782 | 0.723 | 0.767 |

Calibration F14 trên P2 (seed 99, 120 request): `q_low_p10 = 0.8529`, `q_high_p99 = 0.9387` — **đúng hai ngưỡng** in trong
báo cáo cuối §4, nên lượt cũ cũng calibrate trên P2.

## 5. Kết luận

1. **Bảng cũ dùng được, trừ hai cột.** 58 / 60 ô có số ở cả hai engine **khớp đến chữ số cuối**: LLBO (cả ba chỉ số),
   temporal (cả ba), nexttrip hit@20, và cả ba cột theme của khách giả lập.
2. **Chênh duy nhất ở nexttrip nDCG@10 và nexttrip hit@4**, cùng dấu và cùng độ lớn ở mọi cấu hình: nDCG@10
   **+0,0008 … +0,0009**, hit@4 **+0,0012 … +0,0013**. hit@4 = 0,0012 trên 800 khách là **1 khách**. Khớp đúng dự đoán
   §2.3 của báo cáo cuối và §3.D (bản sao production chỉ có 10 event bị cap, trên 8 / 5 599 khách).
3. Engine mới **tốt hơn một chút** ở hai cột đó, đều ở phía nexttrip — tức mức giảm nexttrip mà báo cáo cuối ghi là
   *cận trên*, nay còn hơi rộng hơn cận trên thật.
4. **Không cần đo lại nghiên cứu.** Chỉ cần thay hai cột nexttrip nDCG@10 / hit@4 trong bảng §4.2 bằng số ở đây. Mọi so
   sánh và kết luận của báo cáo cuối (F7/F13a/F14 so với F0; P2 so với P0) không đổi, vì chúng dựa trên hit@20 và theme.
5. P0+F7 vẫn chưa có số split thật đo trên engine này ở cỡ mẫu 800 — lượt WP2 (toàn bộ khách) đã có; ô trống trong bảng
   trên là của **JSON bàn giao**, không phải của lượt này.

## 6. Lệnh tái sinh

```bash
# 0. Nạp bản sao production từ gói bàn giao (một lần)
docker run -d --name vota-prodcopy-pg -e POSTGRES_PASSWORD=postgres -p 127.0.0.1:55433:5432 postgres:16
docker exec vota-prodcopy-pg createdb -U postgres vota_prodcopy
docker exec -i vota-prodcopy-pg pg_restore -U postgres --no-owner --no-privileges -d vota_prodcopy < vota_prodcopy.dump

# 1. Env (ba DSN cùng trỏ bản sao; Weaviate cố tình không tới được)
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55433/vota_prodcopy
export CDP_DATABASE_URL=$DATABASE_URL
export EVAL_DATABASE_URL=$DATABASE_URL
export WEAVIATE_URL=http://127.0.0.1:59999
export PYTHONIOENCODING=utf-8        # Windows: không có biến này thì script chết khi in tên điểm đến

# 2. Hai lượt đo (chạy song song tối đa 2 tiến trình)
VEC=npy:/đường/dẫn/vectors/vec_prodcopy_e5s
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC \
  --as-of 2026-10-08T00:00:00+00:00 --profiles P0_prod,P2_confidence \
  --scorers F0_prod,F7_betweenMinmaxPop30 --n-syn 80 --max-users 800 \
  --scenarios between,open,noisy --syn-seeds 7 --out p1_a.json          # 643 s
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC \
  --as-of 2026-10-08T00:00:00+00:00 --profiles P2_confidence \
  --scorers F13a_betweenCenter,F14_betweenQuantilePop30 --f14-cal-profile P2_confidence \
  --n-syn 80 --max-users 800 --scenarios between,open,noisy --syn-seeds 7 --out p1_b.json   # 327 s

# 3. Bảng
python -m src.evaluation.recsys_bench.theme_study.tables metrics p1_a.json p1_b.json \
  --baseline-dir src/evaluation/recsys_bench/theme_study/results/2026-10-08
```

## 7. Caveat khi trích dẫn

1. Cỡ mẫu 800 khách đầu **theo id** mỗi split, giữ nguyên để so được với bảng cũ — không phải mẫu ngẫu nhiên. Lượt WP2
   (`eval-2026-10-08-recsys-so-thich-ci.md`) chạy toàn bộ khách.
2. Chưa có CI ở bảng này; nó chỉ trả lời "engine mới có đổi số cũ không", không trả lời "cấu hình nào tốt hơn".
3. Bản sao production chụp 08/10 01:49 và có event thật của người bàn giao — không chia sẻ rộng.
4. `theme` của `noisy` ở bảng này là cohort **độc lập** với `between` (luật cũ, giữ để so với bảng cũ). Cohort ghép cặp
   `noisy_paired` chỉ có trong lượt WP2.
