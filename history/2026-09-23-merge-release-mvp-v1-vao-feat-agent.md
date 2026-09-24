# Merge release-mvp-v1 vào feat/agent và chỉnh route catalog theo cấu trúc backend mới

- Ngày: 2026-09-23
- Tác giả: người dùng / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, evaluation, docs

## Mục tiêu

Kéo `origin/release-mvp-v1` (19 commit, 176 file, +8178/-1090) về `feat/agent` và xử lý xung đột, sau khi
commit `1f86065` thêm route `GET /api/v1/destinations` để nối lại chuẩn hóa điểm đến ở HTTP data mode.

Nhánh release mang theo hai thay đổi lớn chạm đúng chỗ vừa sửa: chuẩn hóa cấu trúc backend theo PRD
(router v1 gộp một chỗ, route nhận use case qua `Depends`, `api/errors.py` + `api/middleware.py` tách
khỏi `main.py`, test chia theo tầng) và domain Auth P0.

## File thay đổi

Ngoài nội dung merge từ nhánh release, phần do merge này tạo ra:

- `src/backend/app/main.py` — sửa: giải quyết xung đột, lấy cấu trúc của nhánh release
  (`api/v1/router.py`, `install_cors`/`install_request_id`/`install_error_handlers`); bỏ ba dòng
  `include_router` mà commit `1f86065` thêm thẳng vào app.
- `src/backend/app/api/v1/routes/catalog.py` — sửa: bỏ `prefix="/api/v1"` tự khai (router v1 gắn prefix),
  đọc index qua `Depends(get_index)` thay vì `request.app.state` trực tiếp.
- `src/backend/app/api/deps.py` — sửa: thêm `get_index`, cùng khuôn với `get_search` sẵn có (trả `None`
  khi recsys tắt lúc khởi động).
- `src/backend/app/api/v1/router.py` — sửa: đăng ký `catalog_router`.
- `src/backend/tests/unit/test_catalog_destinations.py` → `src/backend/tests/unit/api/test_catalog_destinations.py`
  — đổi tên: theo cách chia test theo tầng của nhánh release; test mount router kèm prefix `/api/v1`.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: hai test thêm ở `1f86065` chuyển từ
  `patch.object(nodes, 'get_llm')` sang tiêm `llm=` trực tiếp, vì nhánh release bỏ `get_llm()` khỏi
  `nodes.py` và bắt composition root truyền model vào.
- `history/2026-09-23-merge-release-mvp-v1-vao-feat-agent.md` — thêm: entry này.

`src/backend/app/agents/nodes.py` tự merge được: nhánh release đổi phần gọi LLM (`_chat_model`), thay đổi
của `1f86065` nằm trong `_validated_plan` — không chạm nhau.

## Quyết định

- **Lấy cấu trúc của nhánh release cho `main.py`, không giữ cách mount cũ.** Xung đột là do
  `1f86065` mount router thẳng vào app (khi đó search/recommendations tự mang prefix `/api/v1`), còn
  nhánh release gom hết vào `api/v1/router.py` và bỏ prefix ở route con. Cách mới là quy ước đã ghi
  trong `docs/prd/architecture.md` §2; giữ cách cũ sẽ tạo hai kiểu đăng ký route song song.
- **`/destinations` không phải thay đổi lệch PRD.** AGENTS.md mới yêu cầu mỗi feature gắn được vào một mã
  FR/NFR và đề xuất trước nếu lệch PRD (mục 8). Endpoint này đã có sẵn trong contract
  (`paths/catalog.yaml:95`, `schemas/catalog.yaml:368`) từ trước; việc thêm route là bù khoảng trống
  contract ↔ code, không mở rộng phạm vi sản phẩm. Nó phục vụ **FR-AGT-04** (grounding 100%: sản phẩm
  trong lịch trình phải là `productId` thật) và **FR-AGT-02** (tool calling). PRD tự trỏ về contract cho
  phần giao diện kỹ thuật (`api-contract.md` dòng 3), nên contract là căn cứ đúng ở đây.
- **Không đụng vào phần Auth và migration của nhánh release**, chỉ nhận nguyên trạng.

## Kiểm tra

- `git merge origin/release-mvp-v1`: xung đột duy nhất ở `src/backend/app/main.py`, đã giải quyết.
- `pytest src/backend/tests/unit src/backend/tests/architecture` (LANGSMITH_TRACING=false):
  **164 passed**, 68 s — gồm `tests/architecture/test_import_rules.py` mới của nhánh release.
- `python src/shared/contracts/tests/validate_contract.py`: **PASS** — 77 schema (tăng từ 70 vì có auth),
  53 fixture, negative checks.
- Chạy thật sau merge, `ITINERARY_DATA_MODE=http` + Postgres local đã seed + LLM thật:
  `src/evaluation/tests/check_real_data_grounding.py` → **22/22 sản phẩm khớp `cdp.products`, 0 lỗi**
  (exit 0). `GET /api/v1/destinations` vẫn trả 35 điểm đến / 2.897 sản phẩm.
  `tphcm 2 ngày` nay ra đủ stay + 4 hoạt động (trước merge chỉ có stay).

## Còn lại / rủi ro

- **`src/backend/README.md` của nhánh release mô tả vector store là Weaviate + Cohere** (commit
  `7610b65`), nhưng code thật vẫn là `PostgresVectorStore` đọc `cdp.products`; "weaviate/cohere" chỉ còn
  trong README và `src/backend/tests/fakes/`. Tài liệu đang mô tả thứ không chạy — chưa sửa vì ngoài
  phạm vi merge này, cần người viết commit đó xác nhận ý định.
- `db/migrations/0002_drop_product_vectors.sql` xóa bảng `product_vectors`. Chưa chạy migration trên
  database local của lần kiểm tra này; recsys không đọc bảng đó nên không ảnh hưởng kết quả trên.
- Chưa chạy `src/backend/tests/contract` và `src/backend/tests/integration` (hai suite này có lịch sử
  treo/timeout, ghi ở `history/2026-09-22-noi-agent-voi-recsys-backend.md`).
- Các rủi ro của `1f86065` vẫn còn nguyên, xem
  `history/2026-09-23-noi-lai-chuan-hoa-diem-den-o-http-mode.md` mục "Còn lại / rủi ro".
