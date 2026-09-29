# Viết lại split gold cho hai người gán A/B theo bộ 132 câu đã chốt

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng đã chốt bộ draft (`gold/drafts.txt`, 132 câu, 13 slice, mỗi slice ≥ 3 câu) và yêu cầu:
1. Viết lại phần split cho hai người gán A và B.
2. Chạy split để A và B gán nhãn.

Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5. Không lệch PRD: `docs/prd/` không nói về overlap, κ hay câu chung (đã grep), nên chỉ đổi code và spec của bench.

Split cũ được thiết kế cho 200 câu. Chạy trên 124/132 câu đã có pool thử (3.143 dòng thật), nó có ba chỗ yếu:
- `out_of_catalog` không có câu chung nào, nên κ bỏ trống slice này;
- câu riêng chia theo số câu, không theo số cặp: A 1.923 cặp, B 1.870 cặp;
- hai file có cùng thứ tự câu, nên hai người gán cùng một câu chung ở cùng thời điểm.

## File thay đổi

**Split**
- `src/evaluation/search_bench/gold.py` — sửa:
  - `overlap_quota`: số nguyên; slice có ≥ 2 câu có ≥ 1 câu chung khi `overlap` ≥ số slice đó; phần còn lại theo largest remainder (hoà → tên slice).
  - `split_pool` viết lại, cùng chữ ký và giá trị trả về, qua các helper mới:
    - `_pick_shared`: mẫu hệ thống theo cỡ pool trong từng slice, mỗi slice một luồng RNG;
    - `_assign_private`: cân theo số cặp, mỗi slice và tổng lệch ≤ 1 câu, rồi đổi chéo A↔B trong cùng slice;
    - `_rotation`, `_queue`: mỗi slice một khối liền; B bắt đầu từ slice ở khoảng giữa; trong khối, câu riêng xáo riêng từng người, câu chung đặt cách đều.
  - Thêm `split_report`, gồm cờ `apart`.
  - Giữ nguyên cách xáo ứng viên từng người.
- `src/evaluation/search_bench/__main__.py` — sửa `gold split`:
  - mặc định **không in qid câu chung**; thêm cờ `--show-shared`;
  - in thêm số câu / cặp chung, lệch số cặp, câu chung theo slice, slice bắt đầu của A và B;
  - cảnh báo khi không lệch được nửa vòng.

**Map `case_id` (lỗi phát hiện khi chạy pool)**
- `src/evaluation/search_bench/gold.py` — thêm `local_only_edits`; lỗi của `case_ids_for` chỉ cách sửa.
- `src/evaluation/search_bench/__main__.py` — sửa: `gold drafts` cảnh báo khi có câu sửa chỉ nằm trong kho nhãn local.
- `src/evaluation/search_bench/draft_selection.py` — sửa: thêm thao tác `copy_local` vào `decision_rows`.
- `src/evaluation/search_bench/streamlit_app.py` — sửa: chế độ "Bộ câu đã chọn" hiện cảnh báo, kèm nút "Chép vào overrides.tsv" (`_copy_local_edits`, cần tên người sửa).
- `src/evaluation/search_bench/gold/overrides.tsv` — sửa: thêm dòng `c0276 NEEDS_EDIT`, chép nguyên quyết định của QAnh (app soát câu, 24/09) từ kho nhãn local.

**Pool và split thật (chạy sau khi người dùng thay khoá Cohere)**
- `src/evaluation/search_bench/gold/pool.csv`, `pool.build.json` — thêm: `sb gold pool` (B0, depth 15, qid = `case_id`).
- `src/evaluation/search_bench/gold/pool_A.csv`, `pool_B.csv`, `pool_meta.json` — thêm: `sb gold split` (overlap 25, seed 42).

**Bộ draft đã chốt (người dùng làm qua app ngày 29/09)**
- `src/evaluation/search_bench/gold/drafts.txt` — sửa: 132 câu.
- `src/evaluation/search_bench/gold/overrides.tsv` — sửa: các dòng REJECT / NEEDS_EDIT / KEEP của người dùng.

**Test**
- `src/evaluation/search_bench/tests/test_gold.py` — sửa: thêm `FINAL_132`, `_size`, `_synthetic_rows(sizes=…)`, hằng golden, và các test:
  - `test_overlap_quota_floor_every_slice`;
  - `test_split_balances_pairs`;
  - `test_split_queue_order` (có kiểm hai câu chung không liền nhau qua ranh giới khối);
  - `test_split_order_does_not_reveal_shared`;
  - `test_split_golden_output`;
  - `test_split_report_flags_when_order_cannot_separate`;
  - `test_split_shared_inclusion_uniform`.

  Mọi assert cũ giữ nguyên.
- `src/evaluation/search_bench/tests/test_gold_cli.py` — thêm `test_split_cli_hides_shared_qids_by_default`.
- `src/evaluation/search_bench/tests/test_gold_drafts.py` — thêm 3 test: câu chỉ có ở kho local, khác biệt chỉ ở chữ hoa / khoảng trắng, `copy_local`.
- `src/evaluation/search_bench/tests/test_streamlit_app.py` — thêm `test_selection_copies_local_only_edit_to_overrides`.

