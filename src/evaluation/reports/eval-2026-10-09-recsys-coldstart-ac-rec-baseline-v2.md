# Coldstart, AC-REC-01/02 và baseline gate v2 trên bản sao production (lane A2, A3)

- Ngày chạy: 2026-10-08 (tối) → 2026-10-09 (giờ VN)
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04; AC-REC-01, AC-REC-02 (`docs/prd/requirements.md` §3); gate RecSys
  (`docs/spec/bench/recsys-offline-eval.md` §3.1)
- Plan: `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` lane A2, A3
- Kết quả gốc: `src/evaluation/recsys_bench/theme_study/results/2026-10-08-lane-a/` (`coldstart_*.json`, `ci_coldstart.json`,
  `ac/*.txt`); split đóng băng và baseline ở `src/evaluation/recsys_bench/frozen/*-prodcopy-asof20261008.json`
- Môi trường: như `eval-2026-10-08-recsys-latency-dau-cuoi-truoc.md` §2 (`vota_prodcopy`, vector `.npy` gói bàn giao,
  engine = production `6f77e80`); thêm `PYTHONUTF8=1` cho lệnh `recsys_bench user` trên Windows

## 1. Coldstart (ô WP4 còn trống) — kiểm không-hồi-quy

`eval_profile.py` thêm split `coldstart` (`SP.cold_start_split`: target = lần mua hợp lệ đầu tiên, as_of = lúc mua, train =
event trước đó) và chỉ số `destHit@20`. Toàn bộ **5.243** khách; `share_open = 1,000` cho cả P0 và P2 — mọi khách coldstart đều
có chuyến chỉ-xem đang mở (N = 14) nên nhánh không-chuyến-mở (F14c / destCap2) **không chạy**; đây là kiểm không-hồi-quy
của P2, không phải lợi ích.

| Cấu hình | hit@20 | nDCG@10 | hit@4 | destHit@20 |
|---|---:|---:|---:|---:|
| P0+F0 (production) | 0.8114 | 0.6143 | 0.6975 | 0.9943 |
| P2+F0 | 0.8102 | 0.6115 | 0.6964 | 0.9943 |
| P2+F14c | 0.8102 | 0.6114 | 0.6962 | 0.9943 |
| P2+F14c+destCap2 | 0.8100 | 0.6113 | 0.6962 | 0.9943 |

CI ghép cặp so với production (bootstrap 2.000, n = 5.243):

| Cấu hình | hit@20 | hit@4 | nDCG@10 |
|---|---|---|---|
| P2+F0 | −0,0011 [−0,0027, +0,0002] | −0,0011 [−0,0023, +0,0000] | −0,0028 [−0,0040, −0,0016] |
| P2+F14c | −0,0011 [−0,0027, +0,0002] | −0,0013 [−0,0027, −0,0002] | −0,0029 [−0,0041, −0,0018] |
| P2+F14c+destCap2 | −0,0013 [−0,0029, +0,0000] | −0,0013 [−0,0027, −0,0002] | −0,0030 [−0,0042, −0,0018] |

Đọc: hit@20 CI chứa 0; hit@4 −0,0013 là **11 khách lật / 5.243** (CI vừa chạm mức có ý nghĩa), toàn bộ do P2 (F14c và destCap2
thêm đúng 1 khách lật so với P2+F0). nDCG@10 −0,003 (0,5 % tương đối) cũng do P2 — cùng cỡ với LLBO nDCG@10 −0,0031 đã biết.
`destHit@20` không đổi (khoá điểm đến). Kết luận: coldstart **không hồi quy** ngoài chi phí nhỏ, đã biết, của P2.

## 2. AC-REC-01 — P1 (gia đình) đăng nhập, trang chủ có gợi ý kèm `because`

`recsys_bench user --id … --k 4 --vectors npy:$VEC --as-of …` (`ac/*.txt`):

