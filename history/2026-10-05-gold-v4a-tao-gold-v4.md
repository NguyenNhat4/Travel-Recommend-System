# Tạo gold_v4 (đợt v4a): rubric v4, 2 slice mới, 23 câu, nhãn máy đã duyệt, import xong

- Ngày: 2026-10-05
- Tác giả: tqanh123 / Claude Code
- Nhánh: `feat/gold-v4`
- Trạng thái: hoàn thành — `gold.jsonl` đã có 23 câu gold_v4 (+645 nhãn), `gold check` và `verify-append gold_v3` xanh; người dùng commit và chạy `git tag gold_v4`
- Phạm vi: evaluation, docs (thêm một dòng import ở backend để bench chạy được)
- Phục vụ: FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01, test-plan §2.5
- Thay thế: các mục bị người dùng chốt khác đi trong `history/2026-10-05-ke-hoach-gold-v4a.md` (plan gốc: một rubric gold-guide, hai người gán, Track G trước) — quyết định mới ở `docs/plan/2026-10-05-gold-v4a-mo-rong.md` mục "Quyết định đã chốt"

## Mục tiêu

Người dùng chốt cổng G0 (D1–D12) và yêu cầu phiên này chỉ tập trung tạo gold-v4: rubric v4 cho câu mới (D1), làm Track L (D2), thêm 2 slice (D3), duyệt quy ước #8–#14 (D4), chỉ QAnh gán và vẫn làm trước freeze (D5), cho phép nhãn máy có người duyệt (D6), đổi tên/sửa đầu file đề xuất v4 (D8), `/search` vẫn có vé máy bay (D10), sửa lỗi dữ liệu (D11), bench trước — cập nhật PRD sau (D12).

## File thay đổi

