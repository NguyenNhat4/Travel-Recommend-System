# Sinh 600 case ứng viên cho search gold

- Ngày: 2026-09-23
- Tác giả: người dùng / Codex
- Nhánh: codex/role-a-day1
- Trạng thái: hoàn thành
- Phạm vi: evaluation, data, docs

## Mục tiêu

Thực hiện phần sinh ý tưởng của Người A ngày 1 cho benchmark embedding + search: dựng vocabulary từ catalog mới nhất và sinh đúng 600 case ứng viên hợp lệ, có grounding để người dùng tự lọc xuống 200 case. Chưa chọn thay người dùng, chưa tạo gold và chưa gán relevance. Công việc phục vụ FR-SRC-01..04, NFR-PERF-01, NFR-PERF-03 và AC-SRC-01.

## File thay đổi

- `.gitignore` — sửa: bỏ qua `bench_out/`, nơi chứa vocabulary và artifact benchmark dựng lại được.
- `docs/spec/bench/ARMS.md` — sửa: bổ sung mã FR/NFR/AC mà spec phục vụ.
- `docs/spec/bench/SEARCH_EVAL_CHECKLIST.md` — sửa: bổ sung mã yêu cầu; sửa đường dẫn schema/prompt/catalog, 10 slice thành 13 slice; ghi output raw và đánh dấu việc sinh 600 đã hoàn thành, việc chọn 200 vẫn để mở.
- `docs/spec/bench/SEARCH_EVAL_LOCAL_SPEC.md` — sửa: bổ sung mã yêu cầu; sửa đường dẫn schema/catalog và cập nhật cây artifact `gold/`.
- `docs/spec/bench/gold-draft-prompt.md` — thêm: prompt, quota 600 ứng viên, format TSV và checklist QA grounded.
- `src/evaluation/search_bench/gold/drafts_raw.tsv` — thêm: 600 case ứng viên hợp lệ, chưa có quyết định giữ/loại; mỗi case in-catalog có `source_refs`.
- `src/evaluation/search_bench/gold/drafts_manifest.json` — thêm: checksum catalog/vocab, quy mô nguồn, quota 600, mục tiêu sau lọc và kết quả QA.
- `history/2026-09-23-sinh-600-search-cases.md` — thêm: entry này.

Artifact runtime không commit: `bench_out/search/data/vocab.json`, sinh từ catalog 11.387 dòng; checksum được khóa trong manifest.

## Quyết định

- Bàn giao đúng 600 case ứng viên; không cố ý trộn case lỗi, không tạo `drafts.txt`, không tạo rejection log và không tự chọn 200. Người dùng sẽ lọc ở bước kế tiếp.
- Dùng quota draft bằng ba lần quota cuối cho đủ 13 slice; mỗi dòng chỉ có một slice chính.
- Đặt prompt ở `docs/spec/bench/gold-draft-prompt.md` theo chốt của người dùng, thay vì dưới `src/`, để tuân thủ AGENTS.md §7.
- Ground query theo catalog runtime mới nhất tại `src/data_collection/data/products.jsonl`: 11.387 sản phẩm, 3.183 search unit, 38 destination; SHA-256 `518a9aa7820c9ded4a02a2c9148af2ffa4103272071c84b6e0235f4ee251d862`.
- Mỗi query in-catalog giữ `source_refs` để kiểm toán. Query `out_of_catalog` chỉ dùng destination đã xác nhận không có trong vocabulary hiện tại.
- Chưa gọi tập này là `gold_v1`; gold chỉ được khóa sau bước pool và gán nhãn theo checklist.
- Không đổi contract, DDL, retrieval hay ngưỡng benchmark; thay đổi hiện thực đúng phạm vi đánh giá của PRD, không cần proposal PRD.

## Kiểm tra

- Validator bộ draft: **PASS** — 600 dòng và 600 query unique sau chuẩn hóa; đúng quota 13 slice; 570 case in-catalog có reference hợp lệ; 30 case out-of-catalog dùng destination vắng trong vocabulary; 60 AST filter parse được và sản phẩm nguồn thỏa mọi constraint; semantic evidence của destination/type, audience, amenity, parent-child, named entity, no-diacritics và cross-vertical đều hợp lệ.
- Checksum: catalog `518a9aa7820c9ded4a02a2c9148af2ffa4103272071c84b6e0235f4ee251d862`; vocabulary `7268026d48278fcd9ad47dd5c5ff6eec05ee85749bd13584f17ecf99e8ac7482`.
- `git diff --check`: PASS.
- Quét các đường dẫn cũ, số slice cũ, rejection artifact và kết quả chọn/loại cũ trong tài liệu bench: không còn tham chiếu sai.
- Không chạy `validate_contract.py`: không đổi OpenAPI hoặc mock.

## Còn lại / rủi ro

- Người dùng cần tự lọc 600 ứng viên xuống 200 và tạo `gold/drafts.txt`; đây là chủ đích của phạm vi hiện tại.
- `src/evaluation/search_bench/` chưa có CLI `sb`; vocabulary được sinh bằng quy trình một lần, có checksum. Khi Part 0–1 được triển khai, cần chạy lại `sb catalog build` / `sb catalog vocab` và đối chiếu checksum.
- Catalog 11.387 dòng nằm ở workspace tích hợp catalog hiện tại, chưa có trong base `bench/embed-search`; nhánh này cần được merge sau/đồng thời với snapshot catalog mới để tái tạo đúng vocabulary.
- Ngày 2–4 chưa làm: metrics, GUIDE, pool, gán nhãn, kappa, import và tag `gold_v1`.
