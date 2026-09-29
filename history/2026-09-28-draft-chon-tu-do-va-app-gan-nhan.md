# Draft không cần đủ 200 (mỗi slice ≥ 3) và app gán nhãn 0/1/2

- Ngày: 2026-09-28
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu ngày 28/09:
1. **Draft không nhất thiết đủ 200 câu.** Mỗi slice có ít nhất 3 case. Người dùng chọn bao nhiêu case thì lấy bấy nhiêu cho bước tiếp theo, không cần đủ số lượng mới ra gold.
2. **Làm luôn app gán nhãn 0/1/2**, theo `docs/spec/bench/prompts/may2-label-app.md` (việc của máy 2).

Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5. Không lệch PRD: PRD không quy định số câu gold (đã grep `docs/prd/`), nên chỉ đổi config và spec của bench.

## File thay đổi

**Code**
- `src/evaluation/search_bench/config/sbench.yaml` — sửa:
  - `gold.min_per_slice` 10 → **3**;
  - `gold.minimum` 150 → 39 (13 slice × 3);
  - `target` và `slices` ghi chú là mục tiêu tham khảo.
- `src/evaluation/search_bench/gold.py` — sửa:
  - `select_drafts(..., cap=True)`: `cap=False` lấy mọi ý định đã chọn, không cắt theo quota;
  - `render_drafts_report(report, min_per_slice)` thêm cột tối thiểu / đạt;
  - thêm `slices_below_min`.
- `src/evaluation/search_bench/__main__.py` — sửa: `gold drafts` mặc định `cap=False`, không `--fill`; in bảng có tối thiểu; cảnh báo slice dưới 3; bỏ cảnh báo "chưa đủ 200".
- `src/evaluation/search_bench/draft_selection.py` — sửa:
  - `compute(fill=False, cap=False)` mặc định, có `suggested` (câu `--fill` sẽ lấp, chỉ là gợi ý);
  - thêm `slice_status`, `candidates`, thao tác `add`;
  - `alternatives` dùng chung `_unchosen`;
  - thao tác `drop` không còn nói "để --fill lấp".
- `src/evaluation/search_bench/draft_authoring.py` — sửa: `slice_summary` đổi cờ "mỏng" thành "dưới tối thiểu" và "mục tiêu"; bỏ cảnh báo "đủ quota".
- `src/evaluation/search_bench/labeling_core.py` — thêm: lõi gán nhãn, Python thuần:
  - `open_session` (kiểm sha trước khi đọc, chặn file nhãn của người kia);
  - `load_labels`, `progress`, `resume_qid`, `next_unfinished`;
  - `save_label` (LabelRow → `validate_label_against_pool` → `upsert_label`; hạng phòng theo thứ tự pool; bắt lỗi file đang mở);
  - `clear_label`, `header`, `candidate_rows`.
- `src/evaluation/search_bench/streamlit_app.py` — sửa:
  - chế độ "Bộ câu đã chọn" (đổi tên từ "Bộ 200 câu đã chọn") theo luật mới: ô đếm slice đạt, bảng theo slice, mục "➕ Thêm câu chưa chọn" (⭐ gợi ý --fill);
  - chế độ mới "Gán nhãn 0/1/2" (`render_labeling`): chọn người A/B, bảng `data_editor` có cột nhãn / ghi chú, ô hạng phòng cho parent_child, tiến độ, điều hướng, nút "Dùng bản thử fixture gold_small", "Tải lại file".

**Test**
- `src/evaluation/search_bench/tests/test_labeling_core.py` — thêm: 7 test gồm đủ 6 test bắt buộc của may2:
  - gán hết pool_A / pool_B ra đúng `labels_A/B.csv` trừ `labeled_at`;
  - tiếp tục ở câu 3;
  - pool sửa 1 ký tự → chặn;
  - nhãn 2 parent_child thiếu hạng phòng → không lưu;
  - không mở `labels_B.csv` (spy `builtins.open` cộng file canh);
  - `candidate_rows` không lộ cột ẩn.
- `src/evaluation/search_bench/tests/test_streamlit_app.py` — sửa: thêm 2 AppTest cho chế độ gán nhãn (tiến độ / tiếp tục / tick hạng phòng lưu ngay; pool lệch sha bị chặn); đổi nhãn chế độ; 2 test viết câu thay thế chuyển sang slice `named_entity`.
- `src/evaluation/search_bench/tests/test_draft_selection.py` — sửa: test theo luật mới (chỉ câu đã chọn, gợi ý --fill, không cắt quota, thêm / loại).
- `src/evaluation/search_bench/tests/test_draft_authoring.py`, `tests/test_config.py`, `tests/test_gold_cli.py` — sửa: `min_per_slice` 3; `check` mặc định báo "< 3", `--min-per-slice 10` vẫn đúng `expected.json`.

**Tài liệu**
- `docs/spec/bench/search-eval-local-spec.md` — sửa: khối config §1.2; dòng `sb gold drafts` ở Part 5 ghi luật mới.
- `docs/spec/bench/search-eval-checklist.md` — sửa: ghi chú luật mới; ngưỡng `gold check` 10 → 3.
- `docs/spec/bench/README.md` — sửa: 2 mục "Còn phải làm tay" (42 câu --fill thành gợi ý; câu dự phòng không còn cần).
- `docs/spec/bench/prompts/may2-label-app.md` — sửa: ghi đã làm trên `bench/embed-search`, còn những gì.
- `docs/plan/2026-09-23-search-labeling-app.md` — sửa: mục "Bổ sung 28/09 (tối)".
- `history/2026-09-28-draft-chon-tu-do-va-app-gan-nhan.md` — thêm: entry này.

