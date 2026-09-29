# `sb gold drafts`: nhãn của app soát draft → gold/drafts.txt

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

App Streamlit soát draft chỉ ghi nhãn `KEEP / REJECT / NEEDS_EDIT` vào `bench_out/search/labels/labels.jsonl` và xuất CSV; nó **không** tạo `gold/drafts.txt` — file mà `sb gold pool` cần, với định dạng `query \t slice [\t filter_json] [\t expected_no_result]` của spec Part 5. Thiếu bước này thì công sức gán nhãn không đi tiếp được. Người dùng yêu cầu làm script xuất.

Phục vụ FR-SRC-01..04, AC-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/gold.py` — thêm: `read_draft_cases`, `intent_key`, `resolve_decisions`, `select_drafts`, `write_drafts`, `render_drafts_report`; hằng `DRAFT_RAW_COLUMNS`, `PHRASINGS_PER_INTENT`, `PER_ROW_INTENT_SLICES`.
- `src/evaluation/search_bench/__main__.py` — thêm: lệnh `sb gold drafts` (`--labels`, `--raw`, `--out`, `--dry-run`).
- `src/evaluation/search_bench/tests/test_gold_drafts.py` — thêm: 6 test (gom ý định, bất đồng annotator, NEEDS_EDIT, cắt quota, từ chối query trùng, round-trip qua `parse_drafts`).
- `src/evaluation/search_bench/gold/drafts.txt` — thêm: 143 dòng sinh từ nhãn hiện có.
- `docs/spec/bench/search-eval-local-spec.md` — sửa: bảng Part 5 thêm dòng `sb gold drafts`.
- `docs/spec/bench/search-eval-checklist.md` — sửa: ô "chọn 200" ghi rõ dùng app + `sb gold drafts`, kèm kết quả 24/09.
- `history/2026-09-24-sb-gold-drafts-xuat-drafts-txt.md` — thêm: entry này.

Ngoài repo (gitignored, không commit): gộp annotator `kh` / `khoi2` → `khoi` trong `bench_out/search/labels/labels.jsonl` theo chốt của người dùng; đã sao lưu `labels.backup-2026-09-24.jsonl` trước khi đổi.

## Quyết định

- **Quy tắc ý định**: 3 dòng liền nhau của `drafts_raw.tsv` là 3 cách nói của cùng một ý định (gold-draft-prompt rule 10) → chỉ giữ một, ưu tiên `case_id` nhỏ nhất (dạng câu gốc, không có tiền tố `tìm`, không có mệnh đề đuôi). **Ngoại lệ `out_of_catalog`**: 3 dòng là 3 taxonomy khác nhau (resort / vé tham quan / combo) nên mỗi dòng là một ý định — đây là kết luận của vòng phân tích 24/09, ngược với cách nhóm mặc định.
- Nhờ quy tắc này, 43 lần KEEP trùng ý định của người soát **không cần gán lại**: script tự gộp. Người soát không phải quay lại REJECT chúng bằng tay.
- **Bất đồng giữa annotator** (khác verdict trên cùng case) → không chọn, in ra để người dùng xử lý. Không tự chọn đa số, không tự lấy người gán sau: spec Part 5 chỉ định nghĩa luật hoà cho nhãn 2/1/0, không có luật cho vòng lọc draft.
- **Gộp `kh` / `khoi2` → `khoi`** theo chốt của người dùng, giữ nguyên `updated_at` nên "bản mới nhất thắng" tự cho kết quả cuối. Chọn đổi tên trong kho thay vì thêm alias trong code để chính app cũng hiện nhất quán. Đã backup trước.
- Cắt quota theo `gold.slices` của `config/sbench.yaml`, lấy theo thứ tự `case_id`, báo phần thừa thay vì tự ý bỏ im lặng.
- Không tự loại các ý định chết vì catalog trôi (Buôn Ma Thuột, Quy Nhơn combo, Vũng Tàu…): đó là quyết định của người soát trong app, script không được thay người quyết định giữ/loại.
- Đặt logic trong `gold.py` + một subcommand, không viết script rời: `gold.py` đã là nơi của Part 5, nhờ vậy có test và chạy lại được nhiều lần khi gán thêm.

## Kiểm tra

- `pytest evaluation/search_bench/tests/test_gold_drafts.py`: **6 passed**.
- `pytest evaluation/search_bench/tests` (từ `src/`): **135 passed, 9 skipped** (129 trước đó + 6 mới).
- `sb gold drafts` trên kho nhãn thật (532 event, 506/600 case đã gán, 2 annotator, 0 bất đồng sau khi gộp tên):
  - chọn **143/200** ý định; loại 315 (duplicate 164 · fabricated_entity 114 · other 31 · unnatural 6); gộp 43 cách nói trùng ý định; `audience_style` thừa 5 (bỏ c0153, c0154, c0159, c0160, c0165).
  - Thiếu theo slice: multi_constraint 15 (53 case chưa gán), no_diacritics 9, dest_type 6, named_entity 6, amenity_single 5, amenity_negation 5, amenity_offtaxonomy 5, out_of_catalog 5, parent_child 1.
- Round-trip: `parse_drafts` đọc lại `gold/drafts.txt` ra **143 draft, qid q001..q143**, 5 draft có filter, 5 draft `expected_no_result=true` — không lỗi định dạng, không trùng `(query, slice)`.
- Không chạy `validate_contract.py` / `db/verify.sql`: không đổi OpenAPI, mock, schema hay seed.

## Còn lại / rủi ro

- `gold/drafts.txt` hiện **143/200**, chưa đủ để khoá `gold_v1`. Cần gán nốt 94 case chưa chạm (multi_constraint 53, no_diacritics 15, amenity_single 13, out_of_catalog 13) và sinh bù draft cho các slice đã hết ý định (`amenity_negation`, `amenity_offtaxonomy` mỗi slice còn 5/10). Chạy lại `sb gold drafts` sau mỗi đợt gán.
- `amenity_negation` và `amenity_offtaxonomy` không thể đủ quota bằng pool hiện có — phụ thuộc đợt sinh bù `c0601`–`c0630` của Người A.
- Quy tắc "3 dòng liền nhau = 1 ý định" đúng với đợt sinh 23/09; nếu đợt bù không giữ đúng cấu trúc bộ ba liền mạch thì `intent_key` gom sai. Khi append draft mới phải giữ đúng dạng, hoặc đổi sang khoá ý định ghi tường minh trong `drafts_raw.tsv`.
- Script không kiểm grounding: câu đã chết vì catalog trôi vẫn được xuất nếu người soát KEEP. Danh sách phải loại đã gửi người dùng, chưa được áp vào dữ liệu.
- Kho nhãn nằm trong `bench_out/` (gitignored) và chỉ có trên máy này — nếu đổi máy phải mang theo `labels.jsonl`, nếu không `sb gold drafts` không tái lập được `drafts.txt`.
