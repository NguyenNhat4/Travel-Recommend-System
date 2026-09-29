# Áp dụng vào PRD hai đề xuất đã chốt: agent gọi engine trong tiến trình (P-A) và tool Similar (P-B)

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: docs
- Thay thế: 2026-09-28-de-xuat-agent-goi-engine-trong-tien-trinh.md
- Đề xuất: docs/prd/update-archive/2026-09-28-agent-goi-engine-trong-tien-trinh.md, docs/prd/update-archive/2026-09-28-tool-similar-cho-agent.md

## Mục tiêu

Ngày 2026-09-29 người dùng chốt cả hai đề xuất ("chốt 2 đề xuất P-A và P-B"). Theo `AGENTS.md` §8 bước 3–4, phải sửa `docs/prd/` đúng nội dung đã chốt trước khi sửa source, rồi đổi trạng thái hai đề xuất sang `đã áp dụng` và chuyển chúng sang `docs/prd/update-archive/`. Entry này chỉ ghi phần PRD và lưu trữ. Code Phase B (tool `get_similar_products`) nằm ở entry `2026-09-29-tool-similar-cho-agent.md`. Code Phase 0/A của P-A đã làm song song và ghi ở `2026-09-28-agent-goi-engine-trong-tien-trinh.md` cùng `2026-09-28-recsys-strategy-enum-va-cdp-fallback.md`.

## File thay đổi

- `docs/prd/requirements.md` — sửa: §1.4 FR-AGT-02 lấy câu "Thay bằng" của P-A, rồi chèn cụm của P-B "tìm sản phẩm tương tự một sản phẩm đã đề xuất (khi đổi món, FR-AGT-05)" ngay sau "gợi ý cá nhân hoá", theo P-B mục 1 cho trường hợp P-A áp dụng trước. FR-AGT-05 giữ câu cũ và thêm câu về tìm sản phẩm tương tự (P-B mục 2).
- `docs/prd/architecture.md` — sửa, gồm ba chỗ:
  - §2, cây thư mục: thêm dòng ghi chú `itinerary/engine_tools.py` dưới `application/<domain>/` và thay ghi chú dòng `infrastructure/clients/` (P-A mục 2).
  - §3: nhãn chuyển `SearchCandidates --> ToolCatalogSearch` thêm "(và Similar khi đổi món)"; id trạng thái giữ nguyên (P-B mục 3).
  - §3, gạch đầu dòng đầu của Tiêu chuẩn Grounding: nguồn dữ liệu sản phẩm là công cụ truy xuất Search, Recommendation hoặc Similar (`getSimilarProducts`) (P-B mục 4).
