# Đủ 200 draft gold: đồng bộ snapshot 2026-09-23, bổ sung 72 draft, sửa theo phản biện

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, data, docs

## Mục tiêu

Người dùng đã gán thêm 11 nhãn trong app để lấp các slice thiếu, rồi yêu cầu "lấy về và tự bổ sung thêm tương tự nếu thiếu". Trước đó `gold/drafts.txt` có 187/200.

Phục vụ FR-SRC-01..04, AC-SRC-01.

## File thay đổi

- Merge `origin/bench/embed-search` (25 commit: snapshot 2026-09-23, `metrics.py`, text builder v2, config test riêng) — 1 conflict ở `docs/spec/bench/search-eval-checklist.md`, giữ tick Role A và ghép ghi chú vocab 2026-09-23 của Người B.
- `src/evaluation/search_bench/gold.py` — sửa `select_drafts(fill=True)`: (1) một dòng bị loại vì lỗi thật hoặc REJECT trong `overrides.tsv` loại cả ý định, kể cả khi còn dòng chưa gán; (2) ở `dest_type`/`out_of_catalog` loại mọi dòng cùng `review_note`; (3) trong ý định, không chọn câu người soát đã đánh `unnatural`.
- `src/evaluation/search_bench/tests/test_gold_drafts.py` — thêm 4 test cho 3 hành vi trên.
- `src/evaluation/search_bench/gold/drafts_raw.tsv` — thêm `c0601`–`c0672` (72 dòng / 24 ý định); sửa `source_refs` `c0601`–`c0615`; thay câu `c0628`–`c0630`.
- `src/evaluation/search_bench/gold/overrides.tsv` — thêm 24 dòng (6 bất đồng lấy nhãn mới nhất; 11 REJECT; 9 NEEDS_EDIT… xem Quyết định), tổng 29.
- `src/evaluation/search_bench/gold/drafts.txt` — 187 → **200 dòng**.
- `src/evaluation/search_bench/gold/drafts_manifest.json` — `raw_cases` 672, `draft_quota` theo file, thêm 2 mục `supplements` ghi luật chọn; bỏ `draft_shortfall_vs_target`.
- `docs/spec/bench/gold-draft-prompt.md`, `docs/spec/bench/search-eval-local-spec.md`, `docs/spec/bench/search-eval-checklist.md` — cập nhật trạng thái, luật `--fill`, tick ô bổ sung ứng viên.
- `history/2026-09-24-gold-200-bo-sung-draft-va-phan-bien.md` — thêm: entry này.

Ngoài repo (gitignored): dựng lại `bench_out/search/data/` bằng `sb catalog build --allow-id-drift` + `sb catalog vocab` trên snapshot 2026-09-23.

## Quyết định

- **Đồng bộ snapshot trước khi sinh draft.** Snapshot 2026-09-23 có sha256 `518a9aa7…` **trùng** `catalog_sha256` của đợt sinh 600 draft gốc. Toàn bộ "grounding hỏng" báo cáo sáng 24/09 (Buôn Ma Thuột / Pleiku / Tuy Hòa / Điện Biên mất khách sạn, Phong Nha biến mất, Quy Nhơn hết combo) là do bench đang chạy snapshot cũ 2026-09-21 — trên catalog mới cả 6 điểm đến đều có hàng: Pleiku 30 khách sạn, Buôn Ma Thuột 37, Tuy Hòa 30, Điện Biên 35, Phong Nha 9, Quy Nhơn 6 combo. `--allow-id-drift` an toàn vì draft và filter ghi **khoá** amenity, không ghi id.
- **6 bất đồng `khoi` ↔ `QAnh`** (c0173, c0187, c0247, c0257, c0259, c0261): lấy nhãn mới nhất theo nguyên tắc người dùng đã chốt; ghi vào `overrides.tsv` thay vì sửa kho nhãn.
- **Đợt bổ sung 1 (`c0601`–`c0636`)**: pool 600 đã cạn ý định ở 4 slice. Luật chọn ghi trong manifest; mọi cụm off-taxonomy đã kiểm không chứa alias seed.
- **Phản biện độc lập** (workflow 3 agent, chỉ đọc) trên 46 dòng tự lấp + 10 dòng `out_of_catalog`, rồi tôi kiểm lại từng đề xuất trên dữ liệu trước khi áp:
  - Lật 3 KEEP của QAnh ở `out_of_catalog` bằng bằng chứng cứng: `c0571`/`c0572` (SU `dc84e117` "Lotuz Hanoi Hostel - Ha Giang Loop Office"), `c0581` (60 khách sạn Côn Đảo thuộc tỉnh "Bà Rịa - Vũng Tàu"; SU "Velar Hotel Con Dao - Vung Tau"). Cùng lỗi với `c0589` do `--fill` chọn ("Workshop Nhà Hải Dương Học Nhí").
  - REJECT các lựa chọn của `--fill`: `c0430` (wifi 91% Đà Nẵng), `c0199` (trùng khoá pool với `c0631`), `c0412` (sân hiên lần 3), `c0532`/`c0520` (tập kết quả trùng), `c0484`/`c0511` (filter khớp 65 / 52).
  - NEEDS_EDIT: `c0205`, `c0208` (khoá `raw:` nằm trong `amenity_single`) → spa / giặt ủi; `c0202` (không hút thuốc 79%) → thang máy; `c0301` bỏ tên phòng dán từ catalog; `c0403`, `c0409` (ý định lặp lần 2–3) → đưa đón sân bay / quầy bar; `c0517` "0.5 triệu" → "500 nghìn".
  - Sửa lỗi của chính tôi ở đợt 1: ref của câu "khách sạn…" trỏ vào căn hộ/homestay (c0604, c0610, c0613), một ref thực ra có "Chỗ đậu xe" (c0601 — alias seed thiếu "đậu xe"); `c0628` "phòng tắm riêng" gần như chỗ nào cũng có → "chỗ gửi hành lý".
