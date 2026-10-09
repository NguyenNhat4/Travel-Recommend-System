# Công thức điểm OPH-L so với công thức production — kết quả bench (TUNE → TEST một lần)

- Ngày chạy: 2026-10-09 · nhánh `feat/recSys_update-2` · harness commit `8f37f0d` (S1), `cf8a26e` (kịch bản mới), đóng băng
  `e182b94` (trước TEST), kết quả TUNE `e9bc354`
- Plan: `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` (§4 thang ablation, §7 giao thức) · Phục vụ FR-REC-01, FR-REC-02, FR-REC-04,
  NFR-PERF-01, AC-REC-02
- Dữ liệu: `vota_prodcopy` (bản sao production 08/10, container `vota-prodcopy-pg`); track N quyết thêm trên `vota_g6pref_v1`
  (DB lane B2, khách giả lập có sở thích). Vector `vec_prodcopy_e5s` (`intfloat/multilingual-e5-small`, `catalog-text-v2`),
  `WEAVIATE_URL` cố tình không tới được.
- Split đóng băng (sha256 12 ký tự đầu, kiểm bằng `Split.verify` mỗi lượt): llbo `0bff46bb8eac` · temporal `6b4302167980` ·
  nexttrip `f5bd9dc92e71` · coldstart `7c27c6310ef5` (`frozen/split-*-prodcopy-asof20261008.json`); DB G6 dùng
  `split-*-g6pref-v1-asof20261008.json` của lane B2 (đọc chỉ-đọc từ bản checkout chính, sha khớp).
- TUNE = `sha1(uid) mod 10 < 3` (llbo 1.230 · temporal 220 · nexttrip 582), khách giả lập seed 13. TEST = 70 % còn lại
  (llbo 2.793 · temporal 553 · nexttrip 1.253 · coldstart 3.630), seed 101/202/303, chạy **một lần** sau khi đóng băng.
- Kết quả gốc: `src/evaluation/recsys_bench/theme_study/results/2026-10-09-oph/` (JSON tổng hợp, CI, `SHA256SUMS` của file
  per-user; file per-user `.jsonl` không commit).

## 1. Cấu hình

| Tên | Định nghĩa (`theme_study/registry.py`) |
|---|---|
| `B0` | production 08/10 (P0 + F0) |
| `B1p` | B1′ = P2 của PR-A (confidence + CAP_EXEMPT_EVENTS) + ô khám phá B. **Không có gương loại combo** (đề xuất [C] đo ảnh hưởng offline ≈ 1 khách) |
| `B2` | B1′ + F14c (nhánh không chuyến mở: 0,65·cal(cos) + 0,35·pop, Q 0,8529/0,9387) + destCap2 |
| `+orig:pen:0.15` | O1: route bay có điểm xuất phát khác `ô` (suy từ event chuyến bay gần nhất) bị trừ 0,15 ở nhánh có chuyến mở, bị mask ở nhánh không chuyến |
| `+sess` | O3 + O4: chuyến **đã đặt** chưa diễn ra được ưu tiên làm `active_trip` (sửa I-3); không có thì gộp các chuyến chỉ-xem/giỏ đang mở thành chuyến ảo (decay 7 ngày, điểm đến = mode có trọng số) |

Chuỗi đóng băng (`frozen_chain.json`): **F_O** = `B1p+orig:pen:0.15+sess` · **F** = `B2+orig:pen:0.15+sess` · **OPH-prod**
(bản dự phòng G7, không F14c) = `B0+orig:pen:0.15+sess`.

## 2. Cổng parity

Đường code OPH với mọi công tắc tắt cho đúng list production: `B0:V0p`, `B1p:V1p`, `B2:V2p` **nDiscordant4 = nDiscordant20 = 0**
trên toàn bộ TUNE (llbo 1.230 / temporal 220 / nexttrip 582, 3 × 240 khách giả lập) — `p0_base.json`. `pop_h` ở chế độ hộp 90
ngày, α = 0 khớp `Popularity.unit_scores`: `B2:B2+popBox:90:0` nDiscordant = 0 mọi stratum (`p1_track_n.json`).

## 3. Quyết định trên TUNE (`p0_ci.txt`, `p1_*_ci.txt`; bootstrap ghép cặp 10.000 lần)

