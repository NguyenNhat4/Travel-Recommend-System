# Kế hoạch: công thức điểm mới cho recommendation (OPH + sửa chuyến đã đặt + lớp phiên) và bench so với công thức cũ

- Ngày: 2026-10-09
- Nhánh: `feat/recSys_update-2` (worktree `.worktrees/recsys-update-2`). Ngày 09/10 đã merge `feat/recSys_update` (gồm lane A `a4f57e1`) ở commit `eff8abc`; cây file khớp `feat/recSys_update`.
- Người soạn: tqanh123
- Phục vụ (đã kiểm trong `docs/prd/requirements.md`):
  - FR-REC-01, FR-REC-02, FR-REC-03, FR-REC-04 (§1.3, dòng 41-48);
  - NFR-PERF-01 (§2.1, dòng 122-124), NFR-PERF-03 (dòng 128);
  - AC-REC-01, AC-REC-02 (§3, dòng 156-157);
  - đánh giá theo `docs/prd/test-plan.md` §2.5.
- Neo vào: `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` (trên `feat/recSys_update`). Gọi tắt là "plan giai đoạn".
  - Plan này là **lane C** (công thức OPH), chạy sau lane A. Track chính chồng lên cấu hình PR-A; track phụ chồng lên PR-B.
  - Plan giai đoạn đã chốt PR đích là `release-mvp-v2` (§1, dòng WP0.6).
- Nguồn: `docs/spec/bench/recommendation_persona_profile_latency.md` (bản nháp brainstorm, chưa track, 591 dòng).
- Căn cứ:
  - `docs/spec/bench/recsys-bam-so-thich-tong-hop.md`;
  - `recsys-bam-so-thich-quyet-dinh.md` (bản trên `feat/recSys_update`, §7.5);
  - report `src/evaluation/reports/`: `eval-2026-10-08-recsys-so-thich-ci.md`, `eval-2026-10-08-recsys-g2-va-wp4.md`, `eval-2026-10-07-recsys-grid-llbo-coldstart.md`, `eval-2026-10-06-recsys-search-tong-hop.md`, `eval-2026-10-05-recsys-web-latency.md`;
  - hai report chưa track ở bản checkout chính: `eval-2026-10-08-recsys-latency-dau-cuoi-truoc.md` và `eval-2026-10-09-recsys-coldstart-ac-rec-baseline-v2.md`.
- Trạng thái: **đã duyệt 09/10 (tqanh123)**, quyết định ở §0.
  - Pha A (bench) làm ngay trong `src/evaluation/`, không sửa engine.
  - Đưa lên production bị chặn bởi G5a/PR-A (track chính), lane B + G2 chốt lại + G5b (track phụ), và các gate ở §7.6.
---

## Tóm tắt

- Brainstorm `recommendation_persona_profile_latency.md` đề xuất ba lớp profile, trọng số theo persona và nhiều hạng ngữ cảnh. Đối chiếu với code, kết quả đo trước và dữ liệu prodcopy thì phần lớn các hạng đó **không có tín hiệu** trên dữ liệu hiện tại: tier ngẫu nhiên, không có timestamp cho freshness, `last_destination` lộ đáp án, decay trong chuyến đã đo Δ = 0 (§2.5).
- Công thức chọn là **OPH-L** (§3.3). Nhánh có chuyến mở giữ công thức production và thêm:
  - phạt hoặc mask chuyến bay sai điểm xuất phát (`mis`), với origin suy từ event;
  - ưu tiên chuyến đã đặt khi chọn `active_trip` (sửa I-3), gộp các lượt xem lẻ thành một chuyến ảo (`u_session`);
  - món trong giỏ được đưa vào pool và cộng `W_CART`.
- Nhánh không có chuyến mở: F14c (cos đã hiệu chỉnh + pop 0,35), thêm `pop_h` (pop có decay + shrinkage theo điểm đến × taxonomy).
- Trọng số theo persona chỉ đặt ở nơi có khách chịu tác động: dormant (`H_L` dài hơn, `w_pop` cao hơn). Segment suy từ event, dùng nhãn DDL `P1_frequent`…`P4_no_history`.
- Bench: thang ablation B0 (production) → O1…O5 (track chính) và N1…N4 (track phụ). Kiểm parity trước, đo trần oracle để dừng sớm, tune trên 30 % khách (TUNE), test **một lần** trên 70 % còn lại (TEST) với seed mới, CI bootstrap ghép cặp + Holm.
- Plan này chỉ làm bench trong `src/evaluation/`, không sửa engine. Đưa lên production cần đề xuất PRD ([D] mới cho track O, gộp vào [B] cho track N) và qua các gate ở §7.6.
- Ước lượng: bench khoảng 4–5 ngày công + 5–7 giờ máy; Pha B 2–3 ngày.

---

## 0. Quyết định của người dùng (09/10/2026, tqanh123)

| Câu hỏi (§9.2) | Quyết định |
|---|---|
| Duyệt plan | Duyệt |
| Q11 merge | Cho phép. Đã merge `feat/recSys_update` (`eff8abc`). Lane A chạy song song trên cùng máy: chỉ **so kết quả**, không phụ thuộc code chưa commit của lane A |
| Q5 [C7] `pop_h` | **Đưa vào phạm vi** (track N, bậc N1) |
| Q2 B10 | Cho tune `W_ORIGIN` / `W_CART`. Nếu stratum temporal < 30 hit mốc thì tune trên LLBO đã loại khách target-in-cart |
| Q1 G1-LLBO(b), Q3 G1-open′, Q9 LIMIT 500, Q10 brainstorm doc | Đồng ý các thay đổi plan đề nghị |
| Q6 I-3 | Chấp nhận sửa. Tách **một đề xuất riêng [D]** và chốt luôn: `docs/prd/update/2026-10-09-recsys-uu-tien-chuyen-da-dat.md` |
| Q4 G7 | **Có dùng bản dự phòng OPH-prod** (B0 + các bậc O đã giữ + N1, không F14c). Tiêu chí G7 ở §7.6 |
| Q7 ngưỡng dormant | **365 ngày** |
| Q8 persona | Persona = **4 trạng thái cold-start** (`P1_frequent`, `P2_first_time`, `P3_dormant`, `P4_no_history`). PRD đổi persona phong cách du lịch (`P1_family`…`P4_deal`) thành một **đặc trưng của khách**: phong cách du lịch như thích biển, núi, thành phố… Đề xuất [E]: `docs/prd/update/2026-10-09-persona-trang-thai-cold-start-va-phong-cach-du-lich.md` |

Hệ quả cho bench:

- Segment `P3_dormant` dùng ngưỡng **365 ngày** tính từ chuyến trẻ nhất (§3.4). `diagnostics.dormant` của contract vẫn là 90 ngày (không đổi nghĩa field v1).
- Seed sinh nhóm `churned` có lần mua cuối 366–730 ngày (`seed/config.py:54`), nên P3 có mặt chủ yếu ở LLBO; temporal/nexttrip gần như không có. Phase 0 đếm số khách P3 theo split. Nhánh 180 ngày cũ giữ làm arm đối chiếu `N0-180`.
- Track OPH-prod (G7) chạy song song với track F14c ở Phase 2.

---

## 1. Bối cảnh

### 1.1 Công thức production hiện tại (đọc từ code)

**Hằng số** (`src/backend/app/domain/recommendation/profile.py`)

| Hằng | Giá trị | Dòng |
|---|---|---|
| `W_TYPE` | purchase 1,0 · add_to_cart 0,5 · product_view 0,2 · search 0,1 | 11 |
| `H_SHORT_DAYS`, `H_LONG_DAYS` | 30, 365 | 12 |
| `ACTIVE_TRIP_MAX_AGE_DAYS` | 14 | 16 |
| `DORMANT_AFTER_DAYS` | 180 | 17 |
| `MAX_REPEAT_PER_TRIP` | 3 | 18 |
| `W_SHORT, W_POP, W_LONG` | **0,7 / 0,15 / 0,15** (chốt 07/10) | 20 |
| `MMR_LAMBDA`, `MAX_PER_VERTICAL` | 0,7; 2 / taxonomy | 21 |
| `ENGINE_RULES_VERSION` | `"2026-10-02-trip-ended"` | 25 |

**Cách tính**

- Vector chuyến: `v_t = normalize(Σ_{e∈capped(t)} W_TYPE[e]·2^(−days_ago_e/30)·E[unit_e])` (`profile.py:116-121`). Cap lặp giữ **3 event cũ nhất** cho mỗi cặp (trip, unit) (`profile.py:107-114`).
- `u_long = normalize(Σ_t 2^(−age_t/365)·v_t)` (`profile.py:136-137`).
- Chuyến mở (`trip_is_open`, `profile.py:74-81`) theo luật **if/else**:
  - chuyến có `usingDate` thì mở khi `max(usingDate) ≥ hôm nay (giờ VN)`;
  - chuyến không có `usingDate` thì mở khi `age ≤ 14`.
  - Event `add_to_cart` cũng có `usingDate` (`seed_histories.py:257,287`). Vì vậy một chuyến `_solo_` từ giỏ hàng mở hay đóng theo ngày sử dụng, **không theo tuổi**.
- `active_trip` = chuyến mở **trẻ nhất** (`profile.py:138-139`).
- Điểm (`profile.py:145-149`): `score = 0,7·E·u_short + 0,15·pop + 0,15·E·u_long`, với `u_short = active_trip.vec` hoặc `u_long`. Khi không có chuyến mở, công thức thực chất là **0,85·cos(u_long) + 0,15·pop**.
- `pop` (`popularity.py:65-70`) = số lượt mua 90 ngày chia max.
  - Gọi ở **mọi nhánh**: pool popular_k và vector điểm (`use_cases.py:150-159`), với `dest = trip.destination` khi có chuyến mở.
  - Gọi thêm ở cold start (`use_cases.py:209`).
  - Gọi thêm ở `product_popularity` cho listing và suggest (`main.py:238`, dùng ở `main.py:135,270`).

**Ứng viên và lọc** (`use_cases.py:125-163`)

