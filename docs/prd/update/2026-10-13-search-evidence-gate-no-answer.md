# `/search`: chỉ nhận khớp chữ khi có bằng chứng theo cụm, trả rỗng khi câu chỉ có tên lạ, lọc thời lượng cho vé/combo

- Ngày: 2026-10-13
- Người đề xuất: tqanh123 / Claude Code soạn
- Trạng thái: đã chốt (PRD đã cập nhật 2026-10-13; source chưa sửa — chuyển `update-archive/` khi plan làm xong)
- Chốt bởi / ngày: tqanh123, 2026-10-13
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.2 (FR-SRC-03, FR-SRC-04); `docs/prd/deployment-plan.md` §2 (dòng `SEARCH_CUTOFF`, thêm các biến `SEARCH_*` mới); `docs/prd/architecture.md` §5 (index lexical, chỉ cho P1). Contract: định nghĩa R ở `src/shared/contracts/schemas/common.yaml` (1.28.0 additive).
- Mã FR/NFR: FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01, NFR-PERF-01
- Thay thế: `docs/prd/update-archive/2026-10-06-search-hybrid-min-coverage-rrf.md` (hạ `lexicalMinCoverage` 0,6 → 0,1 đi ngược hướng đề xuất này). Khi đề xuất này được chốt, đề xuất cũ chuyển sang `update-archive/` với trạng thái `từ chối (thay bằng 2026-10-13-search-evidence-gate-no-answer)`.
- Plan chi tiết: `docs/plan/2026-10-13-search-evidence-gate-no-answer.md`

## Lý do

Khi câu không có đáp án trong catalog, `/search` vẫn trả kết quả chỉ trùng một âm tiết. Số đo trên backend live ngày 13/10 (chỉ đọc):

| Câu | Hôm nay | Vì sao |
|---|---|---|
| `2 ngày 1 đêm` | 204 kết quả, có "Chợ Đêm", khách sạn "ngay … chợ đêm" | cosine sàn 0,84 nhận cả trăm unit; "đêm" bị coi như nội dung |
| `nguyen khac tiep` | 214 kết quả vô nghĩa | câu không dấu hạ cutoff xuống 0,80 |
| `Trần Thị Mai` | "Thị trấn Hoàng Hôn" | bỏ dấu thì "Trần" = "trấn"; độ phủ đếm âm tiết, bỏ qua thứ tự |
| `khách sạn Nguyễn Khắc Tiệp` | 153 khách sạn | phần "khách sạn" thoả được nên tên lạ bị bỏ qua |
| `Phạm Văn Đồng` | "Sân Vận động…", "Nhà Văn hóa … Đồng Tháp" | như trên (Văn = Vận, Đồng = Động khi bỏ dấu) |

PRD hiện tự ghi đây là giới hạn đã biết (`deployment-plan.md`: "Cutoff tuyệt đối không làm câu ngoài catalog trả rỗng — giới hạn đã biết"), còn FR-SRC-04 chưa nói khi nào được trả rỗng. Bench 06/10 xác nhận chỉnh cutoff không giải quyết được (7/7 câu ngoài catalog vẫn có kết quả ở mọi cấu hình).

## Nội dung đề xuất

### 1. `docs/prd/requirements.md` — FR-SRC-04

Hiện tại:

> **FR-SRC-04 (Xử lý không có kết quả):** Khi truy vấn không có kết quả khớp chính xác, hệ thống phải đề xuất các sản phẩm có độ tương đồng ngữ nghĩa gần nhất hoặc gợi ý điều chỉnh từ khóa tìm kiếm.

Thay bằng:

> **FR-SRC-04 (Xử lý không có kết quả):** Khi truy vấn không có kết quả khớp chính xác, hệ thống phải đề xuất các sản phẩm có độ tương đồng ngữ nghĩa gần nhất (gắn nhãn "Kết quả gần nhất") hoặc gợi ý điều chỉnh từ khóa tìm kiếm. Phần câu còn lại sau khi tách điều kiện (điểm đến, loại, thời lượng, giá, số khách) mà **toàn bộ** là một cụm dạng tên riêng catalog không có (vd "Nguyễn Khắc Tiệp", "khách sạn Nguyễn Khắc Tiệp"), hoặc cả câu không có chữ nào catalog hiểu, thì trả **rỗng** kèm lý do (`emptyReason: unexplained`) để giao diện gợi ý điều chỉnh từ khóa; cụm lạ không phải tên ("rẻ bèo", "sống ảo") chỉ bị bỏ khỏi truy vấn, vẫn tìm phần còn lại. Khớp từ khóa chỉ được vớt hoặc đẩy thứ hạng một sản phẩm khi khớp **cụm liền nhau, đúng thứ tự, giữ dấu** (không tính trùng lẻ một âm tiết).

