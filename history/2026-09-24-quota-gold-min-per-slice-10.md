# Nâng quota hai slice gold nhỏ nhất lên 10 cho khớp min_per_slice

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, data, docs

## Mục tiêu

`gold.min_per_slice: 10` mâu thuẫn với `gold.slices`, nơi `amenity_negation` và `amenity_offtaxonomy` chỉ có 5. Cổng ngày 4 của `docs/spec/bench/search-eval-checklist.md` ("`sb gold check` xanh … không slice < 10 query") chắc chắn trượt với bộ quota này. Người dùng chốt nâng hai slice nhỏ lên 10 và bù từ hai slice lớn nhất để tổng vẫn 200.

Phục vụ FR-SRC-01..04, AC-SRC-01; độ đo theo `docs/prd/test-plan.md` §2.5.

## File thay đổi

- `src/evaluation/search_bench/config/sbench.yaml` — sửa: khối `gold.slices` — `dest_type` 30→25, `audience_style` 25→20, `amenity_negation` 5→10, `amenity_offtaxonomy` 5→10; comment dòng `slices:` ghi bất biến "tổng = target, mỗi mục ≥ min_per_slice".
- `docs/spec/bench/search-eval-local-spec.md` — sửa: bản sao khối `gold:` ở §1.2 (giống config từng byte); sample `results.json` ở §1.4 đổi `"n": 30` → `"n": 25` cho `dest_type`.
- `docs/spec/bench/gold-draft-prompt.md` — sửa: tiêu đề 600 → 630; bảng quota (`dest_type` 90|25, `audience_style` 75|20, `amenity_negation` 30|10, `amenity_offtaxonomy` 30|10, tổng 630|200); header cột thành "Ứng viên cần sinh (≥ 3 × mục tiêu)"; thêm rule 10 về ý định phân biệt; thêm đoạn "Trạng thái 24/09/2026" ghi rõ còn thiếu 30 dòng; siết hai dòng QA về near-duplicate; sửa link spec sang tên chữ thường.
- `src/evaluation/search_bench/gold/drafts_manifest.json` — sửa: `target_quota_after_user_filter` theo quota mới; thêm `target_quota_revised_on`, `target_quota_revision_note`, `draft_shortfall_vs_target`; thêm 2 dòng `notes`.
- `docs/spec/bench/search-eval-checklist.md` — sửa: cổng ngày 4 ghi `gold.min_per_slice` = 10 thay vì literal trơ; thêm một ô `[ ]` ở Ngày 1 — A (bổ sung 30 ứng viên `c0601`–`c0630`); thêm một dòng vào bảng Buffer cho tình huống slice không đủ ý định phân biệt.
- `src/evaluation/search_bench/tests/test_config.py` — thêm: `test_gold_slice_quota_matches_target_and_min`.
- `history/2026-09-24-quota-gold-min-per-slice-10.md` — thêm: entry này.

## Quyết định

- Người dùng chốt ngày 24/09/2026: `amenity_negation` 5 → 10, `amenity_offtaxonomy` 5 → 10, `dest_type` 30 → 25, `audience_style` 25 → 20. Tổng vẫn 200, `min_per_slice` vẫn 10, vẫn 13 slice. Spec §1.7 mục 1 cấm agent tự đổi quota — đây là quyết định của người dùng.
- Nâng hai slice nhỏ, **không** hạ `min_per_slice` xuống 5: slice 5 query không đỡ được cổng `judged_at_10_slice_min: 0.70` (lệch một query = 20 điểm phần trăm), và luật regression "slice nào (n ≥ `min_per_slice`) giảm > ngưỡng thì FAIL" sẽ bỏ qua slice đó.
- Bù từ `dest_type` và `audience_style` vì đây là hai slice dư coverage nhất (90 và 75 ứng viên = 30 và 25 ý định, đều nhiều hơn mục tiêu mới). Tổng 200 không đổi nên không phát sinh chi phí embed / pool / gán nhãn.
- Giữ nguyên `target: 200`, `minimum: 150`, `pool_depth: 15`, `overlap_queries: 25`, `kappa_min: 0.6`, `judged_at_10_min: 0.80`, `judged_at_10_slice_min: 0.70`.
- Hai bản của khối `gold:` (`config/sbench.yaml` và spec §1.2) phải giống nhau từng byte; đã kiểm bằng `diff` sau khi sửa.
- Cột "Ứng viên cần sinh" của `gold-draft-prompt.md`: nâng hai slice nhỏ 15 → 30 (tổng 630) nhưng **giữ** 90 và 75 cho hai slice bị cắt. Cột chuyển nghĩa từ "đúng 3× mục tiêu" thành **sàn `≥ 3 × mục tiêu`**; xoá ứng viên cũ sẽ buộc đánh số lại `case_id` mà app gán nhãn đang khoá theo `case_id`. Nhờ vậy `dest_type` và `audience_style` lần đầu có dư ý định để người dùng thật sự được chọn.
- Không chạm `drafts_raw.tsv`; giữ `raw_cases: 600` và toàn bộ `draft_quota` trong manifest vì đó là sự thật về lần sinh 23/09. Chỉ `target_quota_after_user_filter` đổi, kèm `draft_shortfall_vs_target` ghi rõ phần còn thiếu.
- Giữ literal `0,80` / `0,70` ở `arms.md`: hai số này không đổi trong lần này; việc trỏ literal về khoá config nên là một pass tài liệu riêng cho cả 4 chỗ.
- Không phải lệch PRD (AGENTS.md §8): `docs/prd/` không nói gì về kích thước gold, slice hay ngưỡng benchmark (`grep` "gold|slice|600" chỉ ra CSS/JS trong `docs/prd/slides/`); `docs/prd/update/` rỗng → không cần đề xuất.
- Không thêm `Bị thay thế bởi:` vào `history/2026-09-23-sinh-600-search-cases.md`: entry đó vẫn đúng về 600 dòng, grounding và checksum; chỉ một quyết định trong đó ("quota draft bằng ba lần quota cuối") được nới thành "≥ 3×".