| Bậc | Đo trên TUNE | Quyết định |
|---|---|---|
| Trần Z-orig (đích bay → biết origin đúng) | LLBO không target-in-cart h@4 +0,0525 [+0,0360, +0,0690] | ≥ 0,01 → giữ O1/O2 |
| Trần Z-cart (đích nằm trong giỏ) | temporal h@4 +0,0500 [+0,0227, +0,0818] | ≥ 0,01 → giữ O5 để đo |
| O1 `orig:pen` 0,05 / 0,15 / 0,3 / mask | LLBO h@4 0,5520 / 0,5951 / 0,5943 / 0,5935 (B1p 0,5496); không target-in-cart w=0,15: +0,0150 [+0,0045, +0,0270] | **giữ, w = 0,15** (miễn B10 đã duyệt: temporal TUNE không đủ chuyến bay đích) |
| O3 ưu tiên chuyến đã đặt | split thật: không đổi; `booked_browse` xvAtX@4 +0,5518, tgtHit@4 +0,2487 | **giữ** (NI + conformance) |
| O4 chuyến ảo | LLBO h@20 +0,0065 [+0,0008, +0,0122]; nexttrip h@20 +0,0069 [+0,0017, +0,0137] | **giữ** |
| O5 `cart` 0,05 / 0,10 | LLBO h@4 +0,1187 / +0,1390 nhưng chỉ ở khách target-in-cart; temporal h@4 −0,0045 [−0,0136, +0,0000] | **bỏ** |
| N1 `pop_h` (grid H 45/90/180 × α 0/0,5/1/2) | prodcopy: thay đổi nhỏ; **DB G6**: themePrec −0,0389 … −0,0462 (cận trên < 0), không split thật nào tăng | **bỏ** |
| N2 dormant `H_L × 3` | không đổi split thật; G6 syn_dormant P3 −0,0127 [−0,0312, +0,0012] | **bỏ** (không tác dụng) |
| N3 dormant `w_pop` 0,5 | G6 syn_dormant P3 themePrec −0,2130 [−0,2662, −0,1597] | **bỏ** (vượt ngưỡng 0,10) |
| N4 first-time `w_pop` 0,45 | không khách nào chịu tác động | **bỏ** |

## 4. TEST (một lần) — số tuyệt đối (`p2_test_a.json`, `p2_test_b.json`)

| Cấu hình | llbo hit@4 | llbo hit@20 | temporal hit@20 | nexttrip hit@20 | nexttrip destHit@20 | coldstart hit@4 | syn_between themePrec | syn_noisy_paired themePrec | syn_open themePrec | syn_booked_browse xvAtX@4 | syn_session_multi nextDestHit@4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `B0` | 0.5260 | 0.8099 | 0.1682 | 0.0886 | 0.6752 | 0.6981 | 0.4403 | 0.3778 | 0.7806 | 0.2937 | 0.4916 |
| `B1p` | 0.5249 | 0.8088 | 0.1646 | 0.0854 | 0.6983 | 0.6975 | 0.4247 | 0.3917 | 0.7752 | 0.2895 | 0.5153 |
| `B2` | 0.5249 | 0.8088 | 0.1356 | 0.0535 | 0.7127 | 0.6972 | 0.7683 | 0.6928 | 0.7752 | 0.2895 | 0.5153 |
| `B0+orig:pen:0.15+sess` | 0.5532 | 0.8375 | 0.1844 | 0.0950 | 0.6728 | 0.7876 | 0.4403 | 0.3778 | 0.7806 | 0.9964 | 0.9123 |
| `B1p+orig:pen:0.15+sess` | 0.5525 | 0.8349 | 0.1808 | 0.0934 | 0.6975 | 0.7719 | 0.4247 | 0.3917 | 0.7752 | 0.8003 | 0.9220 |
| `B2+orig:pen:0.15+sess` | 0.5525 | 0.8349 | 0.1555 | 0.0599 | 0.7111 | 0.7716 | 0.7683 | 0.6928 | 0.7752 | 0.8003 | 0.9220 |

### 4.1 Họ chính (Holm, α = 0,05; `family.json` commit trước TEST)

| So sánh | Stratum / chỉ số | p | p Holm | Bác H0 |
|---|---|---:|---:|---|
| B1p → F_O | llbo hit@20 | 0,0 | 0,0 | ✅ |
| B1p → F_O | nexttrip hit@20 | 0,0008 | 0,0048 | ✅ |
| B2 → F | nexttrip hit@20 | 0,006 | 0,03 | ✅ |
| B0 → OPH-prod | nexttrip hit@20 | 0,0092 | 0,0368 | ✅ |
| B0 → OPH-prod | llbo không target-in-cart hit@4 | 0,1032 | 0,3096 | ❌ |
| B1p → F_O | llbo không target-in-cart hit@4 | 0,2044 | 0,4088 | ❌ |
| B2 → F | llbo không target-in-cart hit@4 | 0,2044 | 0,4088 | ❌ |

