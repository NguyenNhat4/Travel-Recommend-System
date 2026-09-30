# Search bench: `sb sanity` (kiểm tra cứng 12.2) và lượt chạy xem trước trên gold chưa tag

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Kế hoạch 3 ngày mục P7 (rút gọn): trước khi có máy trạng thái cổng (Part 12), cần chạy rời được các **kiểm tra cứng**
của spec 12.2 để tin số của B0 / E2.e5 / cổng APP. Đồng thời chạy thử toàn bộ đường (run → holes → sanity) trên một bản
gold **xem trước** dựng trong scratchpad (merge với min(A, B) cho 12 cặp lệch 2 bậc, retire c0463) để ước lượng số hole
cho A1/A2 và kiểm B0 nhất quán với pool — **không** ghi vào `gold/`, số không được trích dẫn. Phục vụ FR-SRC-01..04.

## File thay đổi

- `src/evaluation/search_bench/sanity.py` — thêm: `input_type_vectors_differ`, `cache_recheck`, `collection_counts`,
  `gold_append_ok`, `summary` (PASS | SANITY_FAIL).
- `src/evaluation/search_bench/__main__.py` — sửa: lệnh `sb sanity --arms A,B [--gold] [--n-queries]` (bảng PASS/FAIL,
  exit 1 khi hỏng).
- `src/evaluation/search_bench/tests/test_sanity.py` — thêm: 4 test (FakeEmbedder `ignore_input_type` → FAIL; cache bẩn
  → FAIL; count lệch; gold append với/không tag).
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.3 thêm `sb sanity`; 12.2 ghi lệnh chạy rời và số câu = min(200,
  active).
- `docs/plan/2026-09-30-bench-search-recsys-3-ngay.md` — sửa: mục 5 kiểm chứng ghi số đo 30/09; ước lượng hole cho A.

## Quyết định

- `input_type_vectors_differ` dùng min(200, số câu active) — gold có 131 câu active (spec ghi 200 khi gold còn 200 câu).
- `cache_recheck` embed lại 20 text **không qua cache** (1 lượt Cohere / lần chạy, ~0,0002 $); với e5 là tính lại local.
- `gold_append_ok` bỏ qua (không FAIL) khi chưa có tag `gold_v*`.
- Gold xem trước để trong scratchpad ngoài repo; thư mục hole xem trước cũng vậy. `bench_out/search/runs/preview-0930`
  (gitignore) giữ để đối chiếu, gold_version ghi `fixture:4cb799ce` nên không nhầm với bản tag.

## Kiểm tra

- `pytest evaluation/search_bench/tests -q -p no:cacheprovider`: **327 passed, 11 skipped**.
- `sb sanity --arms B0,E2.e5,APP.dense --gold <preview>` (131 câu): PASS — cohere-v3 gap 0,184, cache cos min 0,99993;
  e5-base gap 0,075, cache cos 1,0; `Products__T3_R__cohere_v3` / `Products__T3_R__e5_base` / `ProductBench` = 3.183.
- Lượt xem trước `--run-id preview-0930` (131 câu active): B0 recall@10 0,501 · ndcg@10 0,732 · judged@10 **0,967** (đúng
  ước lượng); `APP.dense_nocut` trùng B0 từng số; **B0 top-10 trùng `rank_dense` 1..10 của `pool.csv` ở 122/122 câu
  không filter**; E2.e5 judged 0,550 (NEEDS_LABELS); APP.dense (cutoff 0,62) zero-result trong catalog 16,4 %, APP.hybrid
  14,8 %, APP.hybrid_norm 3,9 % (31 câu chuẩn hoá cần embed mới). Số này chỉ để lập kế hoạch — chưa có tag, 12 cặp lệch
  chưa thảo luận.
- `sb gold holes` trên preview: B0 43 cặp / 8 câu (multi_constraint) · E2.e5 575 / 118 câu (+15 ooc tự gán) · 4 arm APP
  (dense, dense_nocut, hybrid, hybrid_norm) 194 / 55 câu · hợp 6 arm **733 cặp / 119 câu**.

## Còn lại / rủi ro

- 733 cặp hole ≈ 4 giờ gán (20 s/cặp): đề xuất A1/A2 gán đợt 1 = B0 + 4 arm APP (~230 cặp, ~1,5 h) rồi đợt 2 = e5
  (575 cặp, `--split` chia hai người); không đọc Δ của e5 trước khi judged@10 ≥ 0,80.
- Máy trạng thái cổng (promote / ack / status / `@ref`) và `stages.yaml` vẫn chưa có; `sb sanity` là phần 12.2 chạy rời.
