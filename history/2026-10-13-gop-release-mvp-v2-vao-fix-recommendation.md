# Gộp origin/release-mvp-v2 vào fix/recommendation, đổi số contract của nhánh sang 1.27.0

- Ngày: 2026-10-13
- Tác giả: tqanh123 (yêu cầu merge vào release-mvp-v2, chạy localhost, rồi mở PR) / Claude Code
- Nhánh: `fix/recommendation`. Commit gộp có cùng cây với `3d059212` của nhánh local `merge/release-mvp-v2`, bản đã chạy thử localhost.
- Trạng thái: hoàn thành (mở PR vào `release-mvp-v2`)
- Phạm vi: src/backend, src/frontend, src/shared/contracts, docs
- Liên quan: `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md`, `history/2026-10-12-gop-release-mvp-v2-vao-cache-control-catalog.md` (tiền lệ đổi số contract khi gộp)

## Lý do

- `release-mvp-v2` local (8519e053) có nội dung bằng `bab57fa5`, là gốc của `fix/recommendation`.
- `origin/release-mvp-v2` (71333eee) đã có thêm khoảng 25 commit, contract lên 1.26.1.
- Người dùng chọn kéo origin vào trước rồi mới merge, để lúc push không phải giải xung đột lại.

**Thứ tự đã làm:**
1. Tạo `merge/release-mvp-v2` từ `release-mvp-v2` local. Phiên của agent bị khoá trong worktree nên không chạy git được ở thư mục repo chính.
2. Merge `origin/release-mvp-v2` vào. Merge sạch; cây sau merge trùng hệt cây của origin.
3. Merge `fix/recommendation` vào, giải 8 file xung đột → `3d059212`. Chạy test và chạy thử localhost trên bản này. Người dùng đã fast-forward `release-mvp-v2` local tới đây.
4. Để mở PR không kéo theo hai commit merge chỉ có ở local (`986b2bec`, `8519e053`): merge `origin/release-mvp-v2` thẳng vào `fix/recommendation`, lấy đúng nội dung đã giải ở `3d059212` cho 22 file. Cây kết quả trùng `3d059212`, chỉ khác tên file entry này.

## Xung đột và cách giải

- `src/shared/contracts/openapi.yaml`, `src/backend/app/main.py`: phiên bản **1.27.0**.
  - Origin đã dùng 1.25.0 (tư vấn vé máy bay, FR-AGT-07), 1.26.0 (ô sở thích) và 1.26.1 (`Cache-Control` cho catalog).
  - Thay đổi của nhánh thêm tham số tuỳ chọn (`diversify`, `taxonomy` nhiều giá trị), nên là bản minor kế tiếp.
- `src/backend/tests/contract/test_search_contract.py`, `test_search_llm_contract.py`: số phiên bản 1.27.0.
- `src/shared/contracts/paths/catalog.yaml`: giữ cả hai câu mô tả, `Cache-Control` của origin và `diversify` của nhánh.
- `src/backend/app/api/v1/routes/catalog.py`: gộp `response: Response` cùng header `Cache-Control` (origin) với `diversify` và tách `taxonomy` theo dấu phẩy (nhánh). Header vẫn chỉ gắn sau khi use case thành công.
- `src/backend/tests/contract/test_catalog_contract.py`: giữ cả hai nhóm test, `Cache-Control` và `diversify`/nhiều taxonomy.
- `src/frontend/src/types/api.gen.ts`: sinh lại bằng `npm run generate:api-types` từ contract đã gộp.

## Đổi số contract của nhánh: 1.25.0 → 1.27.0

Chỉ đổi các dòng nói về thay đổi của nhánh này. Các dòng 1.25.0 của origin (tư vấn vé máy bay) giữ nguyên.

- `src/shared/contracts/paths/catalog.yaml` (mô tả `taxonomy`, `diversify`), `src/shared/contracts/schemas/recommendations.yaml` (dòng P3 đã áp dụng).
- `src/backend/app/domain/catalog/listing.py`, `src/backend/app/application/catalog/use_cases.py` (docstring, comment).
- `src/backend/tests/unit/domain/test_catalog_listing.py`, `src/backend/tests/unit/application/test_catalog_use_cases.py` (comment).
- `src/frontend/src/services/catalog.ts`, `src/frontend/src/components/home/HomeView.tsx`, `src/frontend/tests/unit/catalogService.test.ts` (comment, tên test).
- `docs/spec/hop-dong-tich-hop-backend.md` §4.1, `docs/spec/hop-dong-tich-hop-frontend.md` (hàng ④), `docs/spec/product.md` (hàng ④), `docs/spec/hop-dong-tich-hop-search-recommendation.md` (S5).
- `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md`: số contract. Hai câu về `compose.ha.yml` được sửa vì origin đã xoá file này; biến của secret giờ đi qua compose do `slot-deploy.sh` sinh, vẫn có `env_file: /etc/vota/backend.env`, nên không cần sửa hạ tầng.

**Chỗ không sửa:** các entry `history/2026-10-12-*.md` của nhánh và đề xuất đã lưu trữ `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md` vẫn ghi "1.25.0". Quy tắc không cho sửa entry cũ hay `docs/prd/` ngoài bước áp dụng. Số đó chính là bản 1.27.0 hiện nay.

Các file khác của hai nhánh được gộp nguyên. Đã kiểm thủ công các file cả hai bên cùng sửa: `.env.example` và `docker-compose.yml` (DB index Redis không trùng: 1 auth và session, 2 trợ lý, 3 giỏ khách, 4 cache gợi ý), `core/config.py`, `main.py` (đủ phần orchestrator của origin và cache, làm ấm của nhánh), `ProductCard.tsx`, PRD `architecture.md` và `deployment-plan.md`.

## Kiểm tra

- `python src/shared/contracts/tests/validate_contract.py`: PASS (120 schema, 97 fixture).
- `pytest -q -p no:cacheprovider src/backend/tests src/evaluation/recsys_bench/tests`: 3222 passed, 46 skipped.
- Frontend:
  - `npm run lint`: 0 lỗi, 3 cảnh báo có sẵn ở `ItineraryMap.tsx` và `useFloatingWidget.ts`;
  - `npm run typecheck`: đạt;
  - `npm run test`: 81 file, 848 passed.

## Môi trường local (không phải thay đổi trong repo)

- Người dùng đồng ý áp 6 migration chờ (0005–0010) lên DB `vota` của Postgres local 5432.
- `db/migrations/run.py` lỗi trên Windows vì gọi `os.uname()`. Đã chạy qua một shim lúc chạy, không sửa code.

## Còn lại

- **PR vào `release-mvp-v2`:** chờ review và CI. Sau khi PR được merge trên GitHub, `release-mvp-v2` local (đang ở `3d059212`) sẽ lệch với origin; đồng bộ lại bằng `git reset --hard origin/release-mvp-v2` ở thư mục repo chính, vì nội dung giống nhau.
- **Secret:** `RECOMMEND_CACHE_REDIS_URL` chưa thêm vào `vota-ha-backend-env`, vì tài khoản `tqanh6203tkqn@gmail.com` thiếu quyền Secret Manager. Chưa có biến này thì cache gợi ý trên VM tắt, các phần khác vẫn chạy.
- **Lỗi riêng:** `db/migrations/run.py` không chạy được trên Windows (`os.uname`). Nên sửa ở một thay đổi riêng.