- `docs/prd/deployment-plan.md` — sửa: §2 thêm ba dòng `ITINERARY_DATA_MODE`, `ITINERARY_SERVICE_BASE_URL`, `ITINERARY_TOOL_TIMEOUT_SECONDS` sau `LLM_API_KEY` (P-A mục 3).
- `docs/prd/update-archive/2026-09-28-agent-goi-engine-trong-tien-trinh.md` — thêm: P-A, trạng thái `đã áp dụng`, "Chốt bởi / ngày: tqanh123 (người dùng), 2026-09-29". Ghi rõ đã chốt cả vị trí `engine_tools.py` trong `application`, và FR-AGT-02 được áp dụng gộp với P-B.
- `docs/prd/update-archive/2026-09-28-tool-similar-cho-agent.md` — thêm: P-B, trạng thái `đã áp dụng`, cùng người chốt và ngày. Mục "Câu hỏi mở" ghi cách giải quyết ba câu hỏi.
- `history/2026-09-28-de-xuat-agent-goi-engine-trong-tien-trinh.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.

## Quyết định

- Người chốt không chọn phương án riêng cho ba câu hỏi mở của P-B, nên áp dụng mặc định của đề xuất:
  - Câu 1 (compose ưu tiên kết quả similar cho ô đang đổi) và câu 2 (thêm tham số `destination` hoặc chế độ `cross_taxonomy`): để sau, không làm trong đợt này.
  - Câu 3: thêm tool theo cấu trúc `tool_contracts.py` hiện tại. Việc chọn hướng (a)/(b) vẫn là việc dang dở của `2026-09-23-tai-thiet-lap-cau-truc-backend.md`.
- P-A được chốt cùng cách đọc dòng `infrastructure/ # LỚP 3: hiện thực port`: dòng này chỉ nói về hiện thực port có chạm SDK, DB hoặc HTTP. Vì vậy `application/itinerary/engine_tools.py` ở lại `application`, và `tests/architecture/` không đổi. Nhánh "Nếu bị từ chối" của P-A không còn áp dụng.
- FR-AGT-02 chỉ sửa một lần, bằng câu đã gộp P-A và P-B, thay vì sửa hai lần liên tiếp.
- Chữ PRD chép nguyên văn phần "Thay bằng" của hai đề xuất, không thêm bớt.
- Thứ tự đúng `AGENTS.md` §8 bước 3, theo mtime của file:
  1. Ba file PRD (03:11:46).
  2. Hai file lưu trữ (03:12:02).
  3. Contract Phase B (`paths/catalog.yaml`, 03:17:51).
  4. Source Phase B, từ `tool_contracts.py` (03:18:52).
- Hai đề xuất chưa bao giờ được commit ở `docs/prd/update/`: đó chỉ là file chưa theo dõi trong working tree. Vì vậy chúng được chuyển bằng `mv` thường, vì `git mv` không dùng được. Git chỉ thấy hai file mới dưới `docs/prd/update-archive/` và không thấy file nào bị xoá dưới `docs/prd/update/`. Trong `docs/prd/update/` chỉ còn `2026-09-24-them-thu-muc-docs-guide.md`, không liên quan.
- Entry này thay thế `2026-09-28-de-xuat-agent-goi-engine-trong-tien-trinh.md`: trạng thái `dang dở` và các đường dẫn `docs/prd/update/2026-09-28-*.md` của entry đó hết hiệu lực. Thân entry cũ không sửa (`history/README.md`).
- File P-A đã lưu trữ không ghi tên entry history của lần áp dụng; entry này chính là entry đó. File P-B đã lưu trữ trỏ tới `2026-09-29-tool-similar-cho-agent.md` cho phần source.

## Kiểm tra

- Chỉ sửa tài liệu, không có test tự động riêng.
- Kiểm bằng script (so sau khi chuẩn hoá khoảng trắng): câu FR-AGT-02 đã gộp, câu thêm của FR-AGT-05, nhãn chuyển §3, câu grounding §3, hai ghi chú cây thư mục §2 và ba dòng biến môi trường đều có đúng nguyên văn trong PRD. Kết quả: cả 7 mục `True`.
- Bước review cuối của Phase B cũng xác nhận các sửa PRD khớp nguyên văn P-A và P-B, và hai đề xuất đã ở trạng thái `đã áp dụng` với "Chốt bởi tqanh123, 2026-09-29".
- Tìm `docs/prd/update/2026-09-28` trên toàn repo (Grep): chỉ còn trong entry `2026-09-28-de-xuat-agent-goi-engine-trong-tien-trinh.md` (bị entry này thay thế) và chính entry này. `docs/spec`, `docs/plan`, `src` không còn tham chiếu nào tới đường dẫn cũ.

## Còn lại / rủi ro

- Không còn việc PRD nào của P-A và P-B.
- Hai câu hỏi mở 1 và 2 của P-B vẫn để sau. Muốn làm thì phải qua đề xuất mới trong `docs/prd/update/`.
- Chưa commit. Khi chia commit, hai file PRD/lưu trữ và entry này nên đi cùng, hoặc đi trước, commit code Phase B.