### 4.2 Chênh lệch ghép cặp chính (`p2_test_ci.txt`, 95 %)

| So sánh | llbo hit@4 | temporal hit@20 | nexttrip hit@20 | coldstart hit@4 | syn_open themePrec | syn_between themePrec |
|---|---|---|---|---|---|---|
| B1p → F_O | +0,0276 [+0,0190, +0,0362] | +0,0163 [+0,0054, +0,0289] | +0,0080 [+0,0032, +0,0136] | +0,0744 [+0,0603, +0,0887] | +0,0000 | +0,0000 |
| B2 → F | +0,0276 [+0,0190, +0,0362] | +0,0199 [+0,0090, +0,0325] | +0,0064 [+0,0016, +0,0112] | +0,0744 [+0,0603, +0,0887] | +0,0000 | +0,0000 |
| B0 → OPH-prod | +0,0272 [+0,0186, +0,0358] | +0,0163 [+0,0072, +0,0271] | +0,0064 [+0,0016, +0,0112] | +0,0895 [+0,0755, +0,1039] | +0,0000 | +0,0000 |
| B0 → F | +0,0265 [+0,0179, +0,0351] | −0,0127 [−0,0325, +0,0054] | −0,0287 [−0,0415, −0,0168] | +0,0736 [+0,0595, +0,0879] | −0,0053 [−0,0137, +0,0030] | +0,3280 [+0,2969, +0,3581] |

### 4.3 Gate

| Gate | F vs B0 (track F14c) | OPH-prod vs B0 (G7) |
|---|---|---|
| temporal h@20 giảm ≤ 0,04 (điểm) | −0,0127 ✅ | +0,0163 ✅ |
| LLBO h@4 (G1-LLBO(b): cận dưới ≥ −0,01) | +0,0265, cận dưới +0,0179 ✅ | +0,0272, cận dưới +0,0186 ✅ |
| theme ≥ +0,15 | +0,3280 ✅ | không yêu cầu (G7) |
| `open` (G1-open′: cận dưới ≥ −0,02) | −0,0053, cận dưới −0,0137 ✅ | +0,0000 ✅ |
| latency (trong tiến trình, chẩn đoán) | §5 ✅ | §5 ✅ |
| G2 nexttrip | −0,0287 [−0,0415, −0,0168] — vẫn là câu hỏi G2 của lane B (F cải thiện +0,0064 so với B2) | không áp |
| ít nhất một chỉ số đích cận dưới > 0 (G7) | — | nexttrip h@20 +0,0064 [+0,0016, +0,0112], Holm ✅ |

## 5. Latency xếp hạng trong tiến trình (`latency_llbo.json`, `latency_nexttrip.json`)

400 khách, k = 4, lấy lượt nhanh nhất trong 3; cache popularity 512 (không tính bước dựng bảng phổ biến).

| Cấu hình | llbo p50 / p95 ms | nexttrip p50 / p95 ms |
|---|---|---|
| `B0` | 1.45 / 2.79 | 3.35 / 3.67 |
| `B0+orig:pen:0.15+sess` | 1.46 / 2.82 | 3.39 / 3.75 |
| `B1p` | 1.72 / 2.83 | 3.34 / 3.68 |
| `B1p+orig:pen:0.15+sess` | 1.70 / 2.77 | 3.41 / 3.76 |
| `B2` | 1.71 / 2.83 | 2.96 / 3.64 |
| `B2+orig:pen:0.15+sess` | 1.76 / 2.87 | 2.98 / 3.76 |

Chênh p95 do chuỗi O ≤ +0,12 ms. Số cũ 29,62 / 38,63 ms (`eval-2026-10-08-recsys-g2-va-wp4.md`) dùng cache popularity 8 mốc nên
gồm cả việc dựng lại bảng phổ biến. Đây **không** phải latency đầu-cuối (G1 chấm bằng `http-latency` sau Pha B).

## 6. Caveat khi trích dẫn

