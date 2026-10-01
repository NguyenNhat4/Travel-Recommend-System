# Đặc tả thuật toán cho bảng so sánh recsys — `algos_v1.yaml`

- Phục vụ: **FR-REC-01, FR-REC-02, FR-REC-04** (`docs/prd/requirements.md` §1.3), NFR-PERF-01; `docs/prd/test-plan.md` §2.5; handbook
  §12. Bổ sung cho `docs/plan/2026-10-01-plan-day4-5.md` §2.2 và checklist §5.2 của `docs/plan/2026-10-01-chia-task-day4-search-rec.md`
  (R3–R5); mục đích: bỏ blocker đặc tả cho `cooc_trip`, `star_blend` và chốt tham số mặc định của `ease`, `itemknn`, `rp3beta`,
  `ials`, `bpr`.
- **Mốc đối chiếu v5 (chốt 01/10):** report `src/evaluation/reports/eval-2026-10-01-recsys-bench-v5-asof20260924.md`, split đóng băng
  `src/evaluation/recsys_bench/frozen/split-{llbo,temporal}-asof20260924.json` (1.016 / 98 khách), `configHash b0aee886 / 81d16abd`,
  `ENGINE_RULES_VERSION 2026-10-02-trip-ended` (`profile.py`). Mọi đẳng thức "= engine" trong file này so với run
  `bench_out/recsys/runs/2026-10-01-{llbo,temporal}-v5` (`per_user.jsonl` có `ids` của `engine` và `engine_nommr`).
- Nguồn gốc công thức: tài liệu nội bộ `TRAINING_FREE_RECSYS.md` §2.2 (STAR blend cho V-OTA) và `serve_bench.py` (`build_neighbors`,
  `serve`, `ease`) — **hai file này không có trong repo**; công thức được chốt **tại đây**, chỗ nào hai nguồn để ngỏ hoặc lệch nhau thì
  bản này thắng. Tham chiếu `EMBEDDING_AND_ENGINES §6.4` → đọc `domain/recommendation/profile.py::explain`; bảng `app.item_neighbors`
  không tồn tại trong DDL (`db/vota_schema.sql`).
- Tuần này **không tune**: mọi tham số dưới đây là mặc định để đo; grid tuần sau ghi ở §7. Code thực thi: `src/evaluation/recsys_bench/models/`
  (R3–R6), chạy bằng `python -m src.evaluation.recsys_bench run --algos src/evaluation/recsys_bench/algos_v1.yaml …` (xem
  `docs/spec/bench/recsys-offline-eval.md` §1).

## Errata 01/10 — đối chiếu code engine sau M6 (áp dụng cho toàn file)

Bản nháp đầu viết trước khi M6 (FR-REC-02) được áp dụng và trước khi đo pool của engine trên v5. Các điểm sau **thắng** phần thân
file nếu còn mâu thuẫn:

| # | Nháp đầu ghi | Code thực tế (01/10) | Áp dụng trong file này |
|---|---|---|---|
| E1 | Trip mở = "tuổi ≤ 60 ngày"; yaml `open_trip_max_age_days: 60` | `trip_is_open(age, ends_on, today)` (`profile.py:48-53`): có `usingDate` → mở khi `max(usingDate) ≥ as_of.date()`; không có → tuổi ≤ `ACTIVE_TRIP_MAX_AGE_DAYS` = **14** | §0.3 dùng `trip_is_open`; bỏ hằng khỏi yaml (luật nằm trong `configHash`) |
| E2 | `w_s = w_type · min(n_s, 3) · 2^(−Δt/h)` | `build_profile` giữ **3 event cũ nhất** mỗi (trip, unit), **mỗi event** một hệ số `W_TYPE·2^(−d_e/30)` (`profile.py:80-90`); nhánh long gộp hai tầng (`trip.vec` chuẩn hoá, rồi `2^(−age_t/365)`, `:103-104`) | §0.3 lấy S và `w_e` **từ `build_profile`**, không tự tính lại |
| E3 | Funnel lọc "destination chuyến mở ∥ 2 destination lịch sử", "≠ anh em cùng cha với seed" | Mask engine (`use_cases.py:131-142`): có trip mở → destination trip mở ∧ taxonomy ∉ đã mua ∧ recommendable/available (mask rỗng → bỏ destination); **không trip mở → không lọc destination**; luôn bỏ `bought_units`; không loại anh em | §0.4 funnel = mask engine (quyết định người dùng 01/10) |
| E4 | "List đánh giá k = 20 không MMR, không cap (đã chốt Day 3)" | Arm `engine` (eval) của v5 **vẫn chạy MMR λ 0,7**, chỉ bỏ cap (`engine.py:93-95`); mốc không-MMR là `engine_nommr[:20]` | §0.4 thêm knob `rerank ∈ {none, mmr}`; chạy **cả hai** |
| E5 | Chấm điểm trên toàn mask | Engine chấm **pool** = ANN top-200 quanh `u_short` (và `u_long` khi có trip mở) ∪ 50 món phổ biến trong mask (`use_cases.py:144-168`); pool bị cắt ở 4/1.016 khách LLBO nhưng **76/98** khách temporal | §0.4 thêm knob `pool ∈ {engine, mask}`: gate = `engine`, bảng = `mask` |
| E6 | `sem(x)` "lấy từ engine" | Engine không xuất điểm semantic theo món (`score_candidates` trả điểm trộn, `profile.py:112-116`); `sem = E_full[c] @ u` (dot float32, bằng cos khi vector đơn vị) | §2.1 |
| E7 | `score = 0,6·[…] + 0,25·pop_D + 0,15·cos(u_long, v)` với hằng ghi trong yaml | Hằng là `W_SHORT / W_POP / W_LONG` của `profile.py:19`, đọc lúc chạy để `--override` và `configHash` đi theo | §2.2; bỏ `weights:` khỏi yaml |
| E8 | X_train "khách test u chỉ event < as_of_u, khách khác toàn bộ" | Đúng, nhưng phải dựng từ `kept` (event đã lọc của `_prepared`), **không** từ `Split.train_purchases` (chứa cả purchase bị giấu, `splits.py:192`) | §0.2 |
| E9 | Seed có `add_to_cart` thiếu gid vào ma trận user; purchase thiếu gid "giữ trong ma trận user × item" | `filter_events` đã **bỏ** 94 purchase thiếu gid khỏi `kept` (`events.py`); chỉ purchase mới có gid trên seed hiện tại → B (trip × item) **thực tế chỉ có purchase** | §0.1, §0.2, §6 |
| E10 | `CosineRecommender(K=50)` rồi `.similarity` | `.similarity` chứa chính item → dùng `K = k + 1` rồi bỏ đường chéo | §3 |
| E11 | iALS `c = 1 + α·r` | `implicit` nhân dữ liệu với α: `c = α·r = 40` | §6.1 |
| E12 | BPR negative "đều trên toàn bộ item" | `implicit` lấy negative theo phân bố popularity (nnz); `bpr_dest` không có cài đặt ở nhánh research → `status: not_run` | §6.2 |

## 0. Quy ước chung cho mọi scorer

### 0.1 Không gian id và ánh xạ event → item

- Item id trong mọi ma trận = **search unit id** (cùng id với collection `Product` và với ứng viên của engine). Event ở mức phòng/chuyến
  được map lên search unit cha bằng **đúng hàm engine đang dùng**: `UnitIndex.resolve(product_id)` (`application/ports/unit_index.py`,
  gọi ở `use_cases.py:113`). Không viết hàm map thứ hai.
- Bỏ event có `product_id` không tồn tại trong catalog (≈ 2 % orphan theo MOCK_DATA_SPEC) và — như engine (`use_cases.py:119`) — event
  có unit **chưa có vector** trong kho (`has_vector`, run v5 `vectorsMissing 0` nên không bỏ gì); log số bỏ (tái dùng
  `EventFilterReport` của `events.py`).
- Event thiếu `event_group_id` (≈ 3 %): engine gom thành trip `_solo_<productId>` (`use_cases.py:123`). Trong ma trận: **bỏ khỏi
  trip × item** (không gom được chuyến), **giữ** trong user × item và trong tập seed S (khi trip solo đó mở hoặc ở nhánh long). Trên
  seed hiện tại chỉ `purchase` có gid và 94 purchase thiếu gid đã bị `filter_events` loại khỏi `kept`, nên phần "thiếu gid" còn lại chỉ
  là view/cart. Log số.

### 0.2 Dữ liệu train theo split — chống rò rỉ

- `X_train` = tập event dùng để fit, dựng từ **`kept`** (mọi event đã lọc trong `__main__._prepared`), không từ `Split.train_purchases`
  (chứa cả purchase bị giấu). Leave-last-booking-out: với mỗi khách test u chỉ lấy event có `timestamp < as_of_u` (`as_of_u` =
  timestamp purchase bị giấu — chính là `split.train_by_user[u]`); khách không thuộc test (1 purchase) lấy toàn bộ. Temporal split:
  event có `timestamp < T` (khách cold đã bị loại khỏi test, vẫn vào X_train). **Một ma trận toàn cục mỗi split**, tính trên toàn
  `split.targets` (không theo `--limit-users`).