**Sửa sau phản hồi** ("thêm hoặc loại câu rồi áp dụng mà không thấy thay đổi"):
- **Nguyên nhân:** chưa nhập tên người sửa. Callback từ chối ghi, nhưng lỗi chỉ hiện ở đầu trang trong khi người dùng đang cuộn ở dưới. Tái hiện trên bản sao `gold/`: `overrides.tsv` không đổi. Có tên thì thêm và loại đều ghi đúng.
- `streamlit_app.py`: chưa có tên thì các nút "Thêm vào bộ", "Áp dụng", "Áp dụng câu thay thế" bị khoá, kèm nhắc ngay dưới nút. Thông báo kết quả qua `_flash` hiện ở đầu trang, ngay dưới nút vừa bấm, và dạng toast.
- `tests/test_streamlit_app.py`: thêm `test_selection_buttons_need_author_and_show_feedback`.
- `tests/test_draft_authoring.py`: `test_state_on_committed_gold` đối chiếu với `drafts.txt` hiện có thay vì số 200 cứng.
- `src/evaluation/search_bench/gold/drafts.txt`: người dùng đã bấm "Ghi drafts.txt" (16:06), file giờ có 163 dòng theo luật mới.

## Quyết định

**Luật chọn draft**
- Luật mới cho ra **163 câu**: người soát 145, `overrides.tsv` 18. Trong đó `audience_style` có 25 câu vì không còn cắt ở mục tiêu 20.
- 12/13 slice đạt ≥ 3; `out_of_catalog` mới 2 câu nên cần chọn thêm, đã có 8 câu gợi ý ⭐.
- 42 câu `--fill` trước đây giờ chỉ là gợi ý và không tự vào bộ.
- `drafts.txt` chưa ghi lại: đang là bản 200 câu cũ. App hiện diff và nút "Ghi drafts.txt"; người dùng tự quyết khi nào ghi.
- `gold check` mặc định dùng ngưỡng 3 và chỉ xét slice có mặt. Slice cấu hình mà vắng hoàn toàn chỉ bị cảnh báo; giữ cách này vì fixture 7/13 slice phải xanh với N = 1, và `expected.json` là hợp đồng không sửa. Chế độ "Bộ câu đã chọn" và `gold drafts` thì đánh dấu đỏ cả slice 0 câu.

**App gán nhãn**
- Dùng `st.data_editor` (cột nhãn là SelectboxColumn) như may2 gợi ý để thao tác nhanh.
- Mỗi lần sửa gọi callback lưu ngay, rồi dựng bảng mới từ file nhãn (khoá có số phiên bản). Nhờ vậy file là nguồn sự thật duy nhất.
- Nhãn 2 ở parent_child chưa có hạng phòng thì giữ ở trạng thái chờ, ô hạng phòng hiện ra; chọn xong mới lưu.
- Phiên cache theo mtime + size của meta và pool; nút "Tải lại file" xoá cache.

**Giới hạn đã biết**
- AppTest không điều khiển được `data_editor`, nên thao tác sửa bảng được kiểm qua test của lõi (`save_label` / `clear_label`), còn ô hạng phòng kiểm bằng AppTest.
- Không làm phím tắt 0/1/2 (may2 ghi "nếu làm được").

## Kiểm tra

- `pytest evaluation/search_bench/tests`: **256 passed, 10 skipped** (trước đó 245), sau cả phần sửa phản hồi.
- `pyflakes evaluation/search_bench`: sạch, trừ cảnh báo có sẵn về lượt import `authlib.deprecate`.
- `gold drafts --dry-run` (từ `src/`): 163 câu, bảng có cột tối thiểu / đạt, cảnh báo "1 slice dưới 3 câu: out_of_catalog".
- AppTest trên dữ liệu thật, không ghi file:
  - "Bộ câu đã chọn": 163 câu · slice đạt 12/13 · người soát / overrides 145 / 18 · gợi ý --fill 42, kèm báo đỏ `out_of_catalog` (2);
  - "Gán nhãn 0/1/2" hiện hướng dẫn chọn người gán.

## Còn lại / rủi ro

- **Chọn thêm ≥ 1 câu `out_of_catalog`** (app: Bộ câu đã chọn → ➕ Thêm câu chưa chọn), rồi bấm "Ghi drafts.txt".
- **Tiếp theo:** chạy `gold pool` + `gold split` trên `drafts.txt` mới để có pool thật, rồi gán nhãn trong app.
- **Mốc 2 của may2:** gán fixture bằng tay theo `labels_A/B.csv`, rồi `gold kappa` / `merge` phải ra đúng `expected.json` / `merged_expected.csv`. Làm được ngay bằng nút "Dùng bản thử fixture", nhưng cần người thao tác trên trình duyệt.
- **Slice ít câu:** `split --overlap 25` cần tổng số câu > 25, hiện 163 nên ổn. Slice chỉ 3 câu thì số liệu theo slice sẽ dao động mạnh; đây là đánh đổi người dùng đã chọn.
- **Chưa commit.**
