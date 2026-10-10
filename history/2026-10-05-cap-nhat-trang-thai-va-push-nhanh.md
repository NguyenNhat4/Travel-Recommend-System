# Cập nhật trạng thái và đóng gói nhánh hiện tại

- Ngày: 2026-10-05
- Tác giả: người dùng / Codex
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành (đóng gói cập nhật; triển khai/CDP còn mở)
- Phạm vi: docs, data, evaluation

## Mục tiêu

Theo yêu cầu người dùng, cập nhật trạng thái thật và commit/push những thay đổi hiện có lên nhánh hiện tại. Không coi push là deploy hoặc hoàn thành làm giàu CDP.

## File thay đổi

Bản đóng gói bao gồm các thay đổi có sẵn của những task trước; quyết định triển khai gốc xem các entry 02/10 về crawler/lịch phòng và 05/10 về Search/latency. Task này bổ sung bản trạng thái, chỉnh hai dòng checklist, làm rõ e5-small chỉ chạy benchmark và thêm entry này.

- `docs/plan/2026-10-05-trang-thai-search-cdp-replica.md`
- `docs/prd/update/2026-10-05-tach-ket-noi-doc-replica.md`
- `history/2026-10-02-mo-lich-phong-30-ngay-va-sua-khoa-trinh-duyet.md`
- `history/2026-10-02-toi-uu-crawler-vm-va-bo-sung-phong.md`
- `history/2026-10-05-de-xuat-doc-replica.md`
- `history/2026-10-05-recsys-web-latency.md`
- `history/2026-10-05-search-day5-e5s-app-cutoff-regress.md`
- `src/evaluation/reports/eval-2026-10-05-recsys-web-latency.md`
- `src/evaluation/reports/eval-2026-10-05-search-day5-e5s-app.md`
- `src/evaluation/reports/report_week_3_search.md`
- `src/evaluation/search_bench/arms/APP.e5s.dense.yaml`
- `src/evaluation/search_bench/arms/APP.e5s.dense_nocut.yaml`
- `src/evaluation/search_bench/arms/APP.e5s.hybrid.yaml`
- `src/evaluation/search_bench/arms/APP.e5s.hybrid_nocut.yaml`
- `src/evaluation/search_bench/arms/APP.e5s.hybrid_norm.yaml`
- `src/evaluation/search_bench/arms/APP.e5s.hybrid_norm_nocut.yaml`
- `src/evaluation/search_bench/devtest.py`
- `src/evaluation/search_bench/gold/holes/gold_v3__D6a/auto_ooc.csv`
- `src/evaluation/search_bench/gold/holes/gold_v3__D6a/holes.json`
- `src/evaluation/search_bench/gold/holes/gold_v3__D6a/meta.csv`
- `src/evaluation/search_bench/gold/holes/gold_v3__D6a/pool_A.csv`
- `src/evaluation/search_bench/gold/holes/gold_v3__D6a/pool_B.csv`
- `src/evaluation/search_bench/gold/holes/gold_v3__D6a/pool_meta.json`
- `src/evaluation/search_bench/gold/splits/devtest@gold_v3.json`
- `src/evaluation/search_bench/regress.py`
- `src/evaluation/search_bench/regression/baseline_v1.json`
- `src/evaluation/search_bench/tests/test_devtest_regress.py`
- `AGENTS.md`
- `Dockerfile.fresh-catalog.dockerignore`
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`
- `docs/plan/2026-10-01-chia-task-day4-search-rec.md`
- `docs/plan/2026-10-01-plan-day4-5.md`
- `docs/spec/DATABASE_SCHEMA.md`
- `docs/spec/MOCK_DATA_SPEC.md`
- `docs/spec/PRODUCT_SCHEMA.md`
- `docs/spec/bench/arms.md`
- `docs/spec/bench/search-eval-local-spec.md`
- `src/data_collection/README.md`
- `src/data_collection/collectors/common.py`
- `src/data_collection/fresh_catalog.py`
- `src/data_collection/fresh_catalog_db.py`
- `src/data_collection/fresh_settings.py`
- `src/data_collection/run_daily_docker.sh`
- `src/data_collection/seed/catalog_meta.py`
- `src/data_collection/seed/config.py`
- `src/data_collection/seed/load_products.py`
- `src/data_collection/seed/parse_combos.py`
- `src/data_collection/seed/seed_histories.py`
- `src/data_collection/tests/test_fresh_catalog_job.py`
- `src/data_collection/tests/test_seed_load_products.py`
- `src/data_collection/tests/test_seed_parse_combos.py`
- `src/evaluation/search_bench/__main__.py`
- `src/evaluation/search_bench/app_adapter.py`
- `src/evaluation/search_bench/config/sbench.yaml`
- `src/evaluation/search_bench/tests/test_app_adapter.py`
- `history/2026-10-05-cap-nhat-trang-thai-va-push-nhanh.md`

## Quyết định

- Người dùng yêu cầu push nhánh hiện tại; không tạo PR, không merge main, không deploy VM.
- Loại .claude/launch.json khỏi commit theo lịch sử latency vì là launcher local.
- Đề xuất replica giữ chờ chốt; yêu cầu cập nhật/push không được diễn giải là phê duyệt kiến trúc.
- Dữ liệu hành vi chưa bổ sung, staging chưa ghi, số benchmark chưa đo lại.

## Kiểm tra

- PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/dangkhoi/miniconda3/envs/vsf2/bin/python -m pytest src/data_collection/tests/test_fresh_catalog_job.py src/data_collection/tests/test_seed_load_products.py src/data_collection/tests/test_seed_parse_combos.py src/evaluation/search_bench/tests -q -k 'not test_share_dry_run_writes_launcher_outside_git_and_codes': 421 passed, 11 skipped, 1 deselected; 1 fail do sandbox cấm socket.
- Chạy lại test_gold_cli.py::test_machine_import_cli_refuses_while_app_listens_and_writes_when_stopped ngoài sandbox: 1 passed.
- PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py: PASS.
- git diff --check: PASS cho diff đã có; sau stage, CSV D6a dùng CRLF bị báo whitespace. Kiểm lại với core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol: PASS; giữ nguyên byte CSV để không đổi checksum artifact.
- Rà mẫu credential trên file đóng gói: chỉ phát hiện URL demo/placeholder; không đưa thông tin kết nối được cung cấp trong chat vào Git.
- git fetch origin: thành công; nhánh hiện tại không lệch remote trước commit.
- Chưa chạy db/verify.sql trong task này: chưa có DB đích phù hợp, không sửa/reset DB benchmark đóng băng.

## Còn lại / rủi ro

- Chưa xác minh DB staging/replica do SSH Connection refused; không khẳng định nguyên nhân là VM.
- Xem docs/plan/2026-10-05-trang-thai-search-cdp-replica.md về việc tiếp tục làm giàu CDP và các gate còn thiếu.
- Các thay đổi seed/crawler chưa được xác nhận deploy; unit test không thay thế DB verify.