## Kiểm tra

- Bất biến quota (đọc `config/sbench.yaml` bằng `yaml.safe_load`): `n_slices 13 | sum 200 | target 200 | minimum 150`, `min 10 | min_per_slice 10`, `violators {}` → **OK**. Trước khi sửa: `min 5`, `violators {amenity_negation: 5, amenity_offtaxonomy: 5}`.
- `diff` khối `gold:` của `config/sbench.yaml` với §1.2 của spec: **IDENTICAL**.
- `json.load` trên `drafts_manifest.json`: OK; tổng `target_quota_after_user_filter` = 200, min = 10; `raw_cases` vẫn 600, `draft_quota.amenity_negation` vẫn 15.
- Bảng quota trong `gold-draft-prompt.md`: 13 dòng, cột ứng viên = 630, cột mục tiêu = 200.
- `pytest evaluation/search_bench/tests` (từ `src/`, `.venv-sbench`): xem entry `history/2026-09-24-sbench-ngay-1-kiem-lai-tren-clone-moi.md` — chạy cùng lượt với các test còn lại, gồm `test_gold_slice_quota_matches_target_and_min`.
- Không chạy `validate_contract.py`: không đổi OpenAPI hay mock. Không chạy `db/verify.sql`: không đổi schema hay seed.
- `sb gold check` chưa tồn tại nên không kiểm được bằng lệnh; `git grep` xác nhận không file `.py` nào đọc `min_per_slice` / `gold.slices` ngoài `gold.py` dùng **khoá** slice (không dùng giá trị), và `config.py` khai `gold: _Open` (`extra="allow"`) nên đổi giá trị không cần sửa model.

## Còn lại / rủi ro

- **Thiếu 30 ứng viên.** `amenity_negation` (`c0241`–`c0255`) và `amenity_offtaxonomy` (`c0256`–`c0270`) mỗi slice chỉ có 5 ý định trong 15 dòng (5 ý định × 3 cách nói: bare / `tìm …` / `…, có lựa chọn nào?`). Chọn 10 query/slice từ pool hiện tại buộc giữ 2 cách nói của cùng một ý định ⇒ `n = 10` nhưng chỉ 5 ý định độc lập: cổng slice xanh nhờ trùng lặp, CI của paired bootstrap hẹp giả, annotator gán lại đúng bộ doc hai lần. Task riêng của Người A: append `c0601`–`c0630` (2 slice × 5 ý định mới × 3 cách nói), không đánh số lại, grounding theo `gold-draft-prompt.md` rule 1/2/3/4/7/9/10; ý định mới phải khác cả destination lẫn amenity so với 5 ý định đang có; `amenity_offtaxonomy` phải dùng amenity thô có trong `vocab.json` nhưng không phải seed alias và tần suất ≥ `catalog.amenity_min_freq`. Đã ghi ở checklist (ô chưa tick), `gold-draft-prompt.md` và `drafts_manifest.json → draft_shortfall_vs_target`.
- Cả 13 slice đều sinh theo dạng (mục tiêu) ý định × 3 cách nói, nên pool 600 dòng chỉ có **200 ý định**: trước lần cắt này người dùng gần như không có quyền chọn ở mức ý định. Sau khi cắt, `dest_type` (30 ý định → chọn 25) và `audience_style` (25 → 20) mới có dư.
- Bất biến quota hiện chỉ được `tests/test_config.py` canh. Khi cài Part 5, `sb gold check` phải kiểm cả `sum(slices) == target` và `min(slices) ≥ min_per_slice` trên config, không chỉ trên `gold.jsonl`.
- `"n": 25` trong sample `results.json` chỉ là minh hoạ: lúc chạy, `n` là số query **active** của slice và có thể lệch quota sau `sb gold retire` / `gold holes` (Part 11).
- Hai bất nhất khác, **không** xử lý ở đây: `arms.md` còn literal `0,80` / `0,70` thay vì trỏ `gold.judged_at_10_min` / `judged_at_10_slice_min`; ví dụ `out_of_catalog` "resort ở Sapa" trong `arms.md` và spec không còn đúng vì catalog đã có Sa Pa (xem entry ngày 2 của Người B).
