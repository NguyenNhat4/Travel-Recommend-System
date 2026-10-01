# Tự cào fresh sau deploy, giữ lượt đang chạy

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người dùng hỏi số vé thực trong DB, vé khứ hồi và yêu cầu deploy lên tự động cào luôn. Cập nhật CI/CD để phát hành đúng image fresh, khởi động full sau deploy và giữ yêu cầu nếu lượt cũ còn chạy. Không restart VM, monitor hoặc batch đang chạy.

Thay thế quyết định giữ CI/CD legacy trong `2026-09-30-hang-ve-khu-hoi-trip-va-daily-tu-cap-nhat.md` theo yêu cầu mới. Phần DB được xử lý riêng trong `2026-09-30-sua-db-vm-migration-va-bo-sung-catalog.md`.

## File thay đổi

- `.github/workflows/crawler-ci-cd.yml` — sửa: CI build cả daily/fresh, test deploy/cron; publish image fresh riêng; gọi helper deploy fresh thay bước monitor cũ; giữ nhánh CD main/release-mvp-v1/v2/v3.
- `Dockerfile.fresh-catalog.dockerignore` — sửa: chỉ đưa thêm gói business có checksum vào image; tiếp tục loại snapshot khác/runtime/secret. Smoke CI kiểm gói bên trong cả hai image.
- `scripts/deploy-crawler-vm.sh` — thêm: pull image SHA, import gói business bằng image fresh, cài cron fresh duy nhất, ghi request và dispatch nền. Kiểm thư mục/env đã provision; không tự tạo secret/DB.
- `scripts/tests/test-crawler-deploy.sh` — thêm: fake Docker/crontab, dùng helper/runner/installer thật; rảnh, bận, lỗi, yêu cầu mới, giữ cron ngoài phạm vi và không stop/restart.
- `src/data_collection/run_daily_docker.sh` — sửa: tick/auto/full nhận deploy-pending, pin image; phát hiện cả batch fresh và legacy; chỉ xóa request tương ứng sau exit 0, khóa file để không mất request mới.
- `src/data_collection/README.md` — sửa: mô tả CI fresh và request sau deploy; sửa mô tả daily image đã có Chromium.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: luồng CD fresh hiện hành, paths/secrets tùy chọn, yêu cầu full/cron, điều kiện VM và monitor không restart.
- `docs/guide/ve-thuong-gia-va-index-cho.md` — sửa: import trước full, workflow fresh và liên kết deploy.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — sửa: ghi quyết định crawler mới ngày 30/09, tách khỏi phần backend không đổi.
- `history/2026-09-30-tu-dong-cao-fresh-sau-deploy.md` — thêm: entry này.

Giữ các thay đổi dirty khác của task trước; không commit/push trong phiên này.

## Quyết định

- FR-CAT-01/03, FR-SRC-02, NFR-REL-01. Không đổi PRD, contract, DDL hay model embedding. PRD cho phép job nạp/index và lịch vận hành; spec CI đã cho phép yêu cầu crawl nền sau deploy, cập nhật triển khai từ legacy sang fresh.
- Đã đọc PRD README/requirements/deployment/test-plan/architecture và các spec liên quan trong task này/chuỗi trước; lịch sử migration, booking, snapshot/CD 21–30/09; guide deploy, script cron/runner, workflow và spec CI/CD ngày 24/09.
- Image fresh dùng `${GAR_DAILY_IMAGE}-fresh:<sha>` và `:latest`, cùng Artifact Registry đã cấu hình. Daily vẫn được publish để giữ đường legacy/rollback; không đổi bí mật registry.
- Dùng paths fresh hiện có; override qua `GCE_FRESH_DATA_DIR`, `GCE_FRESH_ENV_FILE`, `GCE_FRESH_LOG_DIR`, runner qua `GCE_CRON_RUNNER`. Cấu hình legacy data/env không dùng cho fresh.
- Cron thay cùng một khối quản lý bằng `--job fresh`, không tạo lịch thứ hai. Full sau deploy là yêu cầu thủ công có lưu file, được tick xử lý kể cả ngoài giờ lịch; giờ chạy thường lệ trong monitor vẫn áp sau khi request hoàn tất.
- Không coi CD dispatch thành công là crawl/index thành công. Lỗi pull/import không ghi cron/request mới; lỗi crawl giữ request cho tick sau. Quota deferred/source incomplete có dữ liệu hợp lệ dùng exit 0 theo bản sửa trước, report vẫn partial.
- Monitor hiện có giữ nguyên image/code, đọc cùng volume để theo dõi. Không gọi stop/rm/restart container hiện hữu; batch trước tự kết thúc rồi lượt mới dùng image mới.

## Kiểm tra

- Truy vấn chỉ đọc VM xác nhận: 43 BUSINESS oneWay available; 493 oneWay UNKNOWN; 560 roundTrip (268 ECONOMY, 292 UNKNOWN), trong đó 357 available; 113 route. 17 chỉ là business tuyến HAN-SGN. Chưa có BUSINESS roundTrip.
- `bash scripts/tests/test-crawler-deploy.sh`: PASS (rảnh chạy ngay, bận giữ request, tick chuyển full và pin SHA, failure giữ request, request image mới không bị xóa, pull/import fail giữ cron, không stop/restart).
- `bash scripts/tests/test-install-vota-cron.sh`: PASS (một khối cron, giữ dòng ngoài phạm vi, chuyển fresh/legacy).
- YAML parser + `bash -n` toàn bộ run blocks workflow và các shell sửa/thêm: PASS.
- Smoke đầu phát hiện fresh dockerignore loại gói business; đã thêm ngoại lệ đúng gói và thêm smoke vào CI. Build `Dockerfile.fresh-catalog` local với runner cuối: PASS. Smoke image `--network none`, `release_flights --validate-only`: 43 vé / 6 tuyến PASS.
- Bộ data collection trước thay đổi shell này: 435 PASS / 6 SKIP; không sửa Python trong task deploy, không tuyên bố đã chạy lại toàn bộ.
- `git diff --check`: PASS.

## Còn lại / rủi ro

- Chưa push hoặc chạy GitHub Actions/SSH app VM: người dùng chỉ có quyền DB. Tự cào có hiệu lực khi thay đổi được đưa vào nhánh CD và deploy thành công với secret/VM đã cấu hình.
- Key mới vẫn chỉ thay local; người có quyền VM cần cập nhật env file để lượt mới dùng key mới. Workflow không đóng gói/truyền key qua command line.
- Dữ liệu cào thực tế phụ thuộc quyền truy cập nguồn và công tắc nguồn hiện có. Chưa chứng minh headless crawl trên VM bằng các test giả lập.
- Monitor code cũ giữ nguyên theo yêu cầu không restart; cập nhật monitor cần thao tác riêng khi được phép.