**Tài liệu**
- `docs/spec/bench/search-eval-local-spec.md` — sửa: Part 5, dòng `sb gold split` ghi luật 29/09.
- `docs/spec/bench/gold-guide.md` — sửa: thêm mục "Gán độc lập" (không đoán câu chung, không mở `pool_meta.json` / cột `is_overlap`, không trao đổi từng câu tới khi có κ, `--show-shared` chỉ cho người không gán).
- `docs/spec/bench/search-eval-checklist.md` — sửa:
  - ghi chú 29/09 ở mục chia pool, kèm số liệu thật;
  - Ngày 3 bỏ việc riêng "Gán 25 query chung độc lập", gộp vào "Gán hết pool_X.csv".
- `docs/spec/bench/prompts/may2-label-app.md` — sửa: khối lượng mỗi người ≈ 78–79 câu / ≈ 2.000 cặp.
- `docs/spec/bench/README.md` — sửa: ghi chú 29/09 và tick mục đóng băng drafts + chạy pool thật.
- `docs/plan/2026-09-28-summary-search-recsys-benchmark.md` — sửa: ~2.000 cặp/người, thêm ghi chú 29/09 ở dòng "200 câu" và mục câu dự phòng để bản tóm tắt không tự mâu thuẫn.
- `history/2026-09-29-split-gold-a-b-theo-132-cau.md` — thêm: entry này.

## Quyết định

**Bug map `case_id`.**
- `sb gold pool --qid case` dừng ở dòng 58 của `drafts.txt` (c0276): câu sửa NEEDS_EDIT chỉ nằm trong kho nhãn local `bench_out/search/labels/labels.jsonl`, không được commit.
- Test `test_case_ids_on_committed_drafts` yêu cầu `drafts.txt` đã commit phải map được chỉ từ file commit. Vì vậy mình chép quyết định vào `overrides.tsv`, không cho `pool` đọc kho local; nếu cho thì máy khác và test sẽ đỏ.
- Cảnh báo, kèm nút chép ở app, ngăn lỗi lặp lại.
- `drafts.txt` không đổi: lựa chọn tính lại vẫn trùng từng dòng.

**Thiết kế split** (workflow `gold-split-design`: 3 phương án dựng prototype và đo trên pool mô phỏng, 2 giám khảo).
- Hai giám khảo đồng ý về quota có sàn và cân theo số cặp. Chỉ bất đồng ở thứ tự câu: dồn 25 câu chung thành khối đầu file để chạy κ sớm, hay rải đều.
- **Chọn rải đều.** Khối đầu làm hai người gán cùng một câu cùng lúc và biết đâu là câu bị chấm; κ khi đó chỉ đo phần đầu phiên, lúc người gán chưa quen (giám khảo đo độ lệch −0,049 trong mô hình học + trôi).
- Checklist vốn đã chấp nhận gán lại 25 câu chung nếu κ < 0,6, nên bỏ mốc κ sớm là chấp nhận được.
- Lấy từ phương án kỹ thuật: quota số nguyên, thay cho `Fraction`. Khớp bản `Fraction` trên 3.000 bộ đầu vào ngẫu nhiên.

**Sửa sau review đối kháng** (workflow `gold-split-review`: 4 người review, mỗi phát hiện có 2 người cố bác bỏ; 15 phát hiện đều được xác nhận).
- **[major] Câu chung lộ qua thứ tự `case_id`.** Câu riêng giữ thứ tự tăng, câu chung chen vào lệch thứ tự. Nhìn qid trong app đoán đúng câu chung với độ chính xác 0,80, trong khi đoán mò là 0,32. Nay câu riêng xáo trong khối; kiểm lại trên pool mô phỏng: A 0,32, B 0,44 so với nền 0,33.
- **[major] `gold split` in toàn bộ qid câu chung.** Nay mặc định không in; thêm `--show-shared`.
- **[major] Cảnh báo câu sửa local chỉ cách sửa không làm được** (`check_rewrite` từ chối câu trùng chính nó). Nay có nút `copy_local`.
- **[minor] Docstring hứa lệch số cặp "≤ 1" và "nhỏ nhất".** Sửa thành "thường ≤ 1, không bảo đảm".
- **[minor] Câu "không gán cùng lúc" in cả khi không đúng.** Chỉ đúng khi không slice nào quá nửa số câu; `split_report.apart` kiểm điều này và CLI cảnh báo khi không đạt.
- **[minor] Checklist và plan còn mâu thuẫn.** Đã sửa.
- **[minor] Test còn yếu.** Thêm test golden (bắt RNG phụ thuộc `hash()`), test hai câu chung không liền nhau qua ranh giới khối, test giới hạn quota có ràng buộc thật, test `casefold`.

**Giữ nguyên:**
- `gold.overlap_queries` = 25 và `kappa_min` = 0,6. Mô phỏng cho SD của κ̂ ≈ 0,045–0,053 ở 25 câu chung; tăng lên 30 chỉ giảm ≤ 0,008.
- Hợp đồng `gold_schema.py`, fixture `gold_small/`, `write_split`, kappa / merge, `labeling_core.py`.