- Mọi bảng item-item / factor **tính lại trên `X_train` của từng split**; không dùng bảng nào của production khi đánh giá.
  **Assert trong harness (`models/data.assert_no_leak`, chạy trong `run`, ném `LeakageError`):** mọi event của khách test u trong
  X_train có `ts < as_of_u`, và hàng trip của target không chứa ô target.
- **Caveat LLBO (ghi cạnh mọi bảng LLBO):** vì `as_of_u` khác nhau theo khách, ma trận toàn cục chứa event của **khách khác** xảy ra sau
  `as_of_u`; `pop_D` của engine thì cắt tại `as_of_u` (`OfflineEngine.reader_at`). Không có target nào rò rỉ, nhưng hai nguồn không
  đối xứng về thời gian; kết luận so scorer lấy từ **temporal** (quy ước B10), LLBO là bảng tham chiếu.
- Hai cách gom hàng:
  - **`rows = trip`** (`(cdpUserId, eventGroupId)`) cho `cooc_trip`, `itemknn`, `ease`, `rp3beta` — đo "đi cùng chuyến", đúng mục tiêu
    cross-vertical (tính theo user sẽ trộn các chuyến cách nhau nhiều năm).
  - **`rows = user`** cho `ials`, `bpr` — MF cần user factor để chấm.
- Giá trị ô: **nhị phân**, ô = 1 nếu hàng có `purchase` **hoặc** `add_to_cart` item đó; `product_view` và `search` **không** vào ma
  trận (cờ `include_views: false`, đổi tuần sau). Trùng nhiều event cùng item trong một hàng vẫn = 1. Trên seed hiện tại B = purchase-only
  (E9); `add_to_cart` chỉ có tác dụng ở rows = user. Fit log ghi `cellsByEvent`.

### 0.3 Seed và trọng số — dùng chung cho mọi scorer item-item

Để bảng so sánh *scorer* chứ không so cách lấy lịch sử, mọi arm dùng **đúng tập seed và trọng số engine dùng**, lấy từ
`build_profile(resolved, E_full, taxonomy, destination, today=as_of.date())` của `profile.py` (harness `models/seeds.py`):

```
resolved = event của user có ts < as_of, map §0.1 (bỏ orphan, bỏ unit chưa có vector), unit = chỉ số toàn cục
profile  = build_profile(...)          # mỗi (trip, unit) giữ 3 event CŨ NHẤT; trip mở theo trip_is_open (E1)
Nhánh mở   (profile.active_trip ≠ None; strategy ∈ {cross_vertical, recent_activity, cold_start_content}):
    S = active_trip.events ; w_e = W_TYPE[e] · 2^(−d_e / H_SHORT_DAYS)                      # wt = 1
Nhánh long (active_trip = None; strategy ∈ {long_term, dormant}):
    S = ∪ mọi trip.events ; w_e = 2^(−age_t / H_LONG_DAYS) · W_TYPE[e] · 2^(−d_e / H_SHORT_DAYS)   # dạng `explain`, profile.py:149-151
Không trip nào (strategy popular): S = ∅ → collab = 0 → xếp theo pop_D (§0.4)
W_TYPE = purchase 1,0 · add_to_cart 0,5 · product_view 0,2 · search 0,1 (profile.py:11) ; H_SHORT 30 · H_LONG 365
```

- Nhánh long dùng dạng `explain` (không chia ‖trip.vec‖) — **khác** cách engine dựng `u_long` (có chuẩn hoá từng trip rồi mới cộng,
  `profile.py:103-104`). Chọn dạng này vì `because[]` của engine dùng nó; `star_blend` với a = 1 không phụ thuộc `w_e` (hệ số
  `(1 − a) = 0`) nên đẳng thức a = 1 ⇒ engine không bị ảnh hưởng. Ghi rõ khi đọc `collab` ở khách `long_term`.
- Seed mà item không có trong ma trận (chưa từng đồng xuất hiện) vẫn nằm trong S và vẫn tính vào mẫu số — thiếu bằng chứng = 0, không bỏ seed.
- `search` không có `product_id` trên seed nên không bao giờ vào S (engine cũng bỏ).
- Suy giảm theo **vị trí** 0,7 của STAR **không** dùng cho seed là lịch sử user; chỉ dành cho seed là list có thứ tự từ `/search` /
  chatbot (ngoài phạm vi tuần này).

### 0.4 Funnel, pool, rerank và phá hoà

Hai chế độ của CLI (`--mode`), hai knob của funnel (`common.funnel` trong yaml, ghi đè bằng `--funnel-pool`, `--funnel-rerank`; mọi
giá trị vào `algosHash`):