- Mask: `available`, `is_recommendable`. Khi có chuyến mở thì khoá điểm đến và bỏ taxonomy đã mua. Luôn bỏ `bought_units`.
- Pool: ANN top-200 quanh `u_short` (thêm `u_long` khi có chuyến mở) ∪ 50 món phổ biến trong mask. Cắt còn 200, chạy MMR (`profile.py:152-173`) rồi lấy k.
- `cand` là biến cục bộ trong `RecommendForUser.__call__` (`use_cases.py:142-162`). Các điểm monkeypatch hiện có (build_profile, score_candidates, mmr_select, `_LocalSpace`, Popularity) **không thêm được ứng viên** vào đây.

**`because[]`**: `explain` (`profile.py:176-193`) chỉ phân rã phần tương đồng theo event. Chỉ giữ đóng góp dương rồi chuẩn hoá lại (`profile.py:188-192`). Không giải thích `pop`, cũng không giải thích hạng 0,15·`u_long`.

**Đã chốt nhưng chưa vào engine** (plan giai đoạn §3, PR-A):

- P2 kèm `CAP_EXEMPT_EVENTS` và `Trip.confidence`.
- Loại combo qua `purchase_closure`.
- Ô khám phá B `_explore_fill`: một `near_vector(u_long)` khi `len(chosen) < k`.
- Kiểm trong worktree: `grep CAP_EXEMPT|_explore_fill src/backend/app` không ra kết quả nào.

### 1.2 Brainstorm ghi sai những gì

| Brainstorm ghi | Code thực tế |
|---|---|
| Trọng số `0.6/0.25/0.15` (dòng 19) | 0,7/0,15/0,15 (`profile.py:19-20`) |
| Engine dùng `cdp.profiles` (`home_city`, `vinclub_tier`, `lifecycle_stage`, `last_destination`) (dòng 14) | Đường request **không đọc** profile, chỉ gọi `events_for_user` (`use_cases.py:99`). Bench chặn rò bằng `LeakageError` (`recsys_bench/engine.py:89-91`) |
| `ends_on >= today OR age <= 14 days` (dòng 227-229) | if/else (`profile.py:79-81`) |
| Search có trọng số 0,1 | Search có `product_id` NULL nên bị bỏ (`use_cases.py:107-114`) |
| Persona là nhãn | **Đúng.** `score_candidates` không đọc `Profile.strategy`. Nhánh duy nhất là có hay không có `active_trip` |
| Điểm nghẽn latency là đọc history và dựng Trip/Profile (dòng 337) | Không khớp số đo (xem dưới) |
| Không ghi mã FR/NFR | Plan này bổ sung |

Số đo latency:

- Ranking trong tiến trình: p95 **38,63 ms** (`eval-2026-10-08-recsys-g2-va-wp4.md:199`).
  - Số này có thể đã **gồm cả bước dựng lại popularity**: cache popularity của `OfflineEngine` chỉ giữ 8 mốc, đẩy ra theo FIFO (`recsys_bench/engine.py:64,77-82`); `popularity_at` chạy bên trong `recommend` (`:93`); split có `as_of` riêng từng khách (`splits.py:196,255`).
- Đầu-cuối local, lane A1, trên `vota_prodcopy` + Weaviate local `ProductE5SmallProdcopy`, parity 60/60:
  - server p50/p95 **66,0/87,0 ms** (strata) và **67,0/86,0 ms** (users60);
  - nguồn: `eval-2026-10-08-recsys-latency-dau-cuoi-truoc.md` §4, bản checkout chính.
  - Không có mẫu `cross_vertical`: bản sao 08/10 chỉ có 1 khách có purchase với `usingDate` ≥ 08/10.
- Số cũ 72/86 ms là trên DB bench thời Cohere, snapshot 09-23 (`eval-2026-10-05-recsys-web-latency.md:15,22-25`). Số này đã bị thay.
- Cloud: **820/1.057 ms**, quy cho Weaviate Cloud khác vùng (`eval-2026-10-05-recsys-web-latency.md:13-15,30-35`).

### 1.3 Nghiên cứu trước đã chứng minh gì

**Mốc production P0+F0**, toàn bộ khách theme_study prodcopy (`eval-2026-10-08-recsys-so-thich-ci.md:32`):

| Đo | Giá trị |
|---|---|
| LLBO (4.072 khách), h@20 / nDCG@10 / h@4 | 0,8084 / 0,4988 / 0,5329 |
| temporal (775), h@20 / nDCG@10 / h@4 | 0,1587 / 0,0954 / 0,1135 |
| nexttrip (1.835), h@20 / nDCG@10 / h@4 | 0,0785 / 0,0239 / 0,0256 |
| theme between · noisy_paired · open | 0,439 · 0,376 · 0,800 |
| theme between theo chủ đề (biển / núi / phố) | 0,924 / **0,172** / 0,222 (`results/2026-10-08-wp0-wp3/wp2_full_p0p2_f0f7.json`) |
| nextDestHit@20 · tgtHit@20 | 0,4667 · 0,0000 (`g2-va-wp4.md:131`) |

**Split đóng băng** (`asof20261008`, sha256 llbo `0bff46bb…`, temporal `6b430216…`, nexttrip `f5bd9dc9…`, coldstart `7c27c631…`) và `baseline_v2`: LLBO 4.023 khách, temporal 773 (`eval-2026-10-09-…-baseline-v2.md:85-99`). Số khách khác theme_study vì theme_study bỏ qua `filter_events` (`eval_profile.py:131-136`).

**Ứng viên G3 = P2+F14c+destCap2** (`g2-va-wp4.md` §3.1):

| Đo | Giá trị |
|---|---|
| LLBO h@4 | 0,5324 |
| temporal h@20 | 0,1277 |
| nexttrip h@20 / h@4 | 0,0469 / 0,0202 |
| theme between / noisy_paired | 0,756 / 0,698 |
| nextDestHit@20 · tgtHit@20 | 0,4181 · 0,0111 |
| coldstart (5.243 khách) h@20 / h@4 so với production | −0,0013 [−0,0029; +0,0000] / −0,0030 [−0,0042; −0,0018] (`eval-2026-10-09-…:26-32`) |