1. **Phần lớn lợi ích nằm ở khách mà món đích đã có trong lịch sử của chính họ** (`p2_test_by_target_seen.json`). B0 → OPH-prod
   hit@20: llbo đích đã xem +73 / 1.446, đích mới +4 / 1.347; coldstart đích đã xem +624 / 3.594 (coldstart gần như toàn bộ là
   "xem rồi mua" của seed); nexttrip đích mới +7 / 1.229 (h@4 +7). Kết luận đúng: chuỗi O giúp gợi lại món / route khách đã quan
   tâm qua nhiều phiên xem (chuyến ảo) và loại route sai điểm xuất phát; lợi cho món **mới** nhỏ.
2. Lợi của O1 (điểm xuất phát) trên LLBO đến từ khách đã xem / thêm giỏ chính route đích trước khi mua (`ô` lấy từ chính route
   đó). Đây là thông tin production có lúc request, nhưng LLBO đánh giá cao hơn khách chưa xem chuyến bay nào. Trên TEST, phần
   không target-in-cart **không** có ý nghĩa sau Holm (+0,0068).
3. O3 (I-3) không đổi số nào trên split thật (bản sao hầu như không có khách đã đặt rồi xem lẻ sau); bằng chứng là kịch bản
   `booked_browse` (conformance, tự thiết kế). O4 có kịch bản `session_multi` cũng là conformance.
4. Lịch sử là dữ liệu tổng hợp (seed): điểm đến chuyến kế tiếp độc lập với sở thích, nên temporal / nexttrip không đo được lợi
   bám sở thích (lý do track N quyết trên DB G6).
5. B1′ chưa có gương loại combo. Khách TEST là tập con của nhóm đã dùng để chọn B2 ngày 08/10 → so với B2 không sạch hoàn toàn.
6. Split dựng qua `filter_events` + kiểm sha với file đóng băng, nên số **không** so trực tiếp được với bảng theme_study 08/10
   (theme_study bỏ `filter_events`).
7. Chưa đo: trần Z-pop, arm chẩn đoán D-* (shuffle origin, home_city, union pool, decay theo loại event giữa các chuyến).

## 7. Lệnh tái sinh

```bash
# Git Bash, từ worktree; container vota-prodcopy-pg (:55433) đang chạy
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55433/vota_prodcopy CDP_DATABASE_URL=$DATABASE_URL EVAL_DATABASE_URL=$DATABASE_URL
export WEAVIATE_URL=http://127.0.0.1:59999 PYTHONIOENCODING=utf-8 PYTHONUTF8=1
VEC=npy:D:/Study/VinAI20K/VSF/recsys-vec/2026-10-08/vec_prodcopy_e5s; M=src.evaluation.recsys_bench.theme_study
SC="--scenarios between,open,noisy_paired,booked_browse,session_multi,dormant --syn-target"
# TEST (một lần)
python -m $M.eval_oph --vec $VEC --as-of 2026-10-08T00:00:00+00:00 --configs "B0,B1p,B1p+orig:pen:0.15+sess" \
  --splits llbo,temporal,nexttrip,coldstart $SC --user-part test --syn-seeds 101,202,303 --out p2_test_a.json --per-user-out p2_test_a.jsonl
python -m $M.eval_oph --vec $VEC --as-of 2026-10-08T00:00:00+00:00 --configs "B2,B2+orig:pen:0.15+sess,B0+orig:pen:0.15+sess" \
  --splits llbo,temporal,nexttrip,coldstart $SC --user-part test --syn-seeds 101,202,303 --out p2_test_b.json --per-user-out p2_test_b.jsonl
python -m $M.paired_ci --per-user p2_test_a.jsonl p2_test_b.jsonl --compare "B1p>B1p+orig:pen:0.15+sess,B0>B1p+orig:pen:0.15+sess,B2>B2+orig:pen:0.15+sess,B0>B2+orig:pen:0.15+sess,B0>B0+orig:pen:0.15+sess,B0>B1p,B0>B2" \
  --boot 10000 --split-by tgtInCart --family family.json --by-seed --out p2_test_ci.json
# latency (chạy một mình)
python -m $M.rank_latency --vec $VEC --as-of 2026-10-08T00:00:00+00:00 --configs "B0,B0+orig:pen:0.15+sess,B1p,B1p+orig:pen:0.15+sess,B2,B2+orig:pen:0.15+sess" \
  --split nexttrip --k 4 --n-users 400 --repeat 3 --popularity-cache 512 --out latency_nexttrip.json
```

Lệnh TUNE (Phase 0 / 1) nằm trong khoá `args` của từng file `p0_*.json`, `p1_*.json`.
