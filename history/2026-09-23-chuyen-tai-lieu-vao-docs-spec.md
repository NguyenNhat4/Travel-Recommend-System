# Khôi phục tài liệu đã xoá và chuyển mọi tài liệu ngoài docs/ vào docs/spec

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs
- Thay thế: 2026-09-23-prd-la-tai-lieu-goc-va-noi-dat-tai-lieu.md (chỉ phần xoá 4 file và quyết định không khôi phục `MVP.md`)

## Mục tiêu

Người dùng yêu cầu: khôi phục các file đã xoá ở commit `d23b682` và chuyển chúng vào `docs/spec/`. Các tài liệu còn nằm ngoài `docs/` cũng chuyển hết vào `docs/spec/`, theo `AGENTS.md` §7.

## File thay đổi

- `docs/spec/architecture-repo.md` — thêm: khôi phục `src/ARCHITECTURE.md` (bản ở `7610b65`). Thêm dòng đầu ghi PRD thắng khi lệch; bỏ `product_vectors` (đã gỡ ở migration 0002); sửa đường dẫn `docs/DATABASE_SCHEMA.md` → `docs/spec/DATABASE_SCHEMA.md`.
- `docs/spec/mvp-minimal-fields-1.2.0.md` — thêm: khôi phục `src/shared/contracts/MVP.md`, sửa link fixture.
- `docs/spec/contracts-guide.md` — thêm: khôi phục `src/shared/contracts/README.md`, sửa link tương đối.
- `docs/spec/shared-assets.md` — thêm: khôi phục `src/shared/README.md`, sửa link.
- `src/data_collection/docs/SCHEMA.md` → `docs/spec/data-collection/schema.md` — đổi tên/chuyển.
- `src/data_collection/docs/BANGIAO.md` → `docs/spec/data-collection/ban-giao.md` — đổi tên/chuyển, sửa tên tự tham chiếu.
- `src/data_collection/docs/EXPAND_CATALOG.md` → `docs/spec/data-collection/expand-catalog.md` — đổi tên/chuyển.
- `src/data_collection/docs/bao-cao-ban-giao.md` → `docs/spec/data-collection/bao-cao-ban-giao.md` — chuyển, sửa tên `BANGIAO.md`.
- `src/data_collection/docs/bao-cao-schema.md` → `docs/spec/data-collection/bao-cao-schema.md` — chuyển, sửa link.
- `src/data_collection/docs/test.json` → `docs/spec/data-collection/vi-du-san-pham.json` — đổi tên/chuyển (bản ghi sản phẩm mẫu, không có code nào đọc).
- `mvp/bao-cao-mvp.md`, `mvp/index.html` → `docs/spec/mvp/` — chuyển, sửa link `../docs/spec/` và câu nói vị trí thư mục.
- `AGENTS.md` — sửa: đường dẫn `SCHEMA.md` mới (bảng §1.2, §6.1); bảng §1.2 thêm `contracts-guide.md`, `mvp-minimal-fields-1.2.0.md`, `shared-assets.md`, `architecture-repo.md`; thứ tự ưu tiên §2 thêm lại bộ trường tối thiểu và `architecture-repo.md` (sau PRD); §7 bỏ câu "tài liệu cũ ngoài ba thư mục chỉ chuyển khi cần sửa" vì đã chuyển hết.
- `docs/spec/contract-baseline-v1.1.md`, `hop-dong-tich-hop-backend.md`, `hop-dong-tich-hop-frontend.md`, `hop-dong-tich-hop-itinerary-assistant.md`, `hop-dong-tich-hop-auth.md`, `mvp-v01.md`, `thiet-ke-schema-3-service.md`, `agent/evaluation-plan.md`, `ra-soat-hop-dong-2026-09-17.md`, `ra-soat-hop-dong-2026-09-17.html`, `research/recsys-data-cleaning-embedding-strategy.md` — sửa: link/tham chiếu `MVP.md`, `ARCHITECTURE.md`, `SCHEMA.md`, `EXPAND_CATALOG.md` sang vị trí mới.
- `src/backend/app/main.py`, `src/backend/app/application/ports/auth.py` — sửa docstring: `ARCHITECTURE.md §5` → `docs/prd/architecture.md §2`.
- `src/data_collection/README.md`, `src/data_collection/sample/README.md`, `src/data_collection/make_template.py` — sửa: đường dẫn tới `schema.md`/`ban-giao.md` mới (trong `make_template.py` chỉ đổi chuỗi mô tả `_doc_them`).
- `history/2026-09-23-prd-la-tai-lieu-goc-va-noi-dat-tai-lieu.md` — sửa: thêm dòng `Bị thay thế bởi`.

## Quyết định

- Tên file mới viết thường, dùng gạch nối (`AGENTS.md` §7); tài liệu của Data gom vào `docs/spec/data-collection/`, báo cáo MVP vào `docs/spec/mvp/`.
- Giữ lại README của từng workstream trong `src/`, `db/migrations/README.md` và `src/frontend/AGENTS.md`/`CLAUDE.md`, vì đây là ngoại lệ của §7 (hướng dẫn chạy và cấu hình agent).
- Không sửa các câu chỉ kể lại lịch sử: `ra-soat` §nguồn "Git local `origin/data_contract`: `src/ARCHITECTURE.md`", các lệnh `git show …MVP.md` trong `bao-cao-mvp`, cây thư mục trong handbook.
- Không sửa comment `ARCHITECTURE §8` trong `db/*.sql` và `docs/spec/DATABASE_SCHEMA.md` để tránh chạm DDL chỉ vì một comment.
- `data/SCHEMA.md` trong `src/data_collection/README.md` là file sinh ra lúc chạy, nên giữ nguyên.

## Kiểm tra

- `python3 -m py_compile` cho 3 file Python đã sửa: pass.
- Quét link tương đối trong `docs/spec/`, `AGENTS.md`, README của `src/`: các file đã chuyển/khôi phục không có link hỏng mới. Link hỏng còn lại `so-do-mvp.svg` đã thiếu từ trước khi chuyển.
- Không chạy `validate_contract.py`: không đổi contract/mock.

## Còn lại / rủi ro

- Nhánh khác đang sửa `src/data_collection/docs/*` hoặc `mvp/*` sẽ bị conflict khi merge; cần chuyển thay đổi sang đường dẫn mới.
- `docs/spec/architecture-repo.md` trùng một phần với `docs/prd/architecture.md` §2, §6. Khi sửa quy tắc kiến trúc, sửa PRD trước.
- Còn các link hỏng đã có từ trước, ngoài phạm vi task này (`diagrams/*` trong một số spec, `src/evaluation/agent/README.md` → `docs/agent/README.md`).
