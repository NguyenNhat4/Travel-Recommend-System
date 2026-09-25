# /search: bước chuẩn hoá truy vấn (viết tắt, chính tả tên riêng, điểm đến, kiểu đi)

- Ngày: 2026-09-25
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/hybrid-search
- Trạng thái: hoàn thành
- Phạm vi: backend, contract, docs (spec), frontend (chỉ `api.gen.ts` sinh lại)

## Mục tiêu

`/search` đưa nguyên câu người dùng gõ vào Cohere embed và BM25, nên viết tắt không được hiểu ("KS biển tại NT" → 2 căn hộ ở Nghệ An vì BM25 khớp chữ "KS" trong tên), lỗi chính tả tên riêng không khớp ("Vinpeal"), tên điểm đến không dấu không về dạng chuẩn. Đây là bước 1 (chuẩn hoá) trong quy trình người dùng đưa ra ngày 25/09; bench spec Part 6 (`docs/spec/bench/search-eval-local-spec.md`) và 15 câu gold slice `abbrev_typo` đã mô tả đúng nhu cầu này. Phục vụ FR-SRC-01, FR-SRC-04. Người dùng chốt: bật sửa chính tả dè dặt; `KDL` lấy cả hai nghĩa; chỉ khai ở diagnostics, không sửa UI; thêm nhận diện kiểu đi (một mình, cặp đôi, gia đình, nhóm, công ty).

## File thay đổi

Contract (sửa trước code, AGENTS.md §3):
- `src/shared/contracts/schemas/search.yaml` — sửa: `EngineDiagnostics` thêm trường tuỳ chọn `normalizedQuery`, `appliedAliases[]`, `corrections[]` (`{from, to}`), `party` (enum SOLO/COUPLE/FAMILY/FRIENDS/BUSINESS). Không đổi trường cũ.

Backend:
- `src/backend/app/domain/search/normalize.py` — thêm: `ALIASES`, `DESTINATION_ALIASES`, `PARTY_PHRASES`, `NormalizedQuery`, `QueryNormalizer` (4 lượt trên chuỗi gốc: alias/giá → sửa chính tả → gazetteer điểm đến → kiểu đi; khoảng cách Damerau–Levenshtein OSA; regex âm tiết tiếng Việt làm chốt chặn).
- `src/backend/app/domain/search/__init__.py` — sửa: export các tên trên.
- `src/backend/app/application/search/use_cases.py` — sửa: `SearchProducts` thêm `normalize: bool = True`, dựng `QueryNormalizer` từ `index.destination` + tên search unit lúc khởi tạo; `__call__` embed/BM25/độ phủ đều dùng câu đã chuẩn hoá; `_normalization_diagnostics` chỉ thêm khoá khi có nhận ra/đổi gì.
- `src/backend/app/core/config.py` — sửa: `search_normalize: bool = True`.
- `src/backend/app/main.py` — sửa: truyền `normalize=settings.search_normalize`, log `startup.recsys.search.normalize`.
- `.env.example` — sửa: `SEARCH_NORMALIZE=true`.
- `src/backend/tests/unit/domain/test_normalize.py` — thêm: 15 câu gold `abbrev_typo`, idempotent, alias nhiều token, dấu câu, whole-token, chốt chặn sửa chính tả, alias tới điểm đến catalog không có bị bỏ, NFD, 9 câu kiểu đi.
- `src/backend/tests/unit/application/test_search_normalization.py` — thêm: câu đã chuẩn hoá tới embedder (spy), diagnostics, `normalize=False`, "Vinpeal Golf Nha Trang" được vớt từ BM25 sau khi sửa.
- `src/backend/tests/unit/application/test_hybrid_search.py` — sửa: vòng lặp validate contract thêm "KS ở PQ Vinpeal cho gd".

Spec và frontend:
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 thêm `CHUẨN HOÁ` + định nghĩa `q'`; §2.4 `normalize: true`; §9 tiêu chí 10c; §10 S10.
- `src/frontend/src/types/api.gen.ts` — sinh lại (`npm run generate:api-types`), chỉ thêm trường tuỳ chọn.

## Quyết định