**Không bảo đảm được "mù" tuyệt đối.** Hợp đồng đóng băng vẫn ghi `is_overlap` trong file pool và `overlap_qids` trong `pool_meta.json`. `gold-guide.md` yêu cầu người gán không mở những chỗ đó; app không hiện chúng.

## Kiểm tra

- **Chọn thiết kế:** bản thống kê trước review trùng từng byte với prototype được hai giám khảo chạy lại (seed 42: sha A `81d41556930b`, B `53faa18cf477`). Sau đó bổ sung bước xáo câu riêng.
- **Pool mô phỏng** (124 câu / 3.143 dòng), seed 42, chạy bằng CLI vào thư mục tạm:
  - A 74 câu / 1.889 cặp, B 75 câu / 1.890 cặp;
  - 25 câu chung / 636 cặp, mọi slice ≥ 1 (`out_of_catalog` 1/2);
  - A bắt đầu ở `dest_type`, B ở `named_entity`.
  - `labeling_core.open_session` mở cả hai file, tiếp tục đúng từ câu đầu; `load_pool_set` đọc được.
- **Dữ liệu tổng hợp đúng dáng 132 câu** (golden test): A 79 câu / 1.420 cặp, B 78 câu / 1.420 cặp. Output trùng nhau với `PYTHONHASHSEED` 0 / 1 / random.
- **Test đột biến** trên test mới, cả 4 đột biến đều bị bắt:
  - bỏ bước xáo câu riêng → test chống lộ và golden đỏ;
  - bỏ chặn câu chung liền nhau qua ranh giới khối → `test_split_queue_order` đỏ;
  - chọn câu chung bằng `hash()` → golden đỏ.
- `pytest evaluation/search_bench/tests`: **268 passed, 10 skipped** (trước 257).
- `pyflakes` các file đổi: sạch.

**Chạy thật.**
- Lần 1: `sb gold pool` báo 429 ("Trial key … limited to 1000 API calls / month"). 121/132 câu có vector truy vấn trong cache, 11 câu mới hoặc vừa sửa thì thiếu. Không ghi file nào.
- Người dùng thay khoá. Lần 2, từ `src/`:
  - `sb gold pool`: `gold/pool.csv` **132 câu / 3.359 dòng** (6–30 ứng viên, p50 26; both 526 · dense 1.428 · lexical 1.405). Embed mới 11 câu, cache 121. 0 câu rỗng.
  - `pool.build.json`: sha `drafts.txt` và sha pool khớp, 132 qid không trùng.
  - `sb gold split` (overlap 25, seed 42):
    - `pool_A.csv` **78 câu / 1.999 cặp**, `pool_B.csv` **79 câu / 2.000 cặp**, lệch −1 cặp;
    - **25 câu chung / 640 cặp**: dest_type 2/12, audience_style 2/11, amenity_single 2/13, amenity_multi 2/10, amenity_negation 1/5, amenity_offtaxonomy 1/5, parent_child 2/11, named_entity 3/18, no_diacritics 2/12, abbrev_typo 3/13, multi_constraint 2/9, cross_vertical 2/10, out_of_catalog 1/3;
    - A bắt đầu ở `dest_type`, B ở `named_entity`. CLI không in qid câu chung.
- Kiểm sau split:
  - sha trong `pool_meta.json` khớp `drafts.txt`, `pool_A.csv`, `pool_B.csv`; không có CRLF;
  - mọi câu có người gán; A∩B = đúng tập câu chung; `load_pool_set` cho 640 cặp chung;
  - `labeling_core.open_session` mở được cả A và B;
  - thứ tự không lộ câu chung: tỷ lệ câu chung trong nhóm lệch thứ tự A 0,27, B 0,36, so với nền 0,32;
  - chưa có `gold/labels/`.
- `pytest evaluation/search_bench/tests` với pool thật đã có trong `gold/`: **268 passed, 10 skipped**.

## Còn lại / rủi ro

- **Gán nhãn:** A gán `pool_A.csv`, B gán `pool_B.csv` trong app (`streamlit_app.py`, chế độ "Gán nhãn 0/1/2"), theo `gold-guide.md`, gồm cả mục "Gán độc lập". Nhãn ghi ra `gold/labels/labels_<X>.csv`.
- **Sau khi gán xong:** `sb gold kappa gold/labels/labels_A.csv gold/labels/labels_B.csv` (κ linear ≥ 0,6) → `merge` → sửa các dòng `needs_discussion` → `import` → `check` → `git tag gold_v1`.
- **Không split lại** sau khi đã có `gold/labels/*.csv` (`--force` làm lệch sha). Không mở file pool bằng Excel rồi lưu lại.
- **Nhật ký phiên làm việc 29/09** có qid câu chung của lần chạy mô phỏng (124 câu), có thể trùng một phần với câu chung thật. Người gán không nên đọc log đó.
- Chưa push.