- `src/evaluation/search_bench/gold_schema.py` — sửa: nối `taxonomy_collision`, `flight_direction` vào **cuối** `SLICES` (giữ luồng RNG của `split`).
- `src/evaluation/search_bench/config/sbench.yaml` — sửa: quota `taxonomy_collision: 5`, `flight_direction: 6`; `target` 200 → 211; `minimum` 39 → 45.
- `src/evaluation/search_bench/tests/test_config.py` — sửa: chú thích tổng quota 211.
- `src/evaluation/search_bench/amenities.py` — sửa (D11): `is_not_amenity` bỏ chuỗi "Không có …", "… : no", chuỗi khoảng cách ("… 570 m", "… 1,6 km") và tiện ích "(Tạm thời ngừng hoạt động)" trước khi khớp tiện ích.
- `src/evaluation/search_bench/tests/test_amenities.py` — sửa: test chuỗi phủ định / khoảng cách bị bỏ, chuỗi dương giữ nguyên, `build_vocab` bỏ qua.
- `src/evaluation/search_bench/gold.py` — sửa: `pair_sources`, `provenance_by_source`, `append_gold`; `build_gold(..., sources=None)` (không truyền `sources` thì giống hệt trước).
- `src/evaluation/search_bench/__main__.py` — sửa: `gold import --append [--accept-unreviewed]` (nối câu mới vào cuối gold đã tag, provenance theo nguồn từng nhãn, từ chối nhãn máy chưa duyệt, kiểm `verify_append`, changelog `import_append`); `gold holes --qids / --new-since`; `gold pool` và `gold drafts` đọc `overrides.tsv` cạnh `--raw` (v1 không đổi: `--raw` mặc định nằm ở `gold/`).
- `src/evaluation/search_bench/tests/test_gold_cli.py` — sửa: 6 test `import --append` (thêm câu, qid trùng, thiếu gold, nhãn máy chưa duyệt / duyệt / sửa, cờ loại trừ nhau).
- `src/evaluation/search_bench/holes.py` — sửa: `import_holes(..., sources=None, accept_unreviewed=False)` — nhãn máy chưa duyệt bị từ chối, provenance `holes:<tag>:machine@<version>` cho nhãn máy được duyệt giữ nguyên, stats thêm `machine` / `machine_unreviewed` (không truyền `sources` → như trước). Lý do: D6 "người duyệt" phải áp như nhau cho pool và hole; đợt D4a nhãn máy vào gold mà changelog ghi là "human".
- `src/evaluation/search_bench/tests/test_holes_import_rescore.py` — sửa: test `holes --qids / --new-since`; test `import_holes` với nhãn máy (chưa duyệt → từ chối, duyệt → provenance machine, sửa → người).
- `src/backend/app/application/ports/unit_index.py` — sửa: thêm `from typing import Protocol`. Merge `3a11433` để lại hai class `VectorStorePort` / `CdpClientPort` dùng `Protocol` mà không import → `import src.backend…` lỗi `NameError`, chặn arm APP của bench (và test `test_app_adapter`). Chỉ thêm import, không đổi hành vi.
- `src/evaluation/search_bench/gold/v4a/` — thêm: `drafts.txt`, `drafts_raw.tsv` (23 câu, qid `c0673`–`c0727` bước 3 và `c0730`–`c0733`), `pool.csv` + `pool.build.json` (559 cặp), `pool_A.csv` / `pool_B.csv` / `pool_meta.json` (split `--overlap 0`), `labels/labels_{A,B}.csv` + `labels/provenance_{A,B}.csv` (559 nhãn máy, QAnh đã duyệt).
- `src/evaluation/search_bench/gold/holes/gold_v4__D8a/` — thêm: holes của 23 câu mới từ run `20261005-v4a-holes` (B0, E2.e5, APP.hybrid_norm): 59 cặp cần gán (16 câu) + 27 `auto_ooc`; `labels/labels_A.csv` + `labels/provenance_A.csv` (59 nhãn máy: 47 luật, 12 Claude — QAnh đã duyệt).
- `src/evaluation/search_bench/gold/gold.jsonl` — sửa (chỉ thêm): +23 câu gold_v4 (`import --append`), +559 nhãn pool, +59 nhãn hole + 27 auto_ooc (`holes import`); SHA-256 `721f164d…`.
- `src/evaluation/search_bench/gold/changelog.yaml` — sửa: hai mục `gold_v4` (`import_append`, `holes_import`).
- `src/evaluation/search_bench/gold/v4a/labels/merged.csv` — thêm: 559 cặp sau `gold merge`.
- `docs/spec/bench/search-gold-summary.md` — sửa: hồ sơ gold_v4 (version, nguồn nhãn, phân bố 154 câu, giới hạn: một người duyệt, không κ, hai rubric).
- `docs/spec/bench/gold_v4_bo_sung_va_quy_trinh_gan_nhan.md` → `docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md` — đổi tên (AGENTS.md §7) + sửa: dòng "Phục vụ", khối trạng thái (D1, D5–D8, D12), §1 viết thành giả thuyết bench, §14 đề xuất đổi `SLICES` (header `gold_schema.py` yêu cầu).
- `docs/spec/bench/gold-guide.md` — sửa: mục "Rubric v4" (nhãn 0/1/2, cứng / mềm, thứ tự quyết định), quy ước #8–#14, bảng chính sách 23 câu, một người gán + nhãn máy.
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.2 slice mới, §1.7 #4 (`import --append`), Part 1 (bỏ chuỗi phủ định / khoảng cách), Part 5 (`import --append`, `overrides.tsv` cạnh `--raw`), Part 11 (`holes --qids / --new-since`).
- `docs/plan/2026-10-05-gold-v4a-mo-rong.md` — sửa: mục "Quyết định đã chốt (05/10)" + phần đã thực hiện; trạng thái; đường dẫn đề xuất mới.
- `history/2026-10-05-gold-v4a-tao-gold-v4.md` — entry này.

## Quyết định

