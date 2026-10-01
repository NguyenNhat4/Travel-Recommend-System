# Kế hoạch 3 ngày (30/09 → 02/10): từ "gán nhãn xong" đến bảng bench search + recsys

- Phục vụ: **FR-SRC-01..04**, **FR-REC-01..04**, **AC-SRC-01**, **AC-REC-01/02**, **NFR-PERF-01/03** (`docs/prd/requirements.md`); `docs/prd/test-plan.md` §2.4–2.5.
- Là bản chi tiết cho Day 3–5 của `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` (M1, M2, M5 rút gọn), viết ngày 30/09 sau khi A và B gán xong nhãn gold. Người dùng chốt các quyết định ở §1 ngày 30/09.
- Người đọc: A1, A2 (gold + search bench), C (engine), B (recsys harness). Tick `[x]` và ghi số ngay cạnh mục.

## 0. Đích cuối 02/10

1. **Bảng search** trên gold: Recall@10 / nDCG@10 / MRR@10 / judged@10 / zero-result theo slice cho dense-only (B0), hybrid, hybrid + normalize (cổng APP — đúng `SearchProducts` production).
2. **≥ 2 model embedding** trên cùng gold: Cohere `embed-multilingual-v3.0` (B0) và `intfloat/multilingual-e5-base` (E2.e5); bge-m3 nếu còn CPU.
3. **Bảng recsys** trên DB seed: random / most-popular (cửa sổ) / most-popular-in-destination / engine, LLBO + temporal.

## 1. Quyết định đã chốt (30/09)

| # | Quyết định | Căn cứ |
|---|---|---|
| D1 | c0463 ("ve may bay SG di DN") **retire trước tag** `gold_v1`, lý do `pool_miss` (sản phẩm đúng `5d210e58` không nằm trong pool depth 15) | dựng lại pool làm hỏng sha của 3.999 nhãn; spec Part 11 mở rộng cho `pool_miss` |
| D2 | Hybrid / hybrid + normalize đo bằng **`SearchProducts` thật** (cổng APP, `arms.md` §2) | S2.* của spec dùng `hybrid()` Weaviate, production không dùng |
| D3 | **Số trước, cổng rút gọn**: Part 12 (promote / ack / status / `@ref` / regression) làm sau 02/10; số tuần này từ `sb run --arm` + `sb compare` | 3 ngày không đủ cho cả bộ máy cổng lẫn recsys |
| D4 | Merge `origin/bench/recsys-harness` vào `bench/embed-search` (merge khô sạch) | một nhánh cho cả hai bench |
| D5 | Recsys chạy trên **seed 2026-09-21 đang có** (Postgres 5432: 2.897 unit, 7.131 event; Weaviate app local `Product` 2.897 object) — không seed lại DB dùng chung; search bench trên snapshot 2026-09-23 (3.183 unit). Báo cáo ghi rõ hai snapshot | TRP-release dùng chung DB |
| D6 | Quy ước gold còn thiếu do A1 + A2 chốt tối 30/09 (địa danh con; đúng nơi sai loại → 1; phủ định tối đa 1; tiện ích ngoài danh mục có ghi → 2 / không ghi → 1; cross_vertical; "KS" = mọi `hotel_property`) | audit 30/09: 12 cặp lệch 2 bậc + 5 câu không có nhãn 2 đều là thiếu quy ước / gán nhầm |

## 2. Việc của người (A1, A2) — đóng gold, tag `gold_v1`

Lệnh từ `src/`: `sb` = `../.venv-sbench/Scripts/python -m evaluation.search_bench` (PowerShell đặt `$env:PYTHONUTF8="1"`).

**Tối 30/09**
- [ ] Chốt quy ước D6 vào `docs/spec/bench/gold-guide.md` (kèm ngày, lý do, slice ảnh hưởng); nếu chốt luật tiện ích ngoài danh mục thì rà lại c0259, c0268.
- [ ] Sửa trong app: c0256 (`8a545d40`, `21cb0fce`, `139eec1e` → 2), c0265 (`330f3c0a`, `3ea9f4c4`, `5dc78ee3` → 2) — A; c0503 (`5977c2d5`, `057196df` → 2) — B.