### 2. `docs/prd/requirements.md` — FR-SRC-03 (thêm một ý)

Thêm:

> - Thời lượng trong câu ("2 ngày 1 đêm", "3N2Đ") lọc **vé tham quan và combo** theo số ngày/đêm suy từ tên hoặc thời lượng gợi ý của sản phẩm; không có sản phẩm khớp thì trả rỗng với `emptyReason: duration`. Câu có từ lưu trú ("khách sạn", "resort", "homestay"…) thì thời lượng chỉ được ghi nhận, **không** loại khách sạn.

### 3. `docs/prd/deployment-plan.md` §2 — dòng `SEARCH_CUTOFF`

Hiện tại (ô cuối):

> Không bí mật. Hiệu chỉnh trên gold khi đổi model. Cutoff tuyệt đối không làm câu ngoài catalog trả rỗng — giới hạn đã biết

Thay bằng:

> Không bí mật. Hiệu chỉnh trên gold khi đổi model. Cutoff tuyệt đối không tự làm câu ngoài catalog trả rỗng; việc đó do cổng bằng chứng (`SEARCH_EVIDENCE_GATE`) và luật câu không giải thích được (`SEARCH_UNEXPLAINED_EMPTY`) đảm nhận.

Đồng thời: `SEARCH_NO_DIACRITICS_MODE` thêm giá trị `restore` (phục hồi dấu theo cụm có trong catalog, không hạ cutoff) và thêm dòng cho các biến mới, đều mặc định tắt: `SEARCH_EVIDENCE_GATE`, `SEARCH_DURATION_MASK`, `SEARCH_EMBED_RESIDUAL`, `SEARCH_UNEXPLAINED_EMPTY`, `SEARCH_EMIT_BACKGROUND`.

### 4. Contract (không phải PRD, ghi để người duyệt biết)

Định nghĩa R trong `common.yaml` thêm nhánh "khi `evidenceGate` bật"; `emptyReason` thêm `unexplained`; `queryPlan` thêm `unexplained`, `unparsed`, `denseText`, `duration.role`; backend bắt đầu phát `backgroundScore` (đã khai từ trước). Contract 1.28.0, chỉ thêm; mọi cờ tắt thì response giữ nguyên như 1.27.0.

### 5. P1 — `docs/prd/architecture.md` §5 (chỉ khi làm P1)

Index lexical của Weaviate thêm các trường `nameTone`, `nameBigrams`, `aliasAscii`, `descAscii` cạnh `nameAscii`/`searchTextAscii`; nạp bằng backfill, **không** embed lại. Không thêm vector nào (FR-SRC-02 giữ nguyên).

## Thay đổi source sau khi chốt

- Backend: `src/backend/app/domain/search/{lexical,hybrid,query_plan,constraints,normalize}.py`, `explain.py` (mới), `src/backend/app/domain/catalog/unit_attributes.py`, `src/backend/app/application/ports/unit_index.py`, `src/backend/app/application/search/use_cases.py`, `src/backend/app/core/config.py`, `src/backend/app/main.py`, test tương ứng.
- Contract: `src/shared/contracts/schemas/search.yaml`, `common.yaml`, `openapi.yaml` (1.28.0); regen `src/frontend/src/types/api.gen.ts`.
- Frontend: `src/frontend/src/services/search.ts`, `src/frontend/src/components/search/SearchView.tsx`.
- Bench/gold: `src/evaluation/search_bench/{app_adapter.py,arms/,gold/,config/query_annotations.yaml}`; report `src/evaluation/reports/eval-2026-10-1x-search-evidence-gate.md`.
- Spec: `docs/spec/hop-dong-tich-hop-search-recommendation.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/bench/arms.md`, `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md`.
- P1: `src/backend/app/infrastructure/vectors/weaviate_store.py`, `src/backend/jobs/embed_products.py`.