- **`funnel`**: ứng viên C = **mask engine** (E3; `models/funnel.engine_mask` mirror `use_cases.py:131-142`): có trip mở → `destination`
  trip mở ∧ taxonomy ∉ vertical đã mua trong chuyến ∧ `is_recommendable` ∧ `available` (mask rỗng → bỏ điều kiện destination); không
  trip mở → chỉ `is_recommendable` ∧ `available`; luôn bỏ `bought_units`. **`raw`**: C = `mask(only_recommendable=True)` (recommendable
  ∧ available) trừ `bought_units` — cùng mẫu số với random / popular / Coverage / Gini.
- **`pool ∈ {engine, mask}`** (E5): `engine` = tái tạo đúng pool của engine (ANN top-`candidate_k` 200 quanh `u_short`, thêm `u_long` khi
  có trip mở, cùng lời gọi `near_vector(q, allowed_ids(mask), 200, with_vectors=True)`; ∪ top-`popular_k` 50 theo `pop_D` trong mask;
  giữ **thứ tự chèn**; sort ổn định theo điểm; cắt 200) — dùng cho **gate** regression. `mask` = chấm toàn C bằng vector numpy — dùng
  cho **bảng so scorer** (công bằng giữa scorer; khác engine ở 4/1.016 khách LLBO và 76/98 khách temporal, báo `poolTruncatedUsers`
  và `eqEngineTop20` cạnh bảng).