| Khách / mốc | strategy | destination | Danh sách 4 món | because | Kiểm |
|---|---|---|---|---|---|
| **VP0000001 @ 2026-09-21** (chuyến NT đang mở) | `cross_vertical` | Nha Trang | flight TP.HCM–NT · golf Vinpearl NT · flight HN–NT · combo Aquafield | 1 nguồn / món | **day1Check 4/4 ✓** (cross_vertical, `excludedVerticals == ['hotel']`, không hotel, nextVertical ∈ {flight, attraction}) |
| VP0000001 @ 2026-10-08 (chuyến NT **đã kết thúc** 05/10) | `long_term` | — | flight TP.HCM–PQ · hotel Vinpearl Resort NT · attraction RD Phan Thiết · flight HN–NT | 2 nguồn / món | because đủ; đây là nhánh F14c/destCap2 sẽ đổi (PR-B) — ghi để so SAU |
| VP0000003 (dormant) | `dormant` | — | flight TP.HCM–PQ · hotel Vinpearl NT Bay · JW Marriott PQ · golf PQ | 2 nguồn, daysAgo 204 | **p3Check 4/4 ✓** |
| VP0000002 (2 lượt xem) | `long_term` | — | flight TP.HCM–PQ · hotel Vinpearl NT Bay · Arcadia homestay PQ · flight TP.HCM–ĐN | 2 nguồn / món | because đủ |
| VP0000004 (0 event) | `popular` | — | 2 flight NT · hotel Vinpearl NT Bay · golf NT | rỗng | đúng ràng buộc `popular ⟹ because = []` |

`contractErrors = []` ở mọi lượt. Phần "tiêu đề và nội dung phù hợp cho gia đình" của AC không có nhãn máy — duyệt tay: danh sách
của P1 là vé bay / golf / combo tại Nha Trang (đúng chuyến), không có tín hiệu "gia đình" riêng; ghi là **cần người xem**.

## 3. AC-REC-02 — đặt phòng tại Đà Nẵng

Chưa persona nào có đơn Đà Nẵng nên mã hoá bằng **lịch sử tổng hợp** (không ghi DB): xem → thêm giỏ → mua hạng phòng của
`Caro Premium Danang Hotel`, `eventGroupId = ACREC02-T1`, `usingDate = as_of + 10`. Gọi hai kiểu: trang xác nhận (khoá
`destination = Đà Nẵng`) và trang chủ (không khoá). Kết quả giống nhau:

| # | taxonomy | món | because |
|---|---|---|---|
| 1 | flight | Vé máy bay TP. Hồ Chí Minh - Đà Nẵng | 1 |
| 2 | attraction | Charming Danang Show | 1 |
| 3 | combo | Vé máy bay khứ hồi Hà Nội - Đà Nẵng + Phòng Superior … | 1 |
| 4 | attraction | **Sun World Bà Nà Hills** | 1 |

`strategy = cross_vertical`, `destination = Đà Nẵng`, `nextVertical = attraction`, `excludedVerticals = ['hotel']`, khách sạn
vừa mua không xuất hiện. **Đạt** phần "vé máy bay đến Đà Nẵng + tour Bà Nà". Hai điều phải ghi:

- **"Tour Hội An" không thể đạt theo thiết kế**: Hội An là điểm đến riêng (123 khách sạn, 27 tham quan), luật khoá điểm đến của
  FR-REC-02 loại nó; ô khám phá không giúp vì Đà Nẵng đủ 4 ô (12 chuyến bay, 7 tham quan). Đề xuất sửa câu AC ở
  `docs/prd/update/2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md`.
- Món #3 là combo **có phòng khách sạn** dù khách vừa mua khách sạn — đúng luật "combo kéo theo hotel" ở spec §4.5 /
  `PRODUCT_SCHEMA.md` §5 (đã ghi, chưa cài); đề xuất [C] để nó ngoài phạm vi, nhưng đây là bằng chứng nó có thật.

Mã hoá cố định: `src/evaluation/recsys_bench/tests/test_ac_rec02_danang.py` (3 test, skip khi thiếu `DATABASE_URL` /
`RECSYS_VEC`; chạy trên prodcopy: **3 passed**) và `src/backend/tests/unit/application/test_engines.py::
test_ac_rec_02_booking_prioritises_flights_and_activities_at_the_destination` (catalog giả, chạy trong CI: **12 passed**).

## 4. Gate: split prodcopy đóng băng + baseline_v2

`baseline_v1` (`frozen/baseline_v1-*-asof20260924.json`) là Cohere-era, `configHash b0aee886` — HARD_META nên
`make recsys-regress` **NotComparable** với engine hiện tại dù chưa đổi gì. Ghi lại trên bản sao production, **trước** mọi thay
đổi engine (spec §3.1: model + bộ split mới):

- Split: `split --kind {llbo,temporal,nexttrip,coldstart} --as-of 2026-10-08 --freeze --freeze-path
  frozen/split-<kind>-prodcopy-asof20261008.json` (dsnLabel `127.0.0.1:55433/vota_prodcopy`; **không bao giờ** sinh lại event
  ở DB này). sha256: llbo `0bff46bb…`, temporal `6b430216…`, nexttrip `f5bd9dc9…`, coldstart `7c27c631…`.