- **Rubric v4 chỉ cho câu mới** (D1): gold append-only nên nhãn v3 giữ nguyên; report phải tách khối câu v3 / v4. "Đúng nơi sai loại" = 0 ở câu v4 (v3: 1).
- **23 câu, đếm lại trên dữ liệu đã làm sạch** (cổng của plan): 8 `amenity_negation` (có X + không Y; mỗi câu ≥ 14 đáp án, ≥ 12 bẫy trong catalog), 5 `taxonomy_collision` (Grand World Phú Quốc × 2, VinWonders Nam Hội An vé lẻ, combo bay + KS Đà Lạt, KS Vinpearl Nha Trang), 6 `flight_direction` (3 có hai đầu, 3 chỉ một đầu), 4 `out_of_catalog` (Lạng Sơn, Bạc Liêu, Ba Bể, Tà Xùa — 0 khớp tên / địa chỉ / mô tả / tỉnh).
- **Filter gold:** phủ định = `destination + variant` (không đặt `not`, để pool có bẫy); câu bay = `variant = flight_route` (không lọc destination, để pool có chiều ngược); taxonomy và OOC không filter. Pool đủ mọi tuyến đúng của 6 câu bay.
- **Nhãn máy (D6):** luật tất định `rule:v4a` cho phủ định / bay / OOC (448 cặp) từ dữ kiện catalog; Claude cho `taxonomy_collision` (105 cặp: 2 máy gán độc lập khớp 103/105, 2 cặp qua trọng tài); Claude soát nhãn luật phủ định, 6 cặp lệch lấy nhãn soát và ghi `⚠` vào note (matcher bỏ sót "Quán bar cạnh bể bơi", nhà hàng / gym nói trong mô tả; "Phòng tập thể" (phòng tập thể = dorm) bị khớp nhầm thành gym). Mọi nhãn máy là `chưa duyệt`; `import --append` từ chối cho tới khi QAnh duyệt.
- **Luật combo khứ hồi (#8d) sửa giữa chừng:** bản đầu của luật gán 0 cho mọi sản phẩm không phải tuyến; holes có 6 combo "vé máy bay khứ hồi" đúng cặp → sửa thành 1. Nhãn luật của pool không đổi (byte-identical — pool câu bay chỉ có tuyến).
- **D11:** sửa matcher tiện ích của bench và build lại catalog bench (`--allow-id-drift`: 403 khoá đổi id, 3 khoá `raw:` biến mất; `items_sha256` 90e9ae51… → 03b61f22… → 14e13076… sau review (7)–(8)); `sb load` lại `Products__T3_R__cohere_v3` và `…e5_base` từ vector cache (0 lượt Cohere, text không đổi). Tỉnh sai của sản phẩm golf và Vinpearl Hà Tĩnh trùng nằm ở snapshot nguồn → chưa sửa (ngoài trọng tâm gold-v4).
- **D10 / D12:** không sửa PRD. FR-SRC-03 ("vé máy bay không nằm trong `/search`") lệch với quyết định giữ câu bay như slice thường — tồn đọng, cập nhật PRD sau qua `docs/prd/update/`.

- **Review đối kháng** (workflow 4 người soát + 2 người phản bác mỗi phát hiện): 8 phát hiện đứng vững, 1 bị bác — đã sửa cả 8: (1) `import --append` so `verify_append` với **tag gold_v\* mới nhất** khi ghi gold của package (bản đầu so file với chính nó, không bắt được trôi); (2) `list_gold_tags` (git) chỉ gọi khi cần và nằm trong `_gold_errors` (bản đầu gọi sớm, lỗi git thành traceback exit 1); (3) `pair_sources` kiểm cột / giá trị `source` của `provenance_X.csv` (file hỏng → exit 2, không âm thầm coi nhãn máy là người); (4) `holes --new-since` file hỏng / thư mục → exit 2; (5) `--qids ""` → exit 2; (6) `gold drafts` đọc `overrides.tsv` cạnh `--raw` như `gold pool`; (7) chuỗi "… : no"; (8) tiện ích tạm ngừng hoạt động. (7)–(8) không chạm ứng viên v4a nào (0 / 641 cặp), nhãn luật pool và hole giữ byte-identical sau khi build lại.

## Kiểm tra

- `pytest evaluation/search_bench/tests`: **371 passed, 11 skipped** (sau review; trước review 367 passed) (trước khi sửa backend: 346 passed, 1 failed `test_build_app_catalog_matches_bench_text` do `NameError: Protocol`).
- Chạy thử toàn chuỗi trên bản sao gold ở scratchpad (gold thật không đổi): `gold merge` 559 cặp, 0 `needs_discussion`; `gold import --append` không cờ → exit 1 "nhãn máy chưa duyệt: 559 vi phạm" (đúng thiết kế); có `--accept-unreviewed` → +23 câu (tổng 155); `gold check` xanh (154 câu active, 15 slice); `gold verify-append gold_v3` xanh (+23 câu, +559 nhãn, 0 nhãn cũ đổi).
- Run `20261005-v4a-holes` (`--allow-untagged`, gold bản sao có nhãn máy chưa duyệt — **không trích dẫn**) cho B0, E2.e5, APP.hybrid_norm; holes D8a: 59 cặp / 16 câu + 27 auto_ooc.
- Chạy lại cả chuỗi trên bản sao mới sau review: merge 559 cặp → `import --append` +23 câu → `holes import` +59 nhãn máy + 27 auto_ooc → `gold check` xanh (154 câu) → `verify-append gold_v3` xanh (+23 câu, +645 nhãn; tổng 5.666 nhãn). `gold verify-append gold_v3` trên gold thật: +0 (gold thật chưa đổi).
- Nhãn máy hole: 47 luật + 12 Claude (`taxonomy_collision` 8 cặp: 2 máy khớp 7/8, 1 qua trọng tài; soát phủ định lật 4 nhãn luật: "Bồn tắm spa" bị khớp thành spa, spa nói trong tên "Resort & Spa", nhà hàng / bar chỉ có trong mô tả hoặc chuỗi thô).
- Chạy thử tiếp trên bản sao: `holes import` không cờ → exit 1 (59 nhãn máy chưa duyệt); có `--accept-unreviewed` → +59 nhãn máy + 27 auto_ooc; `gold check` xanh; `verify-append gold_v3` xanh: **+23 câu, +645 nhãn, 0 nhãn cũ đổi**.
- Không chạy `validate_contract.py` (không đổi contract / mock); không đổi `db/`.
- **Duyệt:** QAnh duyệt 618 / 618 nhãn máy (`provenance_*.csv`: `accepted` 279 + 280 + 59, `edited` 0, chưa duyệt 0).
- **Import thật** (từ `src/`): `gold merge` 559 cặp, 0 `needs_discussion` → `gold import --append --version gold_v4`: +23 câu (tổng 155), nguồn `machine_accepted` 559 → `gold holes import gold_v4__D8a --version gold_v4`: +59 nhãn máy đã duyệt, +27 auto_ooc → `gold check` **xanh** (154 câu active, 15 slice) → `gold verify-append gold_v3` **xanh** (+23 câu, +645 nhãn, +0 retired). Tổng 5.666 nhãn (5.636 active).

## Còn lại / rủi ro

1. Người dùng commit (entry này cùng commit) rồi chạy `git tag gold_v4`.
2. Chưa có report trên gold_v4: chạy lại các arm cần so (câu mới chưa có trong run cũ — `rescore` không đủ), report ở `src/evaluation/reports/eval-YYYY-MM-DD-<slug>.md`, tách khối 131 câu v3 / 23 câu v4 (hai rubric). Run `20261005-v4a-holes` chạy trên gold chưa duyệt — không trích dẫn.
3. Giới hạn đã biết của gold_v4: một người duyệt, không có κ; QAnh giữ nguyên 100 % nhãn máy nên không đo được tỉ lệ máy sai; hai slice mới chỉ 5–6 câu.
4. Chưa làm (ngoài trọng tâm, đã ghi ở plan): Track G (guard, probe, `win_scope: gold_v3`), sửa dữ liệu nguồn (tỉnh golf, Vinpearl Hà Tĩnh trùng), dọn hai class thừa ở `unit_index.py` (chủ backend), alias "phòng tập" → gym khớp nhầm "phòng tập thể" trong `amenity_seed.yaml` (dùng chung với vector_bench), cập nhật PRD cho vé máy bay trong `/search` (D12).
5. Các collection Weaviate bench đã nạp lại theo `items_sha256` mới (14e13076…); run cũ vẫn `rescore` được (top_ids không đổi) nhưng `items_sha256` trong report cũ khác bản hiện tại.
