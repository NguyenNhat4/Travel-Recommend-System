# Merge release-mvp-v2 vào feat/recSys_update: giữ CI của release (PR #139)

- Ngày: 2026-10-10
- Tác giả: Khoa15 / Claude Code (Haiku 5.5)
- Nhánh: feat/recSys_update (PR #139 → release-mvp-v2)
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD `.github/`) · recsys (đồng bộ nhánh)

## Mục tiêu

PR #139 (`feat/recSys_update` → `release-mvp-v2`) báo `CONFLICTING`, GitHub không merge được. Đưa nhánh feat về trạng thái merge được, không đẩy CI cũ của nhánh lên release.

## Nguyên nhân

Từ merge-base `d8a86ac2` (08/10) hai nhánh cùng sửa `.github/workflows/`:

- `feat/recSys_update`: `cabba9a9` (chuyển runner sang self-hosted) và `cace980d` (khôi phục workflow của release nhưng vẫn là bản cũ, trước các commit staging-ha của release).
- `release-mvp-v2`: loạt commit staging-ha 09–10/10 (`0ce6c824` … `4b4b3e0b`, `29f1afd6`, `096a7fff`, `c6a90946`): CD có `window-guard`, build image một lần, deploy theo digest, bỏ tag `:latest`.

Ba file `staging-ha-{backend,frontend,crawler}-cd.yml` được tạo ở cả hai nhánh (add/add), nên không tự merge được. Hai file `backend-ci-cd.yml`, `frontend-ci-cd.yml` sửa cùng hunk.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — xung đột: lấy bản `release-mvp-v2`.
- `.github/workflows/frontend-ci-cd.yml` — xung đột: lấy bản `release-mvp-v2`.
- `.github/workflows/staging-ha-backend-cd.yml` — add/add: lấy bản `release-mvp-v2`.
- `.github/workflows/staging-ha-frontend-cd.yml` — add/add: lấy bản `release-mvp-v2`.
- `.github/workflows/staging-ha-crawler-cd.yml` — add/add: lấy bản `release-mvp-v2`.
- `.github/` còn lại (`crawler-ci-cd.yml`, `dependabot.yml`, `staging-ha-{backend,frontend}-build.yml`) — khớp `release-mvp-v2` (đồng bộ cả thư mục; không có file nào chỉ tồn tại ở feat).
- 342 file ngoài `.github/` (`src/`, `docs/`, `db/`, `infra/`, `ops/`, `scripts/`, `history/`, …) — thay đổi của `release-mvp-v2` được git tự merge, không xung đột. Danh sách tái tạo: `git diff --name-only origin/feat/recSys_update HEAD -- ':!.github'`.
- `history/2026-10-10-merge-release-mvp-v2-vao-recsys-pr139.md` — file này.

## Quyết định

- **Lấy CI của `release-mvp-v2` cho toàn bộ `.github/`.** Bản feat là snapshot cũ của cùng việc; commit gần nhất của nhánh (`cace980d`) đã ghi mục tiêu "khôi phục workflow của release-mvp-v2".
- Không mất sửa tương thích runner tự host mà feat có: release đã có đủ — `setup-python` có điều kiện, `python3 -m pip`, `PIP_BREAK_SYSTEM_PACKAGES`, Playwright dùng `tool_cache`, bỏ `--with-deps` trên runner tự host (`0df738e1`, `6cedddea`, `1e2ebfd1`).
- Hệ quả: PR #139 **không đổi nội dung CI** so với `release-mvp-v2`; CD staging-ha của release không đổi.
- Merge commit thường, không force push, không rewrite lịch sử.

## Kiểm tra

- `git diff origin/release-mvp-v2 HEAD -- .github/` rỗng; không còn marker `<<<<<<<` trong file đã merge.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → PASS (120 schemas, 94 fixtures, CDP clone 12 schemas / 7 fixtures).
- `bash scripts/tests/test-backend-vm-cd-sync.sh` → passed.
- `bash scripts/tests/test-install-vota-cron.sh` → passed.
- `python -m pytest -q src/backend/tests` → 2640 passed, 36 skipped. Máy là x86_64 nên không có wheel `torch>=2.3`, đã cài `torch==2.2.2` thay thế; test không cần torch (`src/backend/requirements-embed.txt`).
- `ops/tests/test_cluster_probe.py` → 7 passed.
- `src/data_collection/tests` (bốn file như job `ha-checks`) → 76 passed, 1 skipped.
- `src/frontend` (macOS): `npm ci` OK; `generate:api-types` không đổi file đã commit; `vitest run` → 815 passed, 1 failed. Test lỗi là `tests/unit/floatingWidgetOpening.test.tsx` › "prefills a suggestion…", và chạy riêng trên `origin/release-mvp-v2` cũng lỗi y hệt (`Element type is invalid … got: undefined`) — lỗi có sẵn trên release, không do merge này.
- `src/frontend` `typecheck` (macOS) → exit 2, chỉ có lỗi ở `WidgetChat.tsx` do cặp file `widget/WidgetProgress.tsx` và `widget/widgetProgress.ts` (xem Còn lại). Cùng cặp file này có sẵn ở `d8a86ac2`, `release-mvp-v2` và `feat/recSys_update`.

## Còn lại / rủi ro

- CI thật trên PR #139 (runner `vota-staging-ha`, Linux) chưa chạy; kiểm lại sau khi push.
- **Cặp file trùng tên khác hoa/thường** trong `src/frontend/src/features/itinerary/widget/`: `WidgetProgress.tsx` + `widgetProgress.ts`. Trên FS không phân biệt hoa thường (macOS mặc định) hai file này là một; `import … from './WidgetProgress'` resolve nhầm sang `widgetProgress.ts` → `typecheck` lỗi TS2305/TS1149 và test `floatingWidgetOpening` lỗi runtime. Linux (CI) không bị. Chưa sửa: đổi tên là thay đổi `src/frontend` ngoài phạm vi conflict, cần người phụ trách widget quyết tên file.
- Chưa chạy local: frontend lint/e2e/build, docker build, test cần Postgres (`CATALOG_TEST_DATABASE_URL`), `db/verify.sql`.
- PR mang theo mặc định search production mới (`src/backend/app/core/config.py`: F1/F2/F3/F5/F6 bật). Merge không đổi giá trị đó; người review cần xác nhận lại khi merge vào release.