**Sáng 01/10**
- [ ] `sb gold merge gold/labels/labels_A.csv gold/labels/labels_B.csv` → 3.359 cặp, 12 `needs_discussion`.
- [ ] Sửa `merged.csv` bằng trình soạn văn bản (không Excel): 12 dòng lệch 2 bậc + ghi đè c0457 (4 KS Hà Nội → 2), c0565 theo luật cross_vertical; ghi người quyết + lý do vào `note`.
- [ ] Import thử ra thư mục tạm: `sb gold import merged.csv -o <tmp>/gold.jsonl` → `sb gold check <tmp>/gold.jsonl`.
- [ ] Import thật → `sb gold retire c0463 --reason "pool_miss: 5d210e58 (vé HCM–Đà Nẵng) ngoài pool depth 15"` → `sb gold check` xanh (131 câu active, 13 slice ≥ 3).
- [ ] Commit `gold/gold.jsonl`, `gold/labels/*`, `gold/changelog.yaml`, history → `git tag gold_v1`. **Không** `import --overwrite` sau retire.

**01/10 chiều → 02/10 — gán hole** (`holes.labeler: A`; Claude không gán máy cho hole)
- [ ] Sau mỗi `sb run`: `sb gold holes --arms <arm,…> --tag <đợt> [--split]` → mở `gold/holes/<gv>__<đợt>/pool_meta.json` trong app → gán → `sb gold holes import <thư mục>` → `sb gold check` → `sb gold verify-append gold_vN` → commit → `git tag gold_vN+1` → `sb rescore`.
- Ước lượng **đo thật 30/09** trên gold xem trước (scratchpad, chưa tag): B0 **43 cặp / 8 câu** (multi_constraint) · 4 arm APP (dense, dense_nocut, hybrid, hybrid_norm) **194 / 55 câu** · E2.e5 **575 / 118 câu** (+15 ooc tự gán) · hợp **733 cặp / 119 câu** ≈ 4 giờ gán. Đề xuất: đợt 1 = B0 + APP (~230 cặp, ~1,5 h, `--tag D4a`) → `gold_v2`; đợt 2 = E2.e5 (`--split` chia A1/A2, `--tag D4b`) → `gold_v3`. Không đọc Δ của e5 trước khi judged@10 ≥ 0,80.

## 3. Công cụ (Claude) — trạng thái cuối 30/09

| # | Nội dung | Trạng thái |
|---|---|---|
| P1 | `gold retire`, `gold verify-append`, `changelog.yaml`, version gold theo tag git | ✔ (`history/2026-09-30-gold-retire-verify-append-changelog.md`) |
| P2 | `sb run --arm …`, `sb compare A B`, `by_slice` có zero-result / constraint_precision | ✔ (`history/2026-09-30-search-bench-runner-run-compare.md`) |
| P3 | e5-base local (`embed/local_hf.py`, transformers + torch), arm `E2.e5`, collection `Products__T3_R__e5_base` 3.183 object | ✔ (`history/2026-09-30-search-bench-e5-local-embedder.md`) |
| P4 | `gold holes`, `gold holes import`, `sb rescore`, kết quả theo gold_version | ✔ (`history/2026-09-30-search-bench-holes-rescore.md`) |
| P5 | Cổng APP: `app_adapter.py`, `ProductBench`, 6 arm `APP.*`, `sb app-load` | ✔ (`history/2026-09-30-search-bench-app-gate.md`); parity `APP.dense_nocut` = B0 10/10 câu trên fixture |
| P6 | Recsys: merge nhánh (`dc9a22c`), 2 baseline most-popular, 5 arm × 2 split trên seed 09-21, `recsys-offline-eval.md` §4.4; mode eval bỏ cap (`engine`) + `engine_prod` | ✔ 30/09 (`history/2026-09-30-recsys-baselines-most-popular.md`, `…-recsys-mode-eval-bo-cap.md`) — engine (eval) thắng rõ mpd: Recall@20 0,851 vs 0,635, NDCG@10 0,524 vs 0,389 (M5 đạt); list production (cap) 0,591 / 0,460 |
| P7 | `sb sanity` (kiểm tra cứng 12.2 chạy rời) | ✔ 30/09 (`history/2026-09-30-search-bench-sanity-va-xem-truoc-gold.md`); `stages.yaml` + máy trạng thái cổng: sau 02/10 |
| Dự phòng | bge-m3 (`E2.bge`); recsys với vector e5 | nếu còn giờ |