- Run gate (đúng bộ arm của Makefile `recsys-gate-run`, `--vectors npy:$VEC`, `--mode funnel --funnel-pool engine`):
  `20261009-gate-<kind>-prodcopy-v2` → `analyze` → `baseline --note "baseline_v2: engine production 6f77e80 …"` →
  `frozen/baseline_v2-<kind>-prodcopy-asof20261008.json` → `regress` cùng run: **exit 0, mọi arm PASS, chênh +0,00**.
- Makefile mặc định (`RECSYS_ASOF=20260924`, DB seed) không chạy được trên máy này (GnuWin32 make 3.81, không có DB seed);
  chạy bằng lệnh python trực tiếp như trên.

Arm `engine` (production) trên split prodcopy:

| Split | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Cross-cat | Gini | Div@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| llbo | 4.023 | 0.6214 | 0.4661 | 0.7189 | 0.8071 | 0.4977 | 0.749 | 0.892 | 0.839 | 0.573 |
| temporal | 773 | 0.1177 | 0.0906 | 0.1320 | 0.1604 | 0.0950 | 0.628 | 0.441 | 0.841 | 0.605 |
| nexttrip | 1.835 | 0.0283 | 0.0183 | 0.0469 | 0.0785 | 0.0242 | 0.707 | 0.343 | 0.884 | 0.659 |
| coldstart | 5.233 | 0.7369 | 0.6002 | 0.7703 | 0.8095 | 0.6111 | 0.878 | 1.000 | 0.621 | 0.583 |

(`content_profile+mmr == engine` 4.023/4.023; `star_blend_a1 == content_profile` — gương harness vẫn khớp engine.) Khách llbo
4.023 ở đây ≠ 4.072 ở `theme_study` vì CLI `split` dùng `--min-purchases 2`; số dùng để **so trước / sau** là baseline này.

Sau PR-A (ENGINE_RULES_VERSION đổi) `regress` sẽ **FAIL theo thiết kế** (configHash) → ghi `baseline_v3` sau G5a.

## 5. Lệnh tái sinh

```bash
export PYTHONUTF8=1; VEC=npy:/đường/dẫn/vec_prodcopy_e5s; AS=2026-10-08T00:00:00+00:00
# §1 coldstart
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS --profiles P0_prod,P2_confidence \
  --scorers F0_prod,F14c_betweenQuantilePop35 --f14-cal-profile P2_confidence --splits coldstart --max-users 0 --scenarios "" \
  --per-user-out cs_a.jsonl --out cs_a.json                                                        # 1453 s
python -m src.evaluation.recsys_bench.theme_study.eval_profile … --profiles P2_confidence --scorers F14c_betweenQuantilePop35 \
  --dest-cap 2 --per-user-out cs_dc2.jsonl --out cs_dc2.json                                      # 385 s
python -m src.evaluation.recsys_bench.theme_study.paired_ci --per-user cs_a.jsonl cs_dc2.jsonl --baseline P0_prod+F0_prod --out ci_coldstart.json
# §2 AC-REC-01
python -m src.evaluation.recsys_bench user --id VP0000001 --k 4 --vectors $VEC --as-of 2026-09-21   # day1Check
python -m src.evaluation.recsys_bench user --id VP0000003 --k 4 --vectors $VEC --as-of 2026-10-08   # p3Check
# §3 AC-REC-02
RECSYS_VEC=$VEC pytest src/evaluation/recsys_bench/tests/test_ac_rec02_danang.py -q
# §4 gate
python -m src.evaluation.recsys_bench split --kind llbo --as-of 2026-10-08 --freeze --freeze-path src/evaluation/recsys_bench/frozen/split-llbo-prodcopy-asof20261008.json
python -m src.evaluation.recsys_bench run --arm engine --arm engine_nommr --arm most_popular_in_destination \
  --algos src/evaluation/recsys_bench/algos_v1.yaml --only content_profile --only star_blend_a1 --funnel-pool engine --mode funnel \
  --split llbo --vectors $VEC --split-file src/evaluation/recsys_bench/frozen/split-llbo-prodcopy-asof20261008.json --run-id <id>
python -m src.evaluation.recsys_bench analyze --run-id <id>
python -m src.evaluation.recsys_bench baseline --run-id <id> --note "…" --out src/evaluation/recsys_bench/frozen/baseline_v2-llbo-prodcopy-asof20261008.json
python -m src.evaluation.recsys_bench regress --run-id <id> --baseline src/evaluation/recsys_bench/frozen/baseline_v2-llbo-prodcopy-asof20261008.json   # exit 0
```