- **`rerank ∈ {none, mmr}`** (E4): `none` = khoá sắp xếp `(score giảm dần, pop_D giảm dần, item_id tăng dần)` — "điểm 0 / không có tín
  hiệu → phá hoà theo `pop_D`" nghĩa là đúng khoá này, không có bước riêng; `mmr` = `mmr_select(score, E_full, cand, taxonomy, k,
  max_per_vertical=None)` λ = `MMR_LAMBDA` 0,7 trên `pool_k` = 200 ứng viên đầu (như engine cắt `candidate_k` trước MMR), hoà theo thứ
  tự đưa vào (`profile.py:133`, so `>` chặt). Thứ tự đưa vào MMR: `pool engine` → đúng thứ tự engine (điểm ổn định, hoà theo thứ tự
  chèn ANN → popular) để G1 giữ; `pool mask` → theo khoá `(score↓, pop_D↓, item_id↑)` — scorer có đa số điểm 0 (cooc/ease/knn ở 7k
  event) thì 200 món vào MMR là món phổ biến nhất trong số điểm cao nhất, không phải 200 unit có chỉ số nhỏ nhất. **Chạy cả hai cho
  mọi scorer** (quyết định 01/10): arm `name` (none) và `name+mmr`.
- `pop_D` = `OfflineEngine.popularity_at(as_of).unit_scores(destination)` với `destination` = của trip mở, **None → toàn cục** khi không
  trip mở (đúng `use_cases.py:156`): số lượt mua trong cửa sổ 90 ngày trước `as_of` / max, ∈ [0, 1].
- Cap ≤ 2/vertical chỉ ở list production top-5 (`engine_prod`), không ở list đánh giá k = 20.

## 1. `cooc_trip` — co-occurrence theo chuyến

### 1.1 Xây bảng láng giềng (fit)

```
B ∈ {0,1}^{T × I}        # T = số trip trong X_train, I = số search unit; B[t,i] theo §0.2
n_i   = Σ_t B[t,i]                                   # số trip chứa i
co_ij = Σ_t B[t,i]·B[t,j]      (i ≠ j)               # số trip chứa cả i và j   → C = BᵀB, đặt diag = 0
R_C(i,j) = co_ij / sqrt(n_i · n_j)  ×  co_ij / (co_ij + β)      # cosine × shrinkage
β = 5
```

- `co_ij / sqrt(n_i n_j)` là cosine giữa hai cột nhị phân ∈ [0,1]. Thừa số `co_ij/(co_ij+β)` kéo cặp ít bằng chứng về 0: co = 1 → ×0,167;
  co = 5 → ×0,5; co = 20 → ×0,8. Hệ quả cần biết khi đọc số: ở 7k event phần lớn cặp có co ≤ 2 nên R_C nhỏ (ví dụ co = 2, n_i = 5,
  n_j = 4 → 0,447 × 0,286 = 0,128).
- R_C đối xứng **trước** khi cắt top-K. Cắt: với mỗi hàng i giữ **K = 50** cột j có R_C lớn nhất; hoà → co_ij lớn hơn, rồi item_id nhỏ
  hơn (`np.lexsort((item_id, −co, −R))`). Sau khi cắt, bảng **không** còn đối xứng; tra cứu luôn theo **hàng của seed**: `T[s, x]`.
- Lưu `T` dạng `(I, K)` idx/val (hoặc CSR). Fit log: số trip, số cặp (nnz của C), **tỉ lệ item có ≥ 1 láng giềng**, phân vị của R_C,
  thời gian fit.
- Toàn bộ numpy (`G = BᵀB` float64, I = 3.183 → 81 MB), không cần `implicit`.

### 1.2 Chấm điểm (score)

```
collab(x) = Σ_{s∈S} w_s · T[s, x]  /  Σ_{s∈S} w_s          ∈ [0,1]
score_cooc(x) = collab(x)
```

- **Gom nhiều item lịch sử = trung bình có trọng số** (không max, không tổng) để điểm nằm trong [0,1] và so được với cosine semantic ở
  §2. `T[s,x] = 0` khi x không nằm trong top-50 của s. S rỗng → collab = 0.
- Ứng viên có `collab = 0` (đa số ở 7k event) xếp sau theo khoá §0.4 → ở `rerank none`, `cooc_trip` ≈ "đồng xuất hiện rồi tới
  popularity"; ghi rõ khi đọc bảng. Cột **`collab_coverage`** = tỉ lệ item top-20 có `collab > 0`.
- `because[]`: `contribution_s(x) = w_s · T[s,x] / Σ w`; câu mẫu "Khách đặt {name_s} thường đặt thêm {name_x}" — **hoãn** trong harness
  (không vào metric), chỉ đặc tả.

### 1.3 Test bắt buộc trước khi vào bảng

1. Toy 4 trip × 3 item tính tay (`B = [[1,1,0],[1,1,1],[1,0,1],[0,1,0]]` → `n = [3,3,2]`, `co_01 = 2, co_02 = 2, co_12 = 1`, β = 5 →
   `R_01 = 0,1905, R_02 = 0,2333, R_12 = 0,0680`): R_C đúng công thức, đối xứng, diag = 0.
2. Hàng không có láng giềng → `collab = 0`, không lỗi.
3. `T` được fit trên `X_train` của split: assert không có `event_group_id` nào chứa purchase bị giấu đóng góp vào `co_ij` qua cặp
   (hidden, j) — hàng `(u, gid_target)` trong B có ô target = 0.

## 2. `star_blend` — semantic + co-occurrence (STAR, tầng retrieval)

### 2.1 Hai vế điểm

```
u        = vector profile của engine cho nhánh hiện tại: active_trip.vec nếu có trip mở, ngược lại u_long  (profile.py:114)
sem(x)   = E_full[x] @ u                               # tự tính (E6); = cos khi vector đơn vị; float32 như engine
collab(x)= như §1.2, cùng S và w_s (§0.3)
```

**Vì sao `sem` lấy theo profile vector, không lấy từng item:** với v đơn vị, `cos(normalise(Σ w_s v_s), v_x) = Σ_s w_s (v_s·v_x) /
‖Σ w_s v_s‖` — tổng theo từng item chia cho một hằng số của user. Cùng thứ hạng, chỉ khác thang; chọn dạng profile để (i) a = 1 trùng
**chính xác** engine đang chạy (khi `pool: engine`, cùng kho vector; chấm toàn mask lệch ở 4/1.016 LLBO, 76/98 temporal — E5), (ii)
giữ P99 (1 phép nhân ma trận).

### 2.2 Trộn và điểm cuối

```
score(x) = W_SHORT · [ a · sem(x) + (1 − a) · collab(x) ]  +  W_POP · pop_D(x)  +  W_LONG · (E_full[x] @ u_long)
a = 0,5 ;  W_SHORT / W_POP / W_LONG = 0,6 / 0,25 / 0,15 đọc từ profile.py:19 lúc chạy (E7)
```

- **a áp cho vế semantic**, (1 − a) cho vế co-occurrence, **cả hai nằm trong ngoặc của `W_SHORT`** — thay "độ tương đồng semantic" của
  engine bằng "độ tương đồng lai" của STAR; `pop_D` và `u_long` giữ nguyên. Đây là `blend_scope: inner` (mặc định). Biến thể `outer`
  — `score = a·score_engine(x) + (1−a)·collab(x)` — chỉ để grid tuần sau. Nhánh không trip mở: `u = u_long` → `W_SHORT·[a·sem +
  (1−a)·collab] + W_POP·pop_D + W_LONG·sem` (đúng engine: `s_short = s_long`).
- **Chuẩn hoá trước khi trộn: không chuẩn hoá theo request.** Cả hai vế đã cùng thang: `sem` ∈ [−1, 1] (thực tế ∈ [0,1] với văn bản
  cùng miền; không clamp), `collab` ∈ [0,1] đã được shrinkage hiệu chỉnh. Không min-max, không z-score — sẽ phá "a = 1 ⇒ engine" và
  làm điểm phụ thuộc tập ứng viên của từng request.
- Hệ quả phải ghi cạnh bảng: ở 7k event `collab = 0` với ~2/3 ứng viên, nên tại a = 0,5 vế semantic bị **chia đôi** so với `pop_D` và
  `u_long` → `star_blend` tuần này sẽ trông "thiên popularity" hơn `content_profile`. Vì vậy bảng có cột **`collab_coverage`** và arm
  **`star_blend_a1`** (a = 1) chạy cùng — nó phải ra **đúng top-20** của `content_profile` ở cùng `pool`/`rerank` (`expect_equal_to`,
  regression bắt buộc; a = 1,0 → `1,0·sem + 0,0·collab == sem` theo IEEE nên đẳng thức là cấu trúc; không đạt thì **không có số nào của
  `star_blend` vào report**).
- MMR λ = 0,7: theo knob `rerank` §0.4 (cả hai); cap ≤ 2/vertical chỉ ở list production.

### 2.3 `because[]` (đặc tả, hoãn cài)

```
contribution_s(x) = W_SHORT · [ a · w_s (v_s·v_x) / Z  +  (1 − a) · w_s T[s,x] / Σ w ]
```

Engine (`profile.py:143-160`) phân rã **theo event**, chỉ giữ phần dương, chuẩn hoá về tổng phần dương, làm tròn 2 chữ số, ngưỡng
hiển thị **0,15 áp lên tỉ phần đã chuẩn hoá**, tối đa 3 — hệ số `W_SHORT` triệt tiêu khi chia tỉ phần nên câu hỏi "trước/sau 0,6"
không còn. Phần `pop_D` và `u_long` không phân rã theo event, như engine.

## 3. `itemknn` — cosine láng giềng, không shrinkage

- Thư viện: `implicit.nearest_neighbours.CosineRecommender(K=k+1)` (E10), `fit(B)` với B = ma trận trip × item §0.2 dạng CSR (implicit
  coi hàng là "user" — truyền trip làm hàng). k = 50.
- Chuẩn hoá: cosine cột nhị phân `co_ij / sqrt(n_i n_j)` — chính là vế đầu của §1.1 **không có** thừa số shrinkage. Lấy `model.similarity`
  (I × I, top-K theo hàng, chứa chính item), bỏ đường chéo → còn đúng k láng giềng.
- Chấm: `score(x) = Σ_s w_s · S[s,x] / Σ_s w_s` — cùng S, w_s, cách gom như §1.2. Không dùng `model.recommend()` (hàng user nhị phân,
  không trọng số, không qua funnel).
- Ý nghĩa trong bảng: `itemknn` = `cooc_trip` với β = 0 → cặp này **là ablation của shrinkage**. Test chéo: `cooc_trip(β=0, top_k=k)`
  tự viết phải ra cùng ma trận với `implicit` (sai số 1e-6; so ở K + 1 ≥ I để tránh biên hoà của heap) — bắt lỗi cài đặt ở cả hai bên.
  `requires: implicit` — thiếu lib thì arm báo lỗi rõ, phần numpy vẫn chạy.

## 4. `ease` — nghiệm đóng item × item

```
G = BᵀB  (dày, float64, I × I = 3.183²)
P = (G + λI)⁻¹
B_ease = −P / diag(P)  (chia theo cột j: B_ij = −P_ij / P_jj), đặt diag(B_ease) = 0
λ = 200
score(x) = Σ_{s∈S} w_s · B_ease[s, x]  /  Σ_s w_s
```

- Rows = trip (§0.2). Trọng số âm **giữ nguyên** (EASE học cả "không đi cùng"); không cắt top-K; không clip.
- λ = 200 là giá trị quen dùng; ở quy mô này `diag(G)` nhỏ (n_i ≤ vài trăm) nên λ ≫ G và `B_ease ≈ G/λ` ngoài đường chéo — tức **EASE
  tuần này xấp xỉ co-occurrence thô chia hằng số**, không giảm lệch phổ biến. Ghi `max(diag G)`, `median(diag G)` vào fit log để tuần
  sau chọn grid λ có căn cứ (§7).
- Chi phí: 3.183² float64 ≈ 81 MB, nghịch đảo ≈ 1–4 s; lưu float32. Item không có tương tác → hàng/cột G = 0 → B = 0, không lỗi.
- Test: toy 3 item khớp công thức đóng (`np.linalg.inv`, 1e-9); `diag(B_ease) = 0`; `B_ease` không phụ thuộc thứ tự hàng của B.

## 5. `rp3beta` — Tier 2, chỉ nếu còn giờ

- `P_ui = B_ui / deg(u)`, `P_iu = B_ui / deg(i)`; `W = (P_iuᵀ P_ui)^α` theo phần tử; `W_ij ← W_ij / deg(j)^β`; giữ top-K = 50 theo hàng;
  diag = 0. Tham số: **α = 1,0, β = 0,6, K = 50** (điểm khởi đầu quen thuộc trong các benchmark baseline của Dacrema; chưa tune). Chấm
  như §1.2. Rows = trip. Numpy thuần.

## 6. `ials` và `bpr` — MF, `implicit`, rows = user

Chung: ma trận U × I nhị phân từ `X_train` ⊆ `kept` (hàng = user, **gồm cả** `add_to_cart` thiếu gid; purchase thiếu gid đã bị lọc —
E9); `factors = 64`; chạy **3 seed** `random_state ∈ {42, 43, 44}` → báo mean ± sd (như `random`, gộp bằng `bench.aggregate`);
`num_threads = 1` + `threadpoolctl.threadpool_limits(1)` để tái lập (BPR của `implicit` chạy hogwild đa luồng là không tái lập). Ghi
phiên bản `implicit` vào `summary.libs`. `requires: implicit`.

### 6.1 `ials` — `implicit.als.AlternatingLeastSquares`

- `factors=64, regularization=0.01, iterations=15, alpha=40, use_gpu=False, calculate_training_loss=False, random_state=seed`.
- Confidence: `implicit` **nhân** dữ liệu với `alpha` → `c = α·r = 40` cho mọi ô có tương tác (E11); dạng `log(1 + r/ε)` chỉ cần khi r
  là đếm — ở đây không áp.
- Chấm: user factor **tính lại tại lúc chấm** từ hàng train của user (`model.recalculate_user(uid, row_u)` — một nửa bước ALS, tất
  định khi cố định item factors), `score(x) = u_f · v_x`. User không có hàng train → `score = 0` → phá hoà §0.4.
- `because[]`: `implicit.explain()` — tuỳ chọn, không bắt buộc tuần này.

### 6.2 `bpr` — `implicit.bpr.BayesianPersonalizedRanking`

- `factors=64, learning_rate=0.01, regularization=0.01, iterations=100, verify_negative_samples=True, random_state=seed`.
- **Negative: toàn cục**, lấy theo phân bố popularity của `implicit` (E12), không có tuỳ chọn theo destination; arm `bpr` ghi rõ
  "negative toàn cục". Negative **trong cùng destination** là arm riêng **`bpr_dest`** (Tier 2): đặc tả để đối chiếu — với mỗi positive
  (u, i⁺), lấy i⁻ đều trong tập item cùng destination với i⁺ mà u chưa tương tác; destination có < 20 item → lùi về toàn cục; cùng
  `factors`, `lr`, `reg`, `iterations`, seed. Nhánh `khoa/recsys-research` **không có** cài đặt → `status: not_run`, tuần sau.
- Chấm: `score(x) = u_f · v_x` với `u_f` lấy từ `model.user_factors` (có cột bias → `factors + 1` = 65 cột, nhân đủ); user không có
  trong train → 0 → phá hoà. Trong LLBO mọi khách test đều có hàng train nên không cold.

## 7. Tổng hợp tham số mặc định tuần này và grid tuần sau

| Arm | Rows | Tham số mặc định (tuần này, không tune) | Grid tuần sau (temporal split) |
|---|---|---|---|
| `content_profile` | — (vector engine) | `W_SHORT/W_POP/W_LONG`, `H_*`, `MMR_LAMBDA` của `profile.py` | qua `run --override` (grid lần 1 §4.13 spec recsys) |
| `cooc_trip` | trip | β = 5, K = 50, purchase ∨ add_to_cart, gom = trung bình có trọng số | β ∈ {2, 5, 10}; K ∈ {20, 50}; `include_views` |
| `star_blend` | trip (collab) + vector engine | a = 0,5, `blend_scope = inner`, không chuẩn hoá theo request; kèm `star_blend_a1` | a ∈ {1; 0,8; 0,6; 0,5}; `blend_scope ∈ {inner, outer}` |
| `itemknn` | trip | `CosineRecommender(K = k+1)`, k = 50, không shrink | k ∈ {20, 50, 100} |
| `ease` | trip | λ = 200, float64, giữ âm | λ ∈ {20, 50, 100, 200, 500} (chọn theo `diag G` đã log) |
| `rp3beta` | trip | α = 1,0, β = 0,6, K = 50 | β ∈ {0,3; 0,6; 0,9} |
| `ials` | user | 64 factor, reg 0,01, 15 iter, α = 40, 3 seed, `recalculate_user` | α ∈ {10, 40}; factor ∈ {32, 64} |
| `bpr` | user | 64 factor, lr 0,01, reg 0,01, 100 iter, negative toàn cục, 3 seed, 1 luồng | `bpr_dest` nếu có cài đặt |

Mọi arm: cùng S, w_e (§0.3), cùng funnel / pool / rerank (§0.4), cùng split, k = 20; `configHash` (engine) và `algosHash` (yaml đã giải
`inherit` + knob funnel + mode + phiên bản lib) in đầu file kết quả. Biến thể `content_no_decay` của plan R5 **không** là scorer riêng:
chạy `run --override H_SHORT_DAYS=1000000 --override H_LONG_DAYS=1000000` (đổi `configHash`, không gộp vào run chuẩn).

## 8. Khung `algos_v1.yaml` (`src/evaluation/recsys_bench/algos_v1.yaml`)

```yaml
version: 1
common:
  matrix: {cell: binary, events: [purchase, add_to_cart], include_views: false}
  funnel: {k: 20, pool: mask, rerank: [none, mmr], pool_k: 200, popular_k: 50, tiebreak: [score, pop_D, item_id]}
  # Không lặp hằng engine (W_TYPE, H_*, N, W_SHORT…): chúng nằm trong profile.py và configHash.