## 4. Lịch chạy

| Ngày | Chạy | Kết quả |
|---|---|---|
| 01/10 sáng | A: tag `gold_v1`. Claude: `sb run --arm B0 --arm E2.e5` → kiểm nhất quán B0 (mục 5) → `sb gold holes --arms B0,E2.e5 --tag D4a` | A gán hole đợt 1 |
| 01/10 chiều | `holes import` → `gold_v2` → `sb rescore` → `sb compare B0 E2.e5` | **Bảng 2 model** theo slice |
| 02/10 sáng | `sb run --arm APP.dense --arm APP.dense_nocut --arm APP.hybrid --arm APP.hybrid_nocut --arm APP.hybrid_norm --arm APP.hybrid_norm_nocut` → holes đợt 2 → `gold_v3` → rescore | Bảng dense / hybrid / hybrid_norm (có và không cutoff) |
| 02/10 chiều | P6 recsys 4 arm × 2 split; viết `docs/spec/bench/search-eval-results.md`, cập nhật `recsys-offline-eval.md`; log Day 3–5 lịch 10 ngày | **Bảng search + recsys + so 2 model**; quyết định model (M3) là của người |

Cutoff mốc cho arm APP: 0,62 (`.env`, contract §2.4); báo thêm 0,52 (mặc định trong code từ commit `dbc22c1`, không có history). Không sửa config production.

## 5. Kiểm chứng

- Mỗi thay đổi code: `pytest evaluation/search_bench/tests -q -p no:cacheprovider` xanh (30/09: **327 passed**, 11 skipped); recsys: `python -m pytest -q src/evaluation/recsys_bench/tests` từ gốc repo bằng `.venv` (30 passed).
- B0: **đã đo 30/09 trên gold xem trước** — 122/122 câu không filter có top-10 trùng `rank_dense` 1..10 của `pool.csv`; judged@10 0,967; 0 lượt Cohere mới. Chạy lại trên `gold_v1` sau khi tag (`sb run --arm B0`).
- `sb sanity --arms B0,E2.e5,APP.dense`: **PASS 30/09** — cohere-v3 gap query/document 0,184, e5 0,075 (cần > 0,005); cache cos ≥ 0,9999; ba collection đủ 3.183. Chạy lại trước mỗi lần đọc số.
- E2.e5: token p99 236 / max 301 < 512 (đã đo); collection 3.183 object.
- APP: `ProductBench` 3.183 object, textHash khớp (đã đo); `APP.dense_nocut` = B0 (đã đo 10/10 fixture và từng số trên 131 câu xem trước); `APP.hybrid` với `lexical_k=0` cùng tập R với `APP.dense` (chưa đo).
- Recsys: `doctor` OK với `WEAVIATE_URL=http://127.0.0.1:8080` ghi đè (`.env` đang trỏ Cloud); **đã đo 30/09**: thứ tự random ≪ most-popular < most-popular-in-destination đúng ở LLBO và temporal; engine availability 100 %, coverage 20,5 %.
- Mọi số in kèm judged@10 và n theo slice; slice 3–5 câu ghi "ồn"; multi_constraint của arm APP báo riêng; không đọc Δ của arm có judged@10 < 0,80.

## 6. Rủi ro

- Sau `gold_v1` không sửa nhãn được nữa → quy ước D6 phải chốt tối 30/09.
- Hole dồn vào A1/A2 (2–3 giờ trong 01–02/10).
- `.env` trỏ Weaviate Cloud + DB tunnel: không chạy `embed_products` / `make index-vectors` với `.env` như vậy (xoá vector cloud); harness và adapter ghi đè URL local qua biến môi trường.
- ANN nhiễu ở `ProductBench` (hnsw); trần Recall@10 thấp (trung vị 18 sản phẩm liên quan/câu → trần ≈ 0,64) → đọc nDCG@10 là chính.
- 15 câu `abbrev_typo` đã dùng để viết `QueryNormalizer` → số normalize trên slice này là số đo trong mẫu (caveat bắt buộc).
- Chưa có bộ máy cổng Part 12: bảng 02/10 chưa qua promote / state; làm tuần sau.