- So với production: temporal −0,0310 [−0,0465; −0,0168], nexttrip −0,0316 [−0,0409; −0,0218].
- **Lộ trình đã chốt 08/10** (`feat/recSys_update:docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7.5):
  - ship P2 + ô B + loại combo (PR-A);
  - sau đó làm G6 (đổi bộ sinh event cho có sở thích, đo lại);
  - rồi chốt lại G2 cho F14c + destCap2 (PR-B).
  - G6 **không** cần đề xuất PRD riêng (cùng file, dòng 222).

**Vì sao pop lấn át sở thích**

- Cos e5-small bị nén, đo trên 150 request của khách không có chuyến mở: dải 0,823–0,944, p90 − trung vị **0,012**.
- `pop` có **60 % bằng 0**, p90 **0,282** (`recsys-bam-so-thich-tong-hop.md:104-105`).
- Vì vậy mọi trọng số danh nghĩa đều vô nghĩa nếu cos chưa được hiệu chỉnh. F14 dùng `clip((cos − 0,8529)/(0,9387 − 0,8529), 0, 1)` (`step2_scorers.py:47-79`).

**Những núm đã thử mà không tạo khác biệt** (phạm vi có giới hạn)

- `H_SHORT` 60, `DORMANT` 90, `W_TYPE` 5/3/1 cho Δ = +0,0000 (`recsys-offline-eval.md:538,541,542`).
  - Chỉ đo trên **102 khách temporal**. Chính nguồn ghi đây "chỉ là hướng dò, không phải quyết định" (`:544`).
  - Đây đều là núm decay **trong chuyến** toàn cục. Decay trong chuyến gần như không có tác dụng theo cấu trúc, vì event của một chuyến chỉ cách nhau vài phút (`profile.py:120`).
- `nodecay` (`eval-2026-10-06-recsys-search-tong-hop.md:966-1003`).
- Decay **theo loại event giữa các chuyến** (trong `u_long`, brainstorm §3.3) **chưa từng thử**. Biến thể gần nhất là P2 (trọng số chuyến theo loại event), và P2 có tác dụng: +0,175 theme noisy_paired (`ci.md:82`).
- MMR λ 0,85 / 1,0 không hơn 0,7.
- P3 `session` có hại: noisy 0,447 → 0,287 (`tong-hop.md:232-234`).
- Ẩn món đã xem làm LLBO h@4 giảm 0,5324 → **0,3986**.

**Hạn chế của dữ liệu seed**

- Điểm đến chuyến kế tiếp không phụ thuộc sở thích của khách (`seed_histories.py:160-161,344-346`).
- Lần bốc lại có phụ thuộc `home` qua `w.has(dest, "flight", home)` (`seed_histories.py:194-198`), và còn nhân `VINPEARL_BOOST = 2,0` (`config.py:77`).
- Hệ quả: popularity là bộ đoán tốt trên temporal và nexttrip. G6, đang làm ở lane B (DB `vota_g6pref_v1`), là cách đã chốt để đo thật.

### 1.4 Brainstorm đề xuất gì

- Ba lớp profile:
  - `u_session`: 0–14 ngày;
  - `u_trip`: đến hết `using_date`, hoặc 120 ngày;
  - `u_long`: 2–5 năm.
- Decay riêng cho từng loại event.
- `PERSONA_CONFIG` cho frequent / dormant / first_time / no_history.
- Các hạng `destination_match`, `tier_affinity`, `freshness`, `repeat_penalty`.
- Tách `active_trip` khỏi `current_intent`.
- Materialize profile, cache Redis, stale fallback (§10–15).

---

## 2. Brainstorm: các ứng viên đã xét

| Thiết kế | Đo được | Lợi kỳ vọng | Chi phí/tuân thủ | Tổng |
|---|---:|---:|---:|---:|
| OPH | 8 | 7,5 | 7 | **22,5** |
| L3P | 6 | 4,5 | 8 | 18,5 |
| LW-Seg | 7 | 5,5 | 5 | 17,5 |
| F20 | 4 | 2,5 | 4 | 10,5 |

Plan lấy OPH làm khung, ghép phần sửa đúng nghiệp vụ của L3P và đặc trưng cart của LW-Seg, cùng công cụ đo của F20.

### 2.1 F20 — làm đúng nguyên văn brainstorm §6 (loại)

Lý do loại:

- Các hạng hoặc đã bị bác, hoặc không có tín hiệu:
  - half-life **trong chuyến** toàn cục và `W_TYPE` 5/3/1 cho Δ +0,0000 trên 102 khách (§1.3);
  - dormant pop 0,70 tương đương F10 (pop 0,60), có theme 0,391 **trên tập con 800 khách**, trong khi production toàn bộ là 0,439. Hai số này không cùng mẫu;
  - các hàng trọng số first-time và frequent rơi vào các điểm grid đã kém hơn (`eval-2026-10-06-…:968-981`);
  - hiệu chỉnh cos trên nhánh có chuyến mở làm LLBO h@4 giảm 0,5737 → 0,4188 (F1, **tập con 800 khách**);
  - `vinclub_tier` ngẫu nhiên (`seed_histories.py:493`);
  - không có timestamp nào cho freshness.
- Đổi `halfLifeDays` (30 ngày, decay theo event, spec `hop-dong-tich-hop-search-recommendation.md:532,540`) làm hỏng AC 20-21 (`:856-859`).

**Giữ lại:**

- bộ đếm thời gian theo stage;
- chỉ số because coverage;
- arm đối chứng rỗng (D-shuffleO, §4.4);
- **một arm decay theo loại event giữa các chuyến** (D-typeLong, §4.4), vì chưa từng được đo.

### 2.2 LW-Seg — trọng số học theo segment (chỉ ghép đặc trưng)

Lý do không lấy bộ học:

- W_POP sweep đã vẽ xong biên Pareto (`ci.md:92-104`).
- `φ_sess` gần như không tách khỏi `active_trip`: mọi view trong 14 ngày, và mọi cart có `usingDate` chưa qua, đều tự mở một chuyến `_solo_` (`profile.py:74-81`; `use_cases.py:117`).
- Không có impression logging thì "học" chỉ là khớp bộ sinh.

**Giữ lại:**

- Đặc trưng **cart**. Khi món đích đã nằm trong giỏ, engine đạt hit@20 0,864, còn ials đạt 0,971. Đo trên 1.731/4.021 khách của **append-v1**, chưa phải prodcopy (`eval-2026-10-06-…:151,344`).
- Đưa món của chính khách vào pool.
- Arm chẩn đoán bẫy pop.
- Cổng parity.

### 2.3 L3P — ba lớp profile và trọng số persona (ghép phần sửa đúng nghiệp vụ)

**Không lấy** phần trọng số persona. Trên split thật hầu như không có khách nào chịu tác động: chỉ 107/4.023 khách LLBO xem từ 2 điểm đến trở lên trong 14 ngày, và phân kỳ phiên–chuyến chỉ có ở khoảng 2 khách.

**Giữ lại:**

- **Ưu tiên chuyến đã đặt (sửa I-3)**: một lượt xem lẻ mới hơn đang chiếm `active_trip` của chuyến đã mua và còn mở.
  - Test ghim hành vi này: `tests/test_engine_no_leak.py:43-53`.
  - Giai thoại "8 phòng Nha Trang / Vũng Tàu": `tong-hop.md:38`.
- Gộp phiên thành chuyến ảo.
- Dormant `H_L × 3`. **Đây là tuning thăm dò, không phải làm đúng spec** (xem §3.4).
- Một bộ gán nhãn segment cố định.
- Luồng rng riêng cho mỗi kịch bản giả lập.

### 2.4 OPH — chi phí theo điểm xuất phát chuyến bay và pop làm mượt (khung chính)

**Đòn bẩy 1: điểm xuất phát chuyến bay.**

- Theo SQL chỉ-đọc ngày 08/10 (**chưa có report**; Phase 0 phải tái lập):
  - chuyến bay là món mua cuối của 1.424/4.023 khách LLBO;
  - 534/534 khách có từ 2 vé trở lên chỉ bay từ một điểm xuất phát;
  - origin trùng `home_city` ở 1.354/1.424 khách.
- Engine chưa dùng origin, dù `UnitIndex.mask(origin_city=…)` (`unit_index.py:66-67`) và `origin_city` (`unit_attributes.py:106,155`) đều đã có.
- Khoảng trống (append-v1, trọng số 0,6/0,25): với món đích là chuyến bay, engine đạt hit@20 **0,858**, mpd **0,912**, bpr_dest **0,958** (`eval-2026-10-06-…:348`). Phải đo lại trên prodcopy.
- Đây là **đòn bẩy không rò duy nhất đã thấy** có thể nâng LLBO. Cart cũng nâng được nhưng bị rò (§2.2), và origin cũng có phần rò (§7.1).

**Đòn bẩy 2: ước lượng pop tốt hơn** bằng decay thời gian cộng shrinkage về trung bình nhóm. Việc này chạm mục chờ chốt **[C7]** (`hop-dong-tich-hop-search-recommendation.md:883`).

**Hạn chế:**

- Origin không đổi được theme, vì khách giả lập không có chuyến bay (`theme_exp.py:136-142`).
- Lợi của pop trên temporal và nexttrip là **cận trên do seed** cho tới khi đo trên DB G6.

**Kết luận chọn:** hai track.

- **Track chính, nhánh có chuyến mở:** origin, ưu tiên chuyến đã đặt, chuyến ảo, cart, chồng lên **B1′ = cấu hình PR-A**. Track này không phụ thuộc G2.
- **Track phụ, nhánh `none`:** pop_h, dormant, w_pop, chồng lên **B2 = B1′ + F14c + destCap2**. Đo trên cả `vota_prodcopy` lẫn `vota_g6pref_v1`, và đi cùng lộ trình G6 → G2 → G5b.

### 2.5 Bỏ hẳn (có bằng chứng)

| Hạng | Lý do bỏ |
|---|---|
| `tier_affinity` | Tier ngẫu nhiên. Giá trung vị khách sạn 1,295–1,326 triệu, sao 3,84–3,87 ở mọi hạng. Không có định nghĩa tier phía sản phẩm |
| `home_city` làm tín hiệu điểm đến | Trùng điểm đến đích 7,8–9,3 %, mức ngẫu nhiên là 8,0–8,5 % |
| `last_destination`, `lifecycle_stage` lấy từ snapshot | Lộ đáp án (99,9 % ở LLBO). Tính lại as-of thì về mức ngẫu nhiên |
| `freshness` | Không có created/updated. `lastSeenAt` là thời điểm crawler thấy |
| `repeat_penalty` | Ẩn món đã xem làm mất 0,134 LLBO h@4 |
| Half-life theo loại event **trong chuyến**, decay của search | Núm decay trong chuyến không có tác dụng theo cấu trúc. Search có 100 % `product_id` NULL. Làm hỏng AC 20-21. (Decay **giữa các chuyến** thì không bỏ: D-typeLong) |
| Ngưỡng dormant giữ 180 ngày | Người dùng chốt 365 ngày (§0). 180 chỉ còn là arm đối chiếu `N0-180` |
| Urgency trong điểm | Không có giả thuyết. Chỉ dùng làm stratum |
| Hiệu chỉnh cos trên nhánh có chuyến mở | F1 (tập con 800 khách): LLBO h@4 0,5737 → 0,4188 |

---

## 3. Công thức đề xuất (OPH-L)

### 3.1 Ký hiệu

- `E_i`: vector e5-small (384 chiều, đã chuẩn hoá L2). `cos_x(i) = E_i · u_x`.
- `cal(c) = clip((c − Q_LOW)/(Q_HIGH − Q_LOW), 0, 1)`.
  - Q ghim theo plan giai đoạn lane B: **0,8529/0,9387**.
  - Mỗi lượt chạy hiệu chỉnh lại trên seed 99 và **ghi cả hai** vào report.
- `D` = điểm đến của chuyến hoạt động, hoặc tham số `destination`.
- Event, trip, cap lặp (kể cả `CAP_EXEMPT_EVENTS` của PR-A), `W_TYPE`, `H_SHORT = 30` giữ nguyên.

### 3.2 Lớp profile và luật chuyến

**Các tập chuyến**

- `O = {t : trip_is_open(t)}`. Luật if/else giữ nguyên, không có `grace_period` (§8.3, D5).
- `B = {t ∈ O : có purchase}`.
- `S = O \ B` gồm chuyến `_solo_` xem hoặc giỏ:
  - view mở khi `age ≤ 14`;
  - cart mở khi `usingDate ≥ hôm nay`, **bất kể tuổi**, nên `S` có thể chứa cart cũ hơn 14 ngày.
  - Ngược lại, một cart mới mà `usingDate` đã qua thì đã đóng, nên `ctx = none` vẫn xảy ra được với khách vừa có cart.

**Các vector**

- `conf_t` = độ tin cậy P2 (`profile_variants.py:93-97`; bản engine theo PR-A).
- `u_long = normalize(Σ_t 2^(−age_t/H_L)·conf_t·v_t)`, với `H_L = 365`. Riêng P3 ở bậc N2 dùng `H_L = 1095`.
- `u_trip = v_{t_b}`, với `t_b = argmin_{t∈B} age_t`.
- `u_session = normalize(Σ_{t∈S} 2^(−age_t/H_SESS)·conf_t·v_t)`, với `H_SESS = 7`, độ nhạy 3.

**`active_trip` và vector ngắn hạn theo bậc** (đánh số bậc theo §4)

| Bậc | `active_trip` (mask, loại taxonomy, ANN, explain) | Vector ngắn hạn trong điểm |
|---|---|---|
| B0/B1′/B2, O1, O2 | Như production: chuyến trẻ nhất trong `O` | `active_trip.vec`. `u_trip` **chưa dùng** |
| O3 (I-3) | `t_b` nếu có, nếu không thì chuyến trẻ nhất trong `S` | `u_trip` khi `ctx = booked`, ngược lại `active_trip.vec` |
| ≥ O4 | `t_b` nếu có, nếu không thì chuyến ảo `T_S` | `u_trip` / `u_session` |

Chuyến ảo `T_S`:

- `vec = u_session`; events là hợp của các chuyến trong `S`;
- `destination` = mode có trọng số;
- `purchased_taxonomies = ∅`.

Khi `|S| = 1`, `T_S` trùng production.

**`ctx` và các nhãn**

- `ctx` = `booked` / `session` / `none`.
- `strategy`, `n_events` (chỉ đếm chuyến thật), `diagnostics.trips` và `coldStart` giữ đúng nghĩa contract (`common.yaml:95-107`; `use_cases.py:176-177`).
- `diagnostics.dormant` giữ nghĩa contract 90 ngày.

### 3.3 Điểm

```
ctx = booked :  s(i) = 0,70·cos_short(i) + 0,15·pop(i|D) + 0,15·cos_long(i) − W_ORIGIN·mis(i) + W_CART·cart(i)
ctx = session:  s(i) = (như trên)
ctx = none   :  s(i) = 0,65·cal(cos_long(i)) + w_pop(seg)·pop_N(i) ,  route sai origin bị MASK   (rồi MMR + destCap2)
```

- Hai nhánh có chuyến mở dùng **cos thô** và `pop` production (`unit_scores`, hộp 90 ngày). Ở track chính, pop **không đổi**.
- Nhánh `none` với `w_pop = 0,35` và `pop_N = pop` **đúng là F14c**. `pop_N = pop_h` chỉ có từ bậc N1.

**pop_h (bậc N1, chỉ áp cho `ctx = none`, cả pool lẫn điểm)**

```
n_i = Σ_{purchase p của i, booked_at ∈ (now−730d, now]} 2^(−(now − booked_at)/H_POP)
m_g = trung bình n_j trên unit recommendable j ∈ g(i) = (destination(i), taxonomy(i))
pop_h(i) = (n_i + α·m_g) / max_j (n_j + α·m_j)
```

- Grid TUNE: `H_POP ∈ {45, 90, 180}`, `α ∈ {0; 0,5; 1; 2}`. Giới hạn trên 180 ngày.
- Parity: hộp 90 ngày với `α = 0` phải ra đúng dict production.
- Biến thể toàn cục, áp cả nhánh có chuyến mở, là arm chẩn đoán D-popGlobal (§4.4). Arm này bị xét theo G1-open′, không theo G1-open.

**mis(i): lệch điểm xuất phát**

- `ô` = `origin_city` của route đứng sau event chuyến bay gần nhất (purchase, cart hoặc view) trong train. Ghi `ôSource` ∈ {target-unit, khác} để phân tầng (§7.1).
- `mis(i) = 1` nếu `taxonomy(i) = flight`, `ô ≠ None` và `origin_city(i) ∉ {"", ô}`.
- **Nhánh có chuyến mở:** phạt `W_ORIGIN` (khởi tạo 0,30, grid {0,05; 0,15; 0,30} × {penalty, mask}).
  - Lập luận trội (route sai origin luôn xếp dưới route đúng) chỉ đúng ở nhánh này: ở đây độ trải điểm ≈ 0,85·(độ trải cos thô) + 0,15·(độ trải pop).
  - Phase 0 phải **đo độ trải điểm thật** của ứng viên chuyến bay trên nhánh mở.
  - Unit test kiểm rank guard: "không route sai origin nào xếp trên route đúng origin tốt nhất".
- **Nhánh `none`:** dùng **mask**, vì dải điểm ≈ 0,65 + 0,35 = 1,0 (cal ∈ [0,1], `step2_scorers.py:42`; pop ∈ [0,1], `popularity.py:69-70`), nên mức phạt 0,30 không đảm bảo trội.

**cart(i)**

- `cart(i) = 1` nếu có `add_to_cart` trong 30 ngày và chưa mua. `W_CART` ∈ {0; 0,05; 0,10}. Chỉ áp ở nhánh có chuyến mở.
- Các món này được thêm vào pool nếu qua mask, qua một wrapper port mới (`pool.py`, §5.1). Vector đã có sẵn nhờ lượt `vectors()` ở `use_cases.py:108`.

**MMR**

- λ = 0,7, tối đa 2 món mỗi taxonomy. destCap2 khi `ctx = none`.
- Lưu ý: λ ∈ {0,7; 0,8} chỉ được kiểm ở nhánh `none` nếu `dest_diversity` đọc `profile.MMR_LAMBDA` **lúc gọi**. Hiện nó import theo giá trị (`dest_diversity.py:25,61`), nên phải sửa (§5.1).

### 3.4 Segment và bảng trọng số

Segment suy từ event as-of. Không đọc `app.users.persona`, không đọc `cdp.profiles`. Tên trường là `segment` (AGENTS.md §6.4).

| Nhãn DDL | Luật | Trọng số |
|---|---|---|
| P1_frequent | Có purchase, không dormant | Mở: 0,70/0,15/0,15 thô · `none`: 0,65 cal / 0,35 pop_N |
| P2_first_time | Có event, không purchase | Như P1. N4 thử 0,45 |
| P3_dormant | Có purchase, `ctx = none`, chuyến trẻ nhất > **365 ngày** (chốt 09/10) | `none`: 0,65/0,35. N2: `H_L = 1095`. N3: w_pop 0,50 |
| P4_no_history | Không có chuyến | `_cold_start` giữ nguyên (`use_cases.py:122-123,180-205`) |

**V7 cũ, nay là N2 (`H_L × 3`), không có căn cứ spec.**

- Spec định nghĩa `halfLifeDays` = 30, là decay **theo event** (`hop-dong-tich-hop-search-recommendation.md:532,540`).
- Dormant theo spec là "event gần nhất > 90 ngày", và khi đó `halfLifeDays × 3` (`:688-689`).
- Code đang dùng 180 ngày tính từ chuyến trẻ nhất (`profile.py:17`).
- N2 là tuning thăm dò. Kèm một arm **N2s** làm đúng nguyên văn spec (`H_SHORT × 3` khi event gần nhất > 90 ngày). Arm này gần như không tác dụng theo cấu trúc, và chỉ để ghi nhận xung đột 90/180 (I-8).

### 3.5 Decay theo loại event (quyết định)

| Event | Trong chuyến | Giữa các chuyến (`u_long`) | Lớp phiên | Ghi chú |
|---|---|---|---|---|
| purchase | 1,0 × 2^(−d/30) | 2^(−age/365) × conf | — | Núm trong chuyến không có tác dụng (§1.3) |
| add_to_cart | 0,5 × 2^(−d/30) | conf 0,5 | H_SESS 7 | |
| product_view | 0,2 × 2^(−d/30) | conf 0,2 (P2) | H_SESS 7 | |
| search | không vào | — | — | product_id NULL |

- `H_SHORT_DAYS = 30` giữ nguyên, nên AC 20-21 vẫn đúng.
- **D-typeLong** (chẩn đoán): half-life giữa các chuyến theo loại event chi phối của chuyến (purchase 540 / cart 135 / view 60 ngày, theo brainstorm §8). Arm này đo một ý tưởng chưa từng thử, không ứng tuyển.

### 3.6 `using_date`

- Chỉ dùng để quyết định chuyến mở hay đã đóng.
- `days_to_use` ghi làm stratum.
- Không mask theo ngày. Không có grace period.

### 3.7 `because[]` vẫn trung thực

- `explain` phân rã theo chính vector đang lái điểm: các event của `t_b`, các event hợp của `T_S` (trọng số theo lớp phiên), hoặc `u_long` với `conf_t`.
- Sửa thiếu sót đang có: chia cho `‖v_t‖` của từng chuyến (`tong-hop.md:126`).
- Unit test kiểm **đóng góp có dấu, trước bước lọc dương và chuẩn hoá lại** (`profile.py:188-192`): tổng phải khớp `cos(u, E_i)` với `atol = 1e-5`, cùng mức sai số parity hiện dùng (`eval_profile.py:62`). E là float32.
- `pop`, `mis`, `cart` không sinh lý do mới. Giữ enum `BecauseEvent` (`common.yaml:109-115`).
- Đo because coverage. Không được thấp hơn B1′.

### 3.8 Hằng mới khi đưa lên production

- `profile.py` (vào `configHash`, `recsys_bench/engine.py:99-110`):
  - `H_SESSION_DAYS`, `DORMANT_H_LONG_MULT`, `W_POP_NONE`, `W_ORIGIN`, `W_CART`;
  - nhóm Q đặt tên theo PR-B của plan giai đoạn: `SEMANTIC_Q_LOW`, `SEMANTIC_Q_HIGH`, `SEMANTIC_CALIBRATION_MODEL_VERSION`;
  - `MAX_PER_DESTINATION`;
  - tăng `ENGINE_RULES_VERSION`.
- `popularity.py`: `H_POP_DAYS`, `POP_SHRINK_ALPHA` (chỉ sau khi chốt [C7]). `engine_config` phải được mở rộng để hash cả hằng HOA của `popularity.py`. Hiện nó chỉ hash `profile.py` và `POPULARITY_WINDOW_DAYS`.
- **Không** đưa `ORIGIN_OF_HOME` vào production. Hằng này chỉ nằm trong `theme_study/origin.py` cho D-O2.

---

## 4. Thang ablation

Mọi quyết định giữ/bỏ bậc, mọi luật dừng theo trần Z, và mọi lựa chọn tham số đều làm trên **TUNE**. TEST chỉ chạy **một lần** cho chuỗi đã đóng băng (§7.1).

### 4.1 Mốc và cổng parity

| ID | Định nghĩa | Điều kiện |
|---|---|---|
| **B0** | Production 08/10 (P0+F0) | Tái lập `baseline_v2` (`regress` exit 0) và bảng theme_study 08/10 (0,5329 / 0,1587 / 0,0785 / 0,439) |
| **B1′** | PR-A: P2 (`CAP_EXEMPT_EVENTS`) + loại combo + ô B | Nếu PR-A đã merge thì là engine thật. Nếu chưa, dùng gương harness (`profile_variants` P2 + mirror `purchase_closure` + ô B từ `eval_slots`), và sau khi merge phải parity nDiscordant = 0 |
| **B2** | B1′ + F14c + destCap2 | Tái lập 0,5324 / 0,1277 / 0,0469 / 0,756 / nextDestHit@20 0,4181. Riêng ô B và combo có thể lệch, ghi lại |
| **V0p** | Đường code OPH-L, `confidence=False`, mọi công tắc tắt | **nDiscordant = 0** so với B0, trên mọi stratum kể cả coldstart. Không đạt thì dừng |
| **V1p** | Như V0p với P2 + combo + ô B | nDiscordant = 0 so với B1′ |
| **V2p** | V1p với nhánh `none` = F14c + destCap2 | nDiscordant = 0 so với B2 |

### 4.2 Phase 0: trần (rò có chủ đích, chạy trên **TUNE**)

| ID | Mục đích | Luật dừng (trên TUNE) |
|---|---|---|
| Z-tax | Tách h@4/h@20 của B0/B1′ theo `targetTax`, `originKnown`, `ôSource`, target-in-cart. Đo độ trải điểm ứng viên chuyến bay | — |
| Z-orig | B1′ + mask origin theo origin của route đích | Trần − B1′ < +0,01 trên temporal flight-target (hoặc LLBO không có target-in-cart, xem §9.2 Q2) thì **bỏ** O1–O2 |
| Z-pop | B2 với pop = xác suất bộ sinh | Lặp lại vòng bốc lại có `w.has(…, home)` và `VINPEARL_BOOST`. Không khớp được thì ghi "trần xấp xỉ". Trần − B2 < +0,005 ở cả temporal và nexttrip thì **bỏ** N1 |
| Z-cart | B1′ + đưa món trong giỏ vào pool, với cart = 1 cho món đích. Target đi qua ô trạng thái theo request | Trần − B1′ < +0,01 trên temporal-open thì **bỏ** O5 |

### 4.3 Các bậc

**Track chính, nhánh có chuyến mở, chồng lên B1′:**

| ID | Thay đổi | Loại kiểm (khai trước) | Chỉ số đích (TUNE) | Kỳ vọng |
|---|---|---|---|---|
| **O1** | `mis` penalty (mở) + mask (`none`), `ô` suy từ event | Superiority | temporal h@4, stratum flight-target ∪ open (B10) | +0,005…+0,03, bị chặn bởi Z-orig. Theme nDiscordant = 0 |
| O2 | O1, chế độ mask ở mọi nhánh | Ablation, không vào chuỗi | như O1 | ≈ O1 |
| **O3** | O1 + ưu tiên chuyến đã đặt (I-3) | Conformance + NI | `booked_browse`: cross_vertical 100 %. Thực: LLBO h@4 cận dưới ≥ −0,01, temporal h@20 cận dưới ≥ −0,02 | Làm đúng FR-REC-02 |
| **O4** | O3 + chuyến ảo `T_S` | Conformance + NI | `session_multi` (conformance). Thực như O3 | Không đổi khi `|S| = 1` |
| **O5** | O4 + `W_CART` + món trong giỏ vào pool (`pool.py`) | Superiority | temporal-open h@4 (stratum ≥ 30 hit mốc) | LLBO chỉ báo cáo (rò) |

**Track phụ, nhánh `none`, chồng lên B2 + chuỗi O đã giữ.** Đo trên `vota_prodcopy` **và** `vota_g6pref_v1` (lane B2):

| ID | Thay đổi | Loại kiểm | Ghi chú |
|---|---|---|---|
| **N1** | `pop_h` chỉ ở `ctx = none` | Mô tả trên prodcopy (cận trên do seed). NI theme (cận dưới ≥ −0,02). Quyết định trên DB G6 | G1-open áp dụng: syn_open và LLBO nDiscordant = 0 |
| **N2** | `H_L = 1095` cho P3 | Mô tả / NI | Thăm dò, không phải spec. Kèm N2s |
| **N3** | `w_pop(P3) = 0,50` | Mô tả (cận trên do seed) | Giữ chỉ khi theme `syn_dormant` giảm ≤ 0,10 và DB G6 không âm |
| N4 (tuỳ chọn) | `w_pop(P2, none) = 0,45` | Mô tả | temporal first-time chỉ có n = 23 |

Các bậc N nằm trên **nhánh song song**. Nếu [C7] bị từ chối thì chuỗi O vẫn nguyên giá trị.

### 4.4 Arm chẩn đoán (không ứng tuyển)

| ID | Mục đích |
|---|---|
| D-O2 | O1 + dự phòng `ô` bằng `home_city`. Cận trên của bộ sinh. Production không đọc được profile (§8.3) |
| D-ôNoTgt | O1 với `ô` tính **sau khi loại event trên chính unit đích** (dùng thông tin target). Đo phần lợi origin đến từ rò giỏ hàng |
| D-shuffleO | O1 với `ô` hoán vị ngẫu nhiên giữa các khách có chuyến bay. Đối chứng rỗng, thay D-null (không có đường dữ liệu tier, xem §2.5). Độ lớn Δ là sàn nhiễu |
| D-popGlobal | `pop_h` áp ở mọi nhánh. Xét theo G1-open′ |
| D-pool / D-score | `pop_h` chỉ áp cho pool, hoặc chỉ áp cho điểm |
| D-union | `pool.py` thêm truy vấn ANN theo `u_session` và `u_trip`. Production không thêm truy vấn |
| D-popOnly | `w_pop(none) = 0,60`. Bằng chứng bẫy seed |
| D-typeLong | Decay giữa các chuyến theo loại event (§3.5) |
| OPH-prod | B0 + các bậc O đã giữ + N1, không có F14c. Bản dự phòng (G7, chốt 09/10): vào Phase 2 cùng F_O và F |

---

## 5. Kế hoạch code

### 5.1 Pha A: chỉ bench (`src/evaluation/recsys_bench/`)

Điều kiện: đã đưa worktree lên `feat/recSys_update` **sau khi lane A commit**. Code dựa trên:

- `eval_split(…, idx, …)` có `destHit@20` (diff lane A trong `eval_formula.py`);
- split `coldstart` trong `eval_profile.py`;
- các file `frozen/split-*-prodcopy-asof20261008.json`.

1. **`theme_study/registry.py`**: gom phần đăng ký F13/F14 đang lặp ở `eval_profile.py:165-177`, `rank_latency.py:45-56` và `eval_slots.py:78-88`. Tên cấu hình theo dạng `<profile>+<scorer>[+destCapN][+origin:<mode>:<w>][+pop:<H>:<α>][+cart:<w>][+pool:<mode>]`. Các bí danh `B0`, `B1′`, `B2`, `V0p`…`N4` ghi **tường minh** mặc định: `confidence`, combo, ô B, cap.
2. **`theme_study/layered_profile.py`**: `make_layered_build_profile(*, confidence=False, booked_first=False, session_agg=False, h_session=7.0, dormant_hl_mult=1.0)`.
   - Mặc định **= P0** (parity với `build_profile` production). `confidence=True` thì bằng P2.
   - Ghi `ctx` và `segment` vào một **ô trạng thái theo request**, để `pop_smooth`, `oph_scorer` và `pool` đọc.
   - Mở rộng `parity()` (`eval_profile.py:51-81`).
3. **`theme_study/oph_scorer.py`**: cùng chữ ký với `score_candidates`. Đọc `taxonomy`, `origin_city`, `destination` lúc chấm điểm qua `TrackedSpace` (mẫu `dest_diversity.py:28-80`). Penalty ở nhánh mở, mask ở `none`.
4. **`theme_study/pool.py` (mới)**: wrapper `VectorSearchPort` truyền vào `OfflineEngine`.
   - `near_vector` nối thêm các hit là món trong giỏ hoặc đã xem, có tôn trọng `allowed` (O5, Z-cart).
   - Phát thêm truy vấn `u_session`/`u_trip` cho D-union.
   - Test: tắt thì nDiscordant = 0.
5. **`theme_study/origin.py`**: `infer_origin(...)` và `ôSource`. `load_home_city(dsn)` chỉ đọc cột `home_city`. `ORIGIN_OF_HOME` nằm ở đây.
6. **`theme_study/pop_smooth.py`**: `make_unit_scores(h_pop, alpha, window_days=730, box=None, scope="none"|"global")`. Đọc `ctx` từ ô trạng thái. Cache theo (as_of, destination).
7. **`theme_study/oracle_ceiling.py`**: Z-orig, Z-pop (lặp lại vòng bốc lại có `home` và `VINPEARL_BOOST`), Z-cart (target qua ô trạng thái).
8. **`theme_exp.py`**: ba kịch bản mới, mỗi kịch bản một rng riêng `seed·1_000_003 + k`. Tham số đóng băng trước lượt chạy đầy đủ.
   - `session_multi`: 3–5 lượt xem rải 2 điểm đến. **Ngẫu nhiên hoá** việc điểm đến đa số có phải điểm đến xem gần nhất không. Đích = khách sạn ở điểm đến đa số, **loại các unit đã xem**. Kịch bản này là **conformance**.
   - `booked_browse`: lịch sử `between` + một chuyến đã mua (khách sạn ở X, có `eventGroupId`, mua 5–30 ngày trước, `usingDate` = AS_OF + 5…30 ngày) + 2–4 lượt xem sau đó, cách 1–72 giờ (50 % ở X, 50 % ở điểm đến khác). Đích = điểm tham quan hoặc route bay tới X. Đo `tgtHit@4`, `crossVerticalAtX@4`, `strategy`. Kịch bản này là **conformance**.
   - `dormant`: mọi chuyến cách 200–600 ngày.
   - Bỏ khách có target `None`: `World.pick` trả None khi pool (X, tax) rỗng (`theme_exp.py:70-72`).
9. **`eval_formula.eval_split` / `eval_profile.py`**:
   - Dòng per-user thêm: `segment`, `ctx` (tính trên P0, giống nhau ở mọi cấu hình), `strategy`, `targetTax`, `originKnown`, `ôSource`, `tgtInCart`, `routeSeen`, `rank20`, `becauseN`, `daysToUse`.
   - Port catalog coverage, exposure gini và distinct destinations từ CLI `metrics.py`.
   - Cờ mới:
     - `--configs`;
     - `--user-part tune|test|all` (`sha1(uid) mod 10 < 3` là tune);
     - `--split-file frozen/...` (kiểm sha256);
     - `--filter-events`;
     - `--strata-by`;
     - `--db-label`.
10. **`paired_ci.py` / `tables.py`**:
    - Chỉ số lấy từ dữ liệu, không dùng whitelist cố định. Hiện chỉ có `SPLIT_METRICS`/`SYN_METRICS` (`paired_ci.py:25-27,45`).
    - **Sửa p-value:** `p = min(1, 2·min(P(mean ≤ 0), P(mean ≥ 0)))`; `p = 1` khi nDiscordant = 0. Công thức cũ `2·min(shareBootGt0, 1−shareBootGt0)` ra p = 0 với hai arm giống hệt nhau, vì `shareBootGt0` đếm `means > 0` (`paired_ci.py:69`).
    - Thêm `--family` + Holm, `--split-by`, `--ni-margin`.
    - Dùng `--compare` và `--boot` **đã có** (`paired_ci.py:151-152`) để so từng bậc với bậc trước.
    - `tables.SPLIT_COLS` lấy từ dữ liệu.
11. **`dest_diversity.py`**: đọc `profile.MMR_LAMBDA` lúc gọi, không import theo giá trị.
12. **`rank_latency.py`**: arm cài qua `registry.install`.
    - `OfflineEngine(popularity_cache ≥ n_users)` (mặc định 8, `engine.py:64`), hoặc đo `popularity_at` thành stage riêng.
    - `pop_h` tính sẵn cho mỗi as_of, ngoài vùng đo giờ.
    - Stage: popularity / build_profile / ANN / score / MMR / explain.
13. **`recsys_bench/engine.py:engine_config`**: hash thêm hằng HOA của `popularity.py`.
14. **Test** (không cần DB), trong `src/evaluation/recsys_bench/tests/`:
    - `test_layered_profile.py`:
      - mặc định = P0 và `confidence=True` = P2;
      - ưu tiên chuyến đã đặt;
      - `|S| = 1` thì bằng production;
      - mode có trọng số;
      - `n_events` không đếm trùng;
      - cart cũ hơn 14 ngày mà `usingDate` chưa qua vẫn ở trong `S`;
      - nhãn segment trên 4 lịch sử đồ chơi.
    - `test_oph_scorer.py`: tắt hết thì bằng `score_candidates`; nhánh `none` = F14c; `mis` đúng trên taxonomy hỗn hợp; rank guard origin.
    - `test_pool.py`: parity khi tắt; tôn trọng `allowed`.
    - `test_pop_smooth.py`: parity hộp 90 ngày; công thức shrinkage; cache không vượt qua `as_of`; `scope="none"` không đụng nhánh mở.
    - `test_origin.py`: không có event chuyến bay; origin xung đột; `origin_city == ""`.
    - `test_explain_exact.py`: đóng góp có dấu với `atol = 1e-5`.
    - `test_paired_ci.py`: p = 1 khi d ≡ 0; trường hợp có hoà; thứ tự Holm so với ví dụ tính tay.
    - `test_registry.py`: phân tích tên cấu hình, khứ hồi.
    - `test_theme_exp_hash.py`: hash event của between/open/noisy_paired với seed 42/7/2026 trùng hash trước thay đổi.
    - Chạy `pytest src/evaluation/recsys_bench/tests src/evaluation/recsys_bench/theme_study`. Mốc lần trước: 160 passed, 4 xfailed.

### 5.2 Pha B: đưa lên production (PR đích `release-mvp-v2`)

**Track chính** đi sau PR-A, có đề xuất riêng (§8.2). **Track phụ** gộp vào PR-B.

1. **`profile.py`**:
   - các hằng ở §3.8;
   - `build_profile` có `booked_first`, `u_session`/chuyến ảo, `segment`, `ctx`;
   - `score_candidates(profile, E, pop, ctx: ScoreContext | None = None)`. `ctx=None` phải ra **giống từng byte** hiện tại;
   - `mmr_select(..., destination, max_per_destination)` (PR-B);
   - `explain` phân rã chính xác;
   - `infer_origin` thuần domain;
   - guard version Q khớp `f"{embed_model}:{TEXT_BUILDER_VERSION}"`.
2. **`popularity.py`**: thêm `unit_scores_smoothed(destination, …)`, tính sẵn ở lượt refresh 900 giây (`main.py:198,305-382`). **Giữ nguyên `unit_scores`**, để listing và suggest (`main.py:135,238,270`) và cold start (`use_cases.py:209`) không đổi.
3. **`use_cases.py:125-163`**: dựng `ScoreContext` sau khi đã đủ ứng viên; thêm món trong giỏ vào pool; dùng `unit_scores_smoothed` chỉ khi `ctx = none`. Không thêm I/O.
4. **Test**:
   - unit `domain`/`application` ≥ 80 %;
   - sửa `test_engine_no_leak.py:43-53` và `test_recommendation_trip_open.py` theo I-3;
   - AC 16-18;
   - `src/backend/tests/architecture`;
   - gate registry (lưu ý "today" theo UTC, `models/seeds.py:36-38`);
   - parity HTTP 60/60 trên bộ A1;
   - `make recsys-gate-run` → `baseline_v3`/`v4` theo plan giai đoạn.
5. **Latency** (G1): đo SAU bằng đúng bộ A1 (cùng env, collection `ProductE5SmallProdcopy`, hai file khách), xen kẽ trước/sau.
6. **Spec** `hop-dong-tich-hop-search-recommendation.md`: §4.4, §4.5, §4.7, §4.8 (sau [C7]). Contract OpenAPI không đổi.

---

## 6. Môi trường và lệnh

**S0 môi trường.** Worktree không có `.venv`, không có `.env`, không có vector.

- Settings đọc `REPO_ROOT/.env` (`core/config.py:22-23`) và lặng lẽ bỏ qua khi file không có.
- Vector chỉ có trong `recsys-theme-2026-10-08-ban-giao.zip` ở thư mục gốc của bản checkout chính.

```bash
# Git Bash, từ repo root của worktree; container vota-prodcopy-pg (:55433) đã chạy
PY=/d/Study/VinAI20K/VSF/Travel-Recommendation-Product/.venv/Scripts/python.exe   # interpreter của checkout chính
VECDIR=/d/Study/VinAI20K/VSF/recsys-vec/2026-10-08                               # ngoài repo, giải nén một lần từ gói bàn giao
# kiểm meta: model + text_builder_version của $VECDIR/vec_prodcopy_e5s.meta.json phải khớp TEXT_BUILDER_VERSION
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55433/vota_prodcopy
export CDP_DATABASE_URL=$DATABASE_URL EVAL_DATABASE_URL=$DATABASE_URL SEED_DATABASE_URL=$DATABASE_URL
export WEAVIATE_URL=http://127.0.0.1:59999 PYTHONIOENCODING=utf-8 PYTHONUTF8=1    # export tường minh: không có .env
VEC=npy:$VECDIR/vec_prodcopy_e5s ; AS_OF=2026-10-08T00:00:00+00:00
OUT=src/evaluation/recsys_bench/theme_study/results/2026-10-DD-oph ; mkdir -p $OUT
F=src/evaluation/recsys_bench/frozen
SPL="--split-file $F/split-llbo-prodcopy-asof20261008.json,$F/split-temporal-prodcopy-asof20261008.json,$F/split-nexttrip-prodcopy-asof20261008.json"
SC="--n-syn 80 --scenarios between,open,noisy_paired,session_multi,booked_browse,dormant --syn-target"
COMMON="--vec $VEC --as-of $AS_OF $SPL $SC --strata-by segment,ctx,targetTax,ôSource"
M=src.evaluation.recsys_bench.theme_study

# A0: smoke + parity + bấm giờ MỘT cấu hình đầy đủ (để lập lại lịch)
$PY -m $M.eval_profile $COMMON --configs B0,V0p --max-users 200 --syn-seeds 13 --out $OUT/smoke.json --per-user-out $OUT/smoke.jsonl
# Phase 0 (TUNE, cùng bộ cờ): mốc + parity + trần
$PY -m $M.eval_profile $COMMON --configs B0,B1p,B2,V0p,V1p,V2p --user-part tune --syn-seeds 13 \
    --out $OUT/p0.json --per-user-out $OUT/p0.jsonl            # dừng nếu V*p nDiscordant > 0
$PY -m $M.oracle_ceiling $COMMON --user-part tune --syn-seeds 13 --arms Z-tax,Z-orig,Z-pop,Z-cart --out $OUT/p0_oracle.json
# Phase 1 (TUNE): grid + giữ/bỏ bậc; lặp lại cho DB G6 với DATABASE_URL=.../vota_g6pref_v1 và split -g6pref-v1- (track N)
$PY -m $M.eval_profile $COMMON --configs "<grid>" --user-part tune --syn-seeds 13 --out $OUT/tune.json --per-user-out $OUT/tune.jsonl
$PY -m $M.paired_ci --per-user $OUT/p0.jsonl $OUT/tune.jsonl --compare "B1p:O1,O1:O3,O3:O4,O4:O5,B2:N1,N1:N2,N2:N3" \
    --boot 10000 --ni-margin 0.01 --split-by segment,ctx --out $OUT/tune_ci.json
# Phase 2 (TEST, MỘT lần, seed mới; tối đa 2 tiến trình): chuỗi đóng băng + mốc
$PY -m $M.eval_profile $COMMON --splits +coldstart --configs B0,B1p,B2,F_O,F,OPH-prod --user-part test --syn-seeds 101,202,303 \
    --out $OUT/test.json --per-user-out $OUT/test.jsonl
$PY -m $M.paired_ci --per-user $OUT/test.jsonl --compare "B1p:F_O,B0:F_O,B2:F,B0:OPH-prod" --family $OUT/family.json --boot 10000 --out $OUT/ci.json
# Latency trong tiến trình (chẩn đoán, chạy MỘT MÌNH); G1 chấm bằng e2e A1 sau Pha B
$PY -m $M.rank_latency --vec $VEC --as-of $AS_OF --split nexttrip --k 4 --n-users 400 --repeat 3 --popularity-cache 400 \
    --arms "B0,B1p,F_O,F" --stages --out $OUT/latency_nexttrip.json
```

- `--configs`, `--user-part`, `--split-file`, `--strata-by`, `--family`, `--ni-margin`, `--split-by`, `--stages`, `--popularity-cache` là cờ mới. `--compare` và `--boot` đã có sẵn.
- Mọi lệnh Phase 0, 1, 2 dùng **cùng bộ cờ split/kịch bản**. Riêng coldstart chỉ có ở Phase 2 và chỉ để báo cáo.
- Một lượt bắc cầu B0/B2 trên split theme_study + seed 42/7/2026 để nối với report 08/10.

---

## 7. Giao thức bench

### 7.1 Split, TUNE / TEST, rò

**Split chính:** frozen prodcopy `asof20261008` (LLBO 4.023, temporal 773, nexttrip và coldstart lấy theo file). sha256 ghi vào report làm "split version" (AGENTS.md §7). Track N còn chạy trên split `-g6pref-v1-` của DB `vota_g6pref_v1`.

**TUNE / TEST**

- TUNE = `sha1(uid) mod 10 < 3`, TEST = 70 % còn lại.
- Seed giả lập:
  - seed 99 chỉ để hiệu chỉnh Q;
  - seed **13** cho TUNE;
  - seed **101/202/303 (mới)** cho TEST;
  - seed 42/7/2026 đã dùng để chọn F14c/destCap2, nên chỉ dùng cho bảng bắc cầu.
- Caveat ghi trong report: khách thật của TEST là tập con của nhóm đã dùng để chọn B2 (08/10 dùng toàn bộ khách), nên so sánh với B2 trên TEST không sạch hoàn toàn.

**Luật B10** (`recsys-offline-eval.md:234`, chốt 01/10): tham số chỉ tune trên temporal. `W_ORIGIN` và `W_CART` tune trên **temporal TUNE**, ở stratum flight-target ∪ open và temporal-open.

- Nếu Z-tax cho thấy các stratum này có < 30 hit mốc, phải **hỏi người dùng có miễn B10 không** (§9.2 Q2), và khi đó dùng LLBO đã loại khách có target trong giỏ.
- LLBO luôn chỉ để báo cáo và kiểm non-inferiority.

**Rò ở LLBO**

- 1.731/4.021 khách append-v1 có target trong giỏ (`eval-2026-10-06-…:151`). Prodcopy phải đo lại ở Z-tax.
- Với chuyến bay đích nằm trong giỏ, `ô` chính là origin của đích, tức trùng Z-orig.
- Vì vậy O1 và O5 báo LLBO theo `tgtInCart` × `ôSource`, có kèm D-ôNoTgt.

**coldstart:** chỉ báo cáo. Split này tăng đơn điệu theo W_SHORT (`eval-2026-10-07-recsys-grid-llbo-coldstart.md:59`).

**Ghi trong mọi report:** split theme_study bỏ qua `filter_events` (`eval_profile.py:131-136`); lịch sử là dữ liệu tổng hợp.

### 7.2 Chỉ số

- **Split thật:** hit@20, nDCG@10, MRR@20, destHit@20 (mode eval); hit@4 (mode prod, cap 2 mỗi taxonomy).
- **Giả lập:** themePrec chung và theo chủ đề, độ mất do nhiễu, nextDestHit@20/@4, distinctDestsTotal, tgtHit (không dùng để quyết).
- **Conformance** (không bao giờ vào Holm):
  - `booked_browse`: tỉ lệ cross_vertical, crossVerticalAtX@4;
  - `session_multi`: nextDestHit@4, tách theo "đa số = gần nhất" hay không.
- **Guardrail:** catalog coverage của top-4, distinct destinations, exposure gini, because coverage, flight-target h@4.
- **Strata:** `segment` × `ctx` × `targetTax` × `ôSource` × `tgtInCart`. Chỉ khẳng định bằng CI ở stratum có **≥ 30 hit mốc**, đếm hit chứ không đếm khách. temporal|P3 (68), cross_vertical (63), first-time (23) chỉ mô tả.

### 7.3 MDE và độ mạnh

- Trước Phase 1, tính SE ghép cặp thật của cặp B0–B1′ trên TUNE từ `p0.jsonl`. MDE ≈ 2,8 × SE.
- Ước lượng thô: temporal toàn bộ CI ≈ ±0,015; TEST 70 % ≈ ±0,018; TUNE 30 % ≈ ±0,027.
- Độ lệch giữa các seed giả lập 0,016–0,030 (`ci.md:156-158`).
- nexttrip không đo được lớp phiên: train là event trước lượt duyệt đầu tiên của chuyến mới (`splits.py:242-250`).
- Hệ quả, khai trước: N1, N2, N3 trên prodcopy **không thể** đạt superiority (kỳ vọng +0,000…+0,010, trong khi MDE ≈ 0,02). Vì vậy chúng được khai là mô tả/NI, và quyết định dựa vào DB G6.

### 7.4 CI và họ chỉ số chính

- `paired_ci.py`: bootstrap ghép cặp 10.000 lần (seed 20261008), p-value đã sửa (§5.1 mục 10). Báo kèm nDiscordant và `seed_spread`.
- **Trên TUNE (giữ/bỏ):** mỗi bậc so với bậc trước, theo loại kiểm đã khai ở §4.3. Không dùng Holm, vì đây là sàng lọc.
- **Họ chính trên TEST** (`family.json` commit trước Phase 2, Holm α = 0,05):
  - F_O vs B1′:
    - temporal h@4 stratum flight ∪ open (superiority, chỉ khi O1 hoặc O5 được giữ);
    - LLBO h@4 (NI −0,01);
    - syn_open themePrec (NI −0,02);
  - F_O vs B0: temporal h@20 (điểm ≥ −0,04), LLBO h@4 (CI chứa 0);
  - F vs B2 (track N, trên cả hai DB): nexttrip h@20, nextDestHit@20, temporal h@20, theme between, noisy_paired. Trên DB G6 áp luật D1–D5 của plan giai đoạn.
- Delta từng bậc trên TEST chỉ mô tả.

### 7.5 Luật giữ bậc (trên TUNE)

- **Superiority (O1, O5):** cận dưới CI 90 % một phía > 0 trên chỉ số đích, ở stratum có ≥ 30 hit mốc. Không vượt trần Z.
- **NI/conformance (O3, O4, N2):** đạt conformance (nếu có), và cận dưới CI 95 % ≥ −margin trên split thật (LLBO −0,01, temporal −0,02).
- **Mô tả (N1, N3, N4):** giữ khi DB G6 không âm (cận dưới ≥ −0,01) và theme không vượt ngưỡng ở §4.3.
- Mọi bậc: không vi phạm guardrail. Không đạt thì bỏ bậc và nối bậc sau vào bậc đã giữ gần nhất. Việc này **chỉ chạy lại trên TUNE**.
- Ưu tiên ít hạng hơn.

### 7.6 Cổng quyết định

| Cổng | Nội dung | Trạng thái |
|---|---|---|
| G1 | temporal h@20 giảm ≤ 0,04 (điểm); LLBO h@4 CI chứa 0; theme ≥ +0,15 (track F14c); `open` không đổi; **latency: Δp95 `diagnostics.latencyMs` ≤ 50 ms, đầu-cuối, backend local + Weaviate local, tổng và theo `strategy`** | **Đã chốt 08/10** (plan giai đoạn §1) |
| G2 | Lộ trình PR-A → G6 → chốt lại G2 theo D1–D5 | Đã chốt lộ trình. G2 sẽ chốt lại sau lane B |
| G1-LLBO(b) | Non-inferiority: cận dưới CI ≥ −0,01, thay cho "CI chứa 0" khi chia đôi khách | **Đã chốt 09/10** |
| G1-open | Bậc chỉ đụng `none` (N1, N2, N3, N4): nDiscordant = 0 ở `syn_open` và LLBO | Áp được vì N1 chỉ áp cho `ctx = none` |
| **G1-open′** (mới) | Bậc đụng nhánh mở (O1, O3, O4, O5, D-popGlobal): syn_open cận dưới ≥ −0,02 **và** LLBO đạt G1-LLBO(b) | **Đã chốt 09/10** |
| **G7** (mới) | OPH-prod (không F14c) thay F_O/F nếu G2 không qua: temporal h@20 giảm ≤ 0,04; LLBO h@4 đạt G1-LLBO(b); `open` theo G1-open′; latency như G1; **và** ít nhất một chỉ số đích của bậc O hoặc N1 có cận dưới CI > 0. Không yêu cầu theme +0,15 | **Đã chốt dùng 09/10**; tiêu chí này do plan đề nghị |

- Mốc latency e2e: server p95 **87,0 / 86,0 ms** (A1).
- A1 không có mẫu `cross_vertical`, nên đo `ctx = booked` cần bộ khách có chuyến đã đặt còn mở. Nếu không dựng được trên bản sao 08/10 thì ghi "chưa đo" và chỉ có số trong tiến trình.

### 7.7 Latency trong tiến trình (chẩn đoán)

- `rank_latency` chạy một mình, cache popularity ≥ số khách, có stage riêng cho popularity. **Đo lại B0 trước khi so**, vì số 29,62 / 38,63 / 40,09 ms (p50 / p95 / p99) có thể đã gồm việc dựng lại popularity.
- Không thay thế G1-latency.
- Công thức này không xử lý p95 cloud 1.057 ms.

### 7.8 Thời gian chạy

- Mốc ~8 phút/cấu hình của lượt 08/10 không còn đúng, vì:
  - coldstart (5.243 khách) đông hơn LLBO;
  - mỗi khách gọi engine 2 lần;
  - 6 kịch bản × 240 khách giả lập mỗi seed.
- Ước lượng mới, A0 sẽ bấm giờ để chỉnh lại:
  - Phase 1: khoảng 5–7 phút mỗi cấu hình TUNE (không coldstart). Khoảng 25 cấu hình × 2 DB / 2 tiến trình ≈ 2–3 giờ.
  - Phase 2: khoảng 15–20 phút mỗi cấu hình, 5 cấu hình + 3 D-arm ≈ 1–1,5 giờ.
  - Tổng **≈ 5–7 giờ máy**, chưa tính thời gian chờ chốt.

### 7.9 Đầu ra

- Report `src/evaluation/reports/eval-2026-10-DD-recsys-cong-thuc-oph.md`, gồm:
  - commit, run id, as_of, sha256 split, meta vector, Q;
  - `family.json`, tham số đã đóng băng;
  - bảng số chép nguyên văn từ output;
  - caveat, lệnh tái sinh.
- JSON vào `theme_study/results/2026-10-DD-oph/` (có SHA256SUMS).
- Mục mới trong `recsys-bam-so-thich-quyet-dinh.md`.
- Entry `history/` cho mỗi commit (§10).

---

## 8. PRD và tuân thủ

### 8.1 Không lệch PRD

- Toàn bộ Pha A: bench, harness, kịch bản giả lập.
- Đo latency, coldstart, chạy trên DB G6 (plan giai đoạn §2: "Không phải lệch PRD").

### 8.2 Lệch PRD khi lên production

Không dùng `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md`: file này đã bị tách thành [A], [B], [C] trên `feat/recSys_update`.

- **Track N (pop_h, w_pop, H_L):** gộp vào **[B]** `2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md`. Đề xuất này đang "chờ chốt — chưa trình chốt", đi cùng G6/G2 → G5b.
  - pop_h còn chạm **[C7]** (spec:883). AGENTS.md §2 cấm tự chọn.
- **Track O (origin, ưu tiên chuyến đã đặt I-3, chuyến ảo, cart):** chưa đề xuất nào đang có phủ phần này. [A] chỉ nói về ô khám phá. Ở S6 tạo đề xuất **[D] mới** cho FR-REC-02, hoặc gộp vào [A] nếu người dùng muốn (§9.2 Q6).
  - I-3 đổi hành vi FR-REC-02 (đưa về gần câu chữ PRD) và đổi các test đang ghim hành vi.
  - Chuyến ảo đổi nghĩa thực tế của `recent_activity`. Enum giữ nguyên.
  - Luật mở chuyến, N = 14 và nghĩa `usingDate` không đổi.
- **OPH-prod (G7):** đề xuất riêng, chỉ khi người dùng muốn.

### 8.3 Ngoài phạm vi plan này

| Mục | Lý do |
|---|---|
| D1. Bảng `app.user_recommendation_profile` | Bảng `app` mới; vector trong Postgres trái `data-model.md:47` |
| D2. Cache gợi ý Redis | `architecture.md:20,223`, `noeviction`; mục [P3] "CHỜ DUYỆT" |
| D3. Stale cache | Trái "lập tức" (`project-brief.md:49`), FR-BKG-04, AC-REC-02, AC-BKG-04 |
| D4. Precompute top-200 | Trái quyết định ANN mỗi request (archive 2026-09-24), NFR-PERF-03, FR-CAT-02 |
| D5. `grace_period`, cửa sổ 120 ngày | FR-REC-02 ghi "chưa qua" (spec:600-602) |
| D6. Loại `because` mới | `recommendations.yaml:6-11,107-111`, `common.yaml:109-115` |
| D7. Impression, CTR, bandit | FR-CDP-01, CHECK `vota_schema.sql:75-76` |
| D8. Taxonomy lifecycle mới | CHECK `lifecycle_stage`, nghĩa `diagnostics.dormant` |
| D9. Fine-tune, LightGBM | FR-SRC-02, `architecture.md` §4 |
| D10. Event stream, materializer | Thành phần kiến trúc mới |
| Đọc `cdp.profiles` trong request | `CdpHistoryReader` không có hàm đọc profile (`ports/cdp_client.py:129-152`). `get_profile` là async và mở connection mỗi lần (`local_cdp_client.py:143-145`) |

**Đề nghị đưa vào lane latency của plan giai đoạn (không lệch PRD, PR riêng, không thuộc Pha A):**

- Spec yêu cầu "tối đa 500 event mới nhất, bỏ event đã huỷ" (`hop-dong-tich-hop-search-recommendation.md:514`).
- `PostgresCdpReader.events_for_user` chưa có `LIMIT` (`postgres_cdp_reader.py:113-118`) và mở `psycopg.connect` mới cho mỗi request (`:97`).
- `max_events = 500` đã có ở `ports/cdp_client.py:103-105` và `history.py:19`, nhưng đường request không dùng.
- Đề nghị: thêm LIMIT 500 + dùng lại connection, đo bằng bộ A1. D1–D4 vẫn ngoài phạm vi.

### 8.4 Lệch tên persona (AGENTS.md §6.4)

- Code nội bộ dùng nhãn DDL (`vota_schema.sql:186`), suy từ event, đặt tên trường là `segment`.
- Không đưa `P1_family`…`P4_deal` vào code.
- Ngưỡng dormant: spec 90 ngày tính từ event gần nhất (`:688`), code 180 ngày tính từ chuyến. **Chốt 365 ngày** (§0). Bench dùng 365, có arm `N0-180` và N2s để đối chiếu. Sửa spec `dormantDays` và `DORMANT_AFTER_DAYS` theo đề xuất [E]; `diagnostics.dormant` (contract, 90 ngày) giữ nguyên.

### 8.5 Brainstorm doc

- File chưa track, không ghi FR/NFR, có các lỗi ở §1.2.
- Đề nghị: sửa lỗi và gắn nhãn "nghiên cứu, không chuẩn tắc", hoặc chuyển phần kiến trúc sang một đề xuất. Plan này không sửa file đó.

---

## 9. Rủi ro và câu hỏi mở

### 9.1 Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Worktree cũ, xung đột với lane A chưa commit | S0: đưa lên `feat/recSys_update` sau khi lane A commit. Code trên `eval_split(idx)` |
| Seed không có sở thích nên pop thắng | Track N quyết trên DB G6. D-popOnly làm bằng chứng. Ghi "cận trên" |
| Lợi origin do bộ sinh hoặc do rò giỏ hàng | Penalty + origin suy từ event. D-O2 là trần, D-ôNoTgt đo phần rò, D-shuffleO là sàn nhiễu. Phân tầng theo `ôSource` |
| Tune lẫn vào test | Mọi quyết định trên TUNE. TEST chạy một lần với seed mới. `family.json` commit trước |
| `session_multi` tự xác nhận giả thuyết | Chỉ là conformance, ngẫu nhiên hoá "đa số = gần nhất", loại unit đã xem khỏi đích |
| Thiếu độ mạnh | Khai trước superiority hay NI. Ngưỡng ≥ 30 hit. Track N chỉ mô tả trên prodcopy |
| Latency trong tiến trình bị lẫn bước dựng popularity | Cache ≥ số khách, stage riêng. G1 chấm bằng e2e |
| p-value bootstrap sai khi có hoà | Sửa công thức và thêm test |
| `pop_h` đổi search/listing | Thêm method mới, giữ `unit_scores` |
| Q trôi khi đổi model hoặc text builder | Guard version |
| λ không tới được destCap MMR | Sửa `dest_diversity` đọc lúc gọi |
| B1′ trong harness lệch PR-A thật | Parity sau khi PR-A merge |
| Ưu tiên chuyến đã đặt loại quá tay | Ô B (G4) bù một phần. Theo dõi `booked_browse` 50 % nơi khác |

### 9.2 Câu hỏi cần người dùng chốt

**Đã trả lời 09/10 — xem §0.**

1. **G1-LLBO(b):** đổi sang non-inferiority (cận dưới CI ≥ −0,01)?
2. **B10:** nếu temporal flight-target / open có < 30 hit, có miễn B10 để tune `W_ORIGIN`/`W_CART` trên LLBO đã loại khách target-in-cart không?
3. **G1-open′:** có cho phép các bậc đụng nhánh mở không, và theo tiêu chí ở §7.6?
4. **G7:** có muốn track OPH-prod độc lập không?
5. **[C7]:** đưa pop_h (decay + shrinkage, chỉ `ctx = none`) vào phạm vi quyết định?
6. Track O: tạo đề xuất **[D] mới** hay gộp vào [A]? Có chấp nhận I-3 đổi hành vi FR-REC-02 không?
7. Ngưỡng dormant chuẩn: 90 / 180 / 365?
8. Hợp nhất persona PRD/DDL.
9. Có đưa "LIMIT 500 + dùng lại connection" vào lane latency của plan giai đoạn không?
10. Brainstorm doc: sửa và đánh dấu không chuẩn tắc, hay chuyển thành đề xuất?
11. Cho phép merge hoặc rebase `feat/recSys_update` vào `feat/recSys_update-2` ở S0?

---

## 10. Các bước thực hiện

```
S0 (env + đồng bộ nhánh) ─► S1 harness ─► S2 Phase 0 (TUNE) ─► [luật dừng] ─► S3 Phase 1 (TUNE, đóng băng) ─► S4 Phase 2 (TEST 1 lần) ─► S5 report ─► S6 gate ─► S7 Pha B
                                                   Track N cần lane B2 (DB G6) ─┘
```

| Bước | Việc | Ước lượng | Checklist |
|---|---|---|---|
| S0 | ~~Duyệt plan; merge `feat/recSys_update`; ghi plan + history~~ **Xong 09/10** (`eff8abc`). Còn: venv tuyệt đối, giải nén vector, kiểm meta | 0,5 giờ | - [x] duyệt · - [x] nhánh đồng bộ · - [ ] env · - [x] history |
| S1 | Harness §5.1 (mục 1–14) + test. **Commit + history `dang dở`** | 2–2,5 ngày | - [ ] registry · - [ ] layered_profile (mặc định P0) · - [ ] oph_scorer · - [ ] pool · - [ ] origin · - [ ] pop_smooth · - [ ] oracle · - [ ] kịch bản + hash test · - [ ] split đóng băng · - [ ] metric port · - [ ] paired_ci (p-value, Holm, NI) · - [ ] λ · - [ ] rank_latency · - [ ] pytest xanh |
| S2 | Phase 0 trên TUNE: B0/B1′/B2 + V0p/V1p/V2p parity; Z-tax/Z-orig/Z-pop/Z-cart; MDE; A0 bấm giờ | 0,5 ngày | - [ ] parity = 0 · - [ ] luật dừng · - [ ] MDE · - [ ] lịch lập lại |
| S3 | Phase 1 trên TUNE (prodcopy + DB G6 cho track N); giữ/bỏ bậc; đóng băng tham số + `family.json`. **Commit + history `dang dở`** | 0,5–1 ngày | - [ ] grid · - [ ] 1-SE · - [ ] chuỗi đóng băng |
| S4 | Phase 2 TEST một lần; latency trong tiến trình. **Commit kết quả + history `dang dở`** | 0,5 ngày | - [ ] ci.json · - [ ] strata · - [ ] latency |
| S5 | Report, mục quyết định, history (hoàn thành) | 0,5 ngày | - [ ] report · - [ ] quyet-dinh · - [ ] history |
| S6 | Trình gate: G1-LLBO(b), G1-open′, B10, [C7], I-3, G7. Viết [D] (hoặc gộp [A]) và cập nhật [B] | 0,5 ngày + chờ | - [ ] đề xuất · - [ ] người dùng chốt |
| S7 | Pha B §5.2. Track O sau PR-A + chốt [D]; track N trong PR-B. PRD trước, rồi engine, test ≥ 80 %, parity HTTP 60/60, e2e latency xen kẽ trước/sau, archive, history, PR vào `release-mvp-v2` | 2–3 ngày | - [ ] PRD · - [ ] engine · - [ ] test · - [ ] gate · - [ ] latency · - [ ] archive |

Mỗi commit ở S1, S3, S4, S5 đều kèm entry `history/` liệt kê file theo `git status`, với `Trạng thái: dang dở` cho tới S5 (AGENTS.md §5). Phần bench (S1–S5) mất khoảng 4–5 ngày công, chưa tính thời gian chờ chốt và lane B2.