- **Đợt bổ sung 2 (`c0637`–`c0672`)** thay các ý định vừa loại. `out_of_catalog` chỉ nhận điểm đến có 0 lần xuất hiện (bỏ dấu) trong toàn snapshot và 0 trong vocab `destinations`/`provinces`/`products` — phép kiểm này loại Pù Luông, Mai Châu, Lai Châu, Đồng Văn (đều có trong catalog).
- Không tự sửa KEEP của người soát ngoài phạm vi phản biện (`c0241` "không ghi nhận", `c0503`/`c0531` "0.5 triệu") — nêu thành gợi ý.

## Kiểm tra

- `pytest evaluation/search_bench/tests` (từ `src/`, sau merge): **170 passed, 10 skipped**.
- `sb catalog build --allow-id-drift`: 3.183 search unit / 11.387 bản ghi / 38 điểm đến; `sha256` snapshot = `518a9aa7820c9ded…` = `drafts_manifest.catalog_sha256`.
- `sb gold drafts --fill`: **200/200, 13/13 slice đúng quota**; 29 ghi đè (KEEP 9 · NEEDS_EDIT 9 · REJECT 11); lấp 42 ý định.
- `parse_drafts` đọc lại `gold/drafts.txt`: 200 draft, q001..q200.
- Trong `drafts.txt` không còn dòng nào chứa "Hà Giang", "Vũng Tàu", "Hải Dương", "bồn tắm", "phòng tắm riêng", "hồ bơi view đẹp" từ các case đã loại; 10 `out_of_catalog` là 10 điểm đến khác nhau.
- Đề xuất của phản biện được kiểm lại trên dữ liệu trước khi áp: 10 ref thay thế đều là khách sạn không có tiện ích bị phủ định và không có chuỗi đồng nghĩa; 8 cụm NEEDS_EDIT map đúng một khoá seed (hoặc không khoá nào với off-taxonomy / multi_constraint); 4 filter mới khớp 16–26 sản phẩm.
- Không chạy `validate_contract.py` / `db/verify.sql`: không đổi OpenAPI, mock, schema hay seed.

## Còn lại / rủi ro

- **42 dòng do `--fill` lấp chưa có người rà** — đã qua phản biện máy, nhưng ô "soát tay chọn 200" chỉ nên tick sau khi người soát xem 42 dòng này (in bằng `sb gold drafts --fill --dry-run`). App gán nhãn phải khởi động lại mới thấy 72 draft mới (`load_cases` được cache).
- Alias seed thiếu "đậu xe", "mát-xa", "xông khô", "quán rượu": 80 search unit có chỗ đậu xe và 44 có spa bị matcher bỏ sót. Ảnh hưởng nhãn `amenity_negation` (người gán pool phải cho 0 những property đó). Thêm alias là việc của Data team vì làm đổi `amenity_ids`.
- Gợi ý cho KEEP của người soát (không tự sửa): `c0241` còn "không ghi nhận" (QAnh đã sửa dạng này ở c0247); `c0503`, `c0531` dùng "0.5 triệu".
- `c0409` sau NEEDS_EDIT vẫn trỏ ref là du thuyền; `c0526` ref là căn hộ — `source_refs` không xuất ra `drafts.txt` nên không ảnh hưởng pool, chỉ là gợi ý cho người rà.
- `out_of_catalog` `c0585` Cà Mau: 2 tuyến bay ghi "Cần Thơ" nhưng URL là Cà Mau (CAH); nếu Data sửa nhãn thì dòng này có hit — kiểm lại khi có snapshot mới.