- **Bốn lượt trên chuỗi gốc, khớp trên dạng fold, thay theo span từ phải sang trái**: từ không đụng tới giữ nguyên dấu/hoa thường/dấu câu; lượt alias tra cả gazetteer để "khớp dài nhất" đúng ("tp ho chi minh" 4 token thắng alias "ho chi minh") — nếu không, chạy lần hai ra "TP. TP. Hồ Chí Minh" (test idempotent bắt được).
- **Sửa chính tả không cần từ điển tiếng Việt**: token khớp regex âm tiết Việt (phụ âm đầu + 1–3 nguyên âm + phụ âm cuối) không bao giờ bị sửa; chỉ token dài ≥ 5, không có trong từ vựng, không có chữ số, cách ≤ 1 (≤ 2 khi ≥ 8) so với token có mặt ở ≥ 3 tên sản phẩm. Thay bằng cách viết phổ biến nhất trong catalog ("Vinpearl", "Trang"). Từ vựng dựng từ catalog đang chạy (2.224 token trên DB 2026-09-21), không bảng chép tay.
- **Bảng viết tắt chỉ chứa cách viết** (theo `data_collection/collectors/geo.py`, bỏ địa danh con "ba na", "cam ranh"); alias trỏ điểm đến catalog không có thì bỏ lúc dựng. `dn` = Đà Nẵng (catalog không có Đồng Nai); bỏ `qn`, `vp` vì nhập nhằng.
- **Kiểu đi**: cụm → nhãn mà text catalog dùng (`audience`: Gia đình 297 · Nhóm bạn 286 · Cặp đôi 280 · Doanh nhân 210; mô tả: "cặp đôi" 322, "một mình" 110, "nhóm bạn" 274, "công tác" 260). Cụm mang thêm nghĩa ("có trẻ nhỏ", "nhóm 4 người", "hội nghị") giữ nguyên chữ, chỉ set `party`. Không suy từ số người (bước 2).
- **`KDL` → "khu du lịch nghỉ dưỡng"** theo người dùng (cả hai nghĩa), lệch bench spec Part 6 ("khu nghỉ dưỡng"); bench nên lấy bảng backend làm nguồn cho `config/aliases.yaml` (§10 S10).
- **Quan hệ với `history/2026-09-20-resolve-destination-from-catalog.md`** ("không hardcode alias"): quyết định đó vẫn giữ cho Agent — `match_destination` không đổi, `tests/unit/agents/test_normalization.py` vẫn xanh. Thanh tìm kiếm không có LLM và có ngân sách p95 300 ms nên cần bảng tất định; tính hợp lệ vẫn đến từ catalog (đích alias kiểm với `index.destination`, từ vựng sửa chính tả từ tên sản phẩm).
- Không lệch PRD: bước này hiện thực FR-SRC-01/04; contract chỉ thêm trường tuỳ chọn (spec §7.4). Không tạo đề xuất `docs/prd/update/`.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py` — PASS.
- `PYTHONUTF8=1 pytest src/backend/tests` — **478 passed, 19 skipped** (gồm `tests/architecture`, `tests/unit/agents/test_normalization.py`).
- `QueryNormalizer` trên catalog thật (2.897 search unit, 35 điểm đến): dựng 0,16 s, 0,29 ms/câu; 15 câu gold `abbrev_typo` đều ra đúng; câu đã đúng ("resort 5 sao view biển ở Nha Trang", "VinWonders Phú Quốc", "hotels near center") không đổi.
- Backend thật (`uvicorn`, log `startup.recsys.search.normalize=True`), `GET /api/v1/search`:
  - "KS biển tại NT" → `normalizedQuery` "khách sạn biển tại Nha Trang", **141** khách sạn Nha Trang (trước: 2 căn hộ "KS L'azur" Nghệ An).
  - "Vinpeal Resort Nha Trang" → `corrections` Vinpeal→Vinpearl, top-1 Vinpearl Resort Nha Trang, 39 kết quả (trước: 0 hoặc lệch).
  - "ve may bay SG di DN" → "ve may bay TP. Hồ Chí Minh di Đà Nẵng", top-1 Vé máy bay TP. Hồ Chí Minh - Đà Nẵng.
  - "khach san Nha Trnag co ban cong" → sửa Trnag→Trang, 3 khách sạn Nha Trang.
  - "đi du lịch biển 1 mình ở Nha Trang" → `party: SOLO`, text "một mình"; vẫn 6 attraction, khách sạn chưa qua cutoff 0.62 (đúng như dự báo: đây là việc của S1 cutoff / bước 2, không phải của chuẩn hoá).
  - "chỗ nghỉ yên tĩnh ở Hội An đi cùng bạn gái" → COUPLE, 56 homestay/villa Hội An; "khách sạn Hà Nội đi cùng công ty" → BUSINESS, 4 khách sạn Hà Nội; "KDL NT cho gia đình" → FAMILY, 184 kết quả nghiêng về khu nghỉ dưỡng.
- Frontend: `npm run generate:api-types` sinh `normalizedQuery?`, `party?: "SOLO" | …`; `npm run typecheck` sạch; `npm run test:unit` 75/75 pass.

## Còn lại / rủi ro

- Bảng viết tắt, cụm kiểu đi và ngưỡng sửa chính tả chưa benchmark (spec §10 S10) — đo trên slice `abbrev_typo`, `audience_style` của gold khi bench có `qu.py`.
- Sửa chính tả có thể đổi từ tiếng Anh cách 1 ký tự với token catalog phổ biến ("hotels" → "Hotel"); mọi lần sửa hiện ở `corrections`, tắt bằng `SEARCH_NORMALIZE=false` hoặc `QueryNormalizer(spelling=False)`.
- `party` mới chỉ khai báo; chưa dùng để lọc, ưu tiên loại phòng hay suy `pax` (bước 2). "1 mình" chưa kéo khách sạn qua cutoff — cần bước 2 hoặc benchmark cutoff (S1).
- `QN`, `VP` chưa có alias; "Sapa" → "Sa Pa" nay là điểm đến trong catalog (arms.md dùng "resort ở Sapa" làm ví dụ out_of_catalog — cần sửa ví dụ ở bench).
- Trên worktree Windows, `uvicorn --reload` không nạp lại code: restart tay sau khi sửa backend.