algos:
  content_profile: {scorer: content, tier: 1}
  cooc_trip:       {scorer: cooc_trip, tier: 1, beta: 5, top_k: 50}
  star_blend:      {scorer: star_blend, tier: 1, beta: 5, top_k: 50, a: 0.5, blend_scope: inner}
  star_blend_a1:   {inherit: star_blend, a: 1.0, expect_equal_to: content_profile}   # regression (§2.2)
  itemknn:         {scorer: itemknn, tier: 1, k: 50, requires: implicit}
  ease:            {scorer: ease, tier: 1, lam: 200}
  rp3beta:         {scorer: rp3beta, tier: 2, alpha: 1.0, beta: 0.6, top_k: 50}
  ials:            {scorer: ials, tier: 1, factors: 64, regularization: 0.01, iterations: 15, alpha: 40,
                    seeds: [42, 43, 44], requires: implicit}
  bpr:             {scorer: bpr, tier: 1, factors: 64, learning_rate: 0.01, regularization: 0.01, iterations: 100,
                    negatives: global, seeds: [42, 43, 44], requires: implicit}
  bpr_dest:        {inherit: bpr, negatives: same_destination, min_dest_items: 20, tier: 2, status: not_run}
# estimate (giây fit / giây full run) điền sau smoke --limit-users 50.
```

## 9. Checklist nghiệm thu trước khi bảng Day 5 được tin

- [x] **G1:** `content_profile+mmr` với `--funnel-pool engine` ra **đúng top-20** của arm `engine` cho 100 % khách test, cả hai split, so
      với run v5 `2026-10-01-{llbo,temporal}-v5` (cùng `vectors weaviate`, `frozenSha256`, `configHash b0aee886`) — lệnh `regress`.
      *(01/10: run `2026-10-01-{llbo,temporal}-gate`, `algosHash d0d38a58`: **1016/1016** và **98/98** khớp thứ tự.)*
- [x] **G2:** `content_profile` (`rerank none`, `pool engine`) ≡ `engine_nommr[:20]` — *(01/10: 1016/1016 và 98/98 khớp cả theo thứ tự,
      không cần bỏ qua hoà.)*
- [x] `star_blend_a1` ≡ `content_profile` 100 % khách ở cùng pool/rerank (`expect_equal_to` trong `run`) — *(01/10: 1016/1016, 98/98;
      test fixture khớp ở cả 4 tổ hợp pool × rerank.)*
- [x] `cooc_trip(β=0)` ≡ `itemknn` (ma trận láng giềng khớp 1e-6, K + 1 ≥ I) — `tests/test_models_implicit.py`.
- [x] Toy test §1.3, §4 xanh; `diag = 0` ở mọi ma trận item-item — `tests/test_models_itemitem.py`.
- [x] Assert chống rò rỉ §0.2 chạy trong harness (`run`: `models/data.assert_no_leak`, ghi `summary.leakCheck`), và trong test.
- [x] Fit log cho mỗi arm: số hàng, nnz, tỉ lệ item có láng giềng, `max/median diag G` (ease), thời gian fit, phiên bản thư viện, seed —
      `summary.fitLog`, khối "Fit log" của `report`.
- [x] Bảng có cột `Collab cov.` (cooc/star/itemknn/ease/rp3beta), `Fit s`, `Pool cắt` (tỉ lệ khách pool engine bị cắt). `eqEngineTop20`
      đọc bằng `regress` (so `content_profile` pool mask với `engine` cùng run) thay vì cột riêng.
- [x] `algosHash` vào `summary.json`, `merge_run` và header report; không gộp hai run khác `algosHash`.
