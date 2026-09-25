# Gộp lịch sử thay đổi ngày 2026-09-24

Các entry Markdown trong `history/` của working tree ngày 2026-09-24 được gom theo parent folder. Nội dung nguồn được giữ nguyên dưới các marker để không mất quyết định và bằng chứng.

<!-- BEGIN SOURCE: history/2026-09-24-ci-cd-latest-deploy.md -->

# CI/CD publish và chạy image latest

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: dang dở — đã sửa và kiểm tra local; chưa chạy GitHub Actions hoặc deploy thật lên VM
- Phạm vi: backend, data collection, CI/CD

## Mục tiêu

Sau mỗi lần publish, Backend và crawler dùng image `:latest` trên Artifact Registry; Backend được health-gate, crawler pull image mới trước mỗi lượt cron.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — publish thêm tag `latest`, deploy truyền image `latest`.
- `scripts/deploy-backend-vm.sh` — nhận `latest`, chỉ force-recreate Backend, rollback bằng repository digest trước đó.
- `scripts/install-vota-cron.sh` — cron dùng `latest` và `PULL=1`.
- `scripts/tests/test-backend-ci-cd-config.sh` — kiểm tra tag/latest deploy.
- `scripts/tests/test-deploy-backend-vm.sh` — fixture image `latest`.
- `scripts/tests/test-install-vota-cron.sh` — kiểm tra `PULL=1`.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — đồng bộ chính sách image `latest`.
- `docs/plan/2026-09-24-backend-cicd-cron.md` — đồng bộ kế hoạch kiểm tra/publish/deploy.
- `history/2026-09-24-ci-cd-latest-deploy.md` — entry này.

## Quyết định

- Workflow push cả `${GITHUB_SHA}` và `latest` cho Backend/Crawler.
- VM chạy `latest`; trước khi cập nhật, deploy script capture `RepoDigests` của Backend đang chạy để rollback không phụ thuộc tag mutable.
- Crawler vẫn là one-shot job qua cron, không chạy thành service dài hạn; cron đặt `PULL=1`.
- Không chạm PostgreSQL VM, volume, frontend hoặc secret.

## Kiểm tra

- TDD red: các test latest fail đúng vì implementation cũ bắt buộc digest.
- `bash scripts/tests/test-install-vota-cron.sh` — PASS.
- `bash scripts/tests/test-deploy-backend-vm.sh` — PASS.
- `bash scripts/tests/test-backend-ci-cd-config.sh` — PASS.
- `bash -n scripts/*.sh scripts/tests/*.sh` — PASS.
- PyYAML parse workflow — PASS.
- Contract validator — PASS: 77 schemas, 53 fixtures và CDP checks.
- `python3 -m compileall -q src/backend src/data_collection` — PASS.
- `python3 -m pytest -q src/backend/tests` — 204 passed, 2 skipped; có warning LangSmith network ngoài phạm vi test.

## Còn lại / rủi ro

- Workflow và script còn cần commit/push lên `dev`.
- Cần khai báo GitHub Environment `staging`, IAM WIF/Artifact Registry Reader/Writer, target VM và Compose path.
- Chưa chứng minh GitHub Actions publish hoặc VM health/cron runtime thật.

<!-- END SOURCE: history/2026-09-24-ci-cd-latest-deploy.md -->

<!-- BEGIN SOURCE: history/2026-09-24-remove-local-embedding-weight.md -->

# Bỏ local embedding weight khỏi Backend

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Backend đã dùng Cohere `embed-multilingual-v3.0` và Weaviate để tạo/lưu vector,
nên không còn cần tải hoặc giữ local Hugging Face weight trong image Backend.

## File thay đổi

- `Dockerfile.backend` — bỏ Hugging Face cache, OpenMP/libgomp và bước cài PyTorch riêng.
- `src/backend/app/core/config.py` — bỏ cấu hình cache embedding local không còn được dùng.
- `src/backend/app/infrastructure/embeddings/sentence_transformers_embedder.py` — xóa adapter local weight đã không còn caller.
- `src/backend/tests/architecture/test_import_rules.py` — bỏ các thư viện local embedding khỏi danh sách SDK bị cấm import.
- `history/2026-09-24-remove-local-embedding-weight.md` — thêm entry này.

## Quyết định

- Giữ `embed_model` và `embed_dimension` vì đây là model ID/chiều vector của Cohere.
- Giữ `CohereEmbedder`, `WeaviateVectorStore`, job `embed_products.py` và cấu hình Weaviate.
- Không sửa các file đang có merge conflict từ trước.

## Kiểm tra

- Sẽ kiểm tra không còn reference active tới `SentenceTransformer`, `sentence_transformers`, `torch`, `HF_HOME` hoặc `EMBED_CACHE_DIR` trong Backend image definition/source.
- Chưa rebuild/recreate container trong task này.

## Còn lại / rủi ro

- Container đang chạy hiện tại vẫn là image cũ; cần rebuild/recreate riêng để runtime ngừng dùng weight cũ.

<!-- END SOURCE: history/2026-09-24-remove-local-embedding-weight.md -->

<!-- BEGIN SOURCE: history/2026-09-24-thiet-ke-cicd-backend-crawler-timer.md -->

# Thiết kế CI/CD Backend và cron crawler

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: dang dở — đang chờ người dùng duyệt spec thiết kế trước khi viết plan và source
- Phạm vi: backend, data collection, CI/CD

## File thay đổi

- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — thêm thiết kế CI/CD và cron crawler.
- `history/2026-09-24-thiet-ke-cicd-backend-crawler-timer.md` — ghi phạm vi và trạng thái chờ duyệt.

## Quyết định

- Chọn GitHub Actions → Artifact Registry → GCP Compute Engine/VPS Docker.
- Tái sử dụng cron và runner hiện có trong `src/data_collection`; không thêm systemd timer để tránh lịch chạy trùng.
- VM là shared runtime: CI/CD chỉ deploy in-place, không gọi stop/reset/start VM, không `docker compose down`, không đụng PostgreSQL/Weaviate/Redis; chỉ restart đúng Backend service khi image đổi.
- PostgreSQL là image/container ở VM DB riêng; VM ứng dụng chỉ chạy Backend/Crawler và nhận DSN qua env/secret, không kéo hay khởi động database.
- Backend/Crawler kết nối PostgreSQL qua SSH tunnel local loopback từ VM ứng dụng tới VM DB; tunnel là process long-running có reconnect, không phải lịch crawler và không chạy trên GitHub Actions.
- Không tự suy đoán VM, zone, repository image backend hoặc secret; các giá trị này sẽ là cấu hình bắt buộc của environment.
- Không chạy crawl live hoặc chạm staging DB trong CI/CD.

## Kiểm tra

- Đã đọc deployment plan, test plan, backend README, data collection README và runner `run_daily_docker.sh`.
- Khảo sát chỉ-đọc xác nhận repo hiện chưa có `.github/workflows`.
- Truy vấn danh sách Artifact Registry repository đã thử nhưng timeout; không dùng kết quả chưa xác nhận.

## Còn lại

- Người dùng duyệt spec.
- Viết implementation plan, sau đó mới tạo workflow, cron bootstrap tùy chọn và deploy scripts.

<!-- END SOURCE: history/2026-09-24-thiet-ke-cicd-backend-crawler-timer.md -->

<!-- BEGIN SOURCE: history/2026-09-24-toi-uu-image-data-collection.md -->

# Tối ưu image Docker data collection

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `release-mvp-v1`
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Đóng gói daily data pipeline thành image nhỏ hơn để đẩy lên Artifact Registry, không mang dữ liệu runtime, test, tài liệu hoặc secret vào image.

## File thay đổi

- `Dockerfile.daily` — sửa: COPY theo allowlist runtime, giữ nguyên dependency layer đã được kiểm chứng.
- `Dockerfile.daily.dockerignore` — sửa: giới hạn build context vào source runtime và mapping combo cần cho image.
- `scripts/push-data-collection-image.sh` — thêm: build tùy chọn, cấu hình Artifact Registry, tag immutable/`latest` và push image không log secret.
- `history/2026-09-24-toi-uu-image-data-collection.md` — thêm: ghi quyết định và kết quả kiểm tra.

## Quyết định

- Giữ `lxml`, `rapidfuzz`, `psycopg[binary]`, `numpy`, `httpx`, `pydantic` và `pydantic-settings` vì crawler/normalizer/seed/embed job import hoặc dùng chúng.
- Không copy `src/data_collection/data/`, test, sample, docs, snapshot catalog nén hoặc manifest; chỉ giữ `combo_items_manual.jsonl` để runner `init` có thể khôi phục mapping đã duyệt.
- Giữ image là batch worker chạy `daily.py`, không biến thành HTTP service vì PRD/README hiện mô tả job console hằng ngày.

## Kiểm tra

- Image baseline `vota-daily:baseline-20260924` đã build; metadata đo được `98,615,818` bytes (~94.0 MiB), source layer `13.1 MB`, dependency layer `139 MB`.
- Lần build tối ưu đầu tiên bị lỗi tải `numpy` do `BrokenPipeError` từ PyPI; chưa phải kết quả build cuối.
- Image tối ưu `vota-daily:optimized-20260924` đã build; metadata đo được `87,238,920` bytes (~83.2 MiB), giảm `11,376,898` bytes (~11.5%) so với baseline.
- Docker build context tối ưu còn `31.29 KB` ở build cuối; image smoke test pass cho `daily.py --help`, `data_collection.seed --help`, import runtime, `daily.py status` và allowlist artifact.
- `bash -n scripts/push-data-collection-image.sh`, `./scripts/push-data-collection-image.sh --help` và `git diff --check` → PASS.
- Artifact Registry: tag `20260924-2918c87e` và `latest` cùng digest `sha256:2918c87ec930bc4888d156df6930d080fe27b80166b384f82aced5d035700857` đã push thành công.
- Chạy end-to-end `IMAGE_SOURCE=vota-daily:optimized-20260924 IMAGE_TAG=20260924-2918c87e ./scripts/push-data-collection-image.sh --no-latest` → PASS; registry describe xác nhận đúng digest. Lần thử đầu gặp `502 Bad Gateway` tạm thời từ registry và retry thành công.

## Còn lại / rủi ro

- Image là batch worker theo `Dockerfile.daily`, không phải HTTP service; chạy job qua `run_daily_docker.sh` với `/data` mount và env file bên ngoài.
- Chưa chạy crawl live hoặc nạp DB/Weaviate thật; task này chỉ xác nhận image packaging và registry publish.

<!-- END SOURCE: history/2026-09-24-toi-uu-image-data-collection.md -->

<!-- BEGIN SOURCE: history/2026-09-24-trien-khai-cicd-backend-cron.md -->

# Triển khai CI/CD Backend và cron crawler

- Ngày: 2026-09-24
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: dang dở — artifact đã tạo, chưa chạy deploy thật vì thiếu target VM/Environment variables; backend suite bị chặn bởi merge conflict có sẵn
- Phạm vi: backend, data collection, CI/CD

## File thay đổi trong task này

- `.github/workflows/backend-ci-cd.yml` — CI PR, build image, WIF, push Artifact Registry, deploy qua IAP SSH.
- `scripts/install-vota-cron.sh` — thay đúng managed cron block bằng crawler image digest, giữ cron khác.
- `scripts/deploy-backend-vm.sh` — preflight tunnel, pull image, restart Backend bằng Compose `--no-deps`, health polling, rollback và cập nhật cron.
- `scripts/check-db-tunnel.sh` — kiểm tra local SSH tunnel `127.0.0.1:15432`.
- `scripts/tests/test-install-vota-cron.sh` — test idempotency cron.
- `scripts/tests/test-deploy-backend-vm.sh` — test tunnel fail-closed và Backend-only dry-run.
- `scripts/tests/test-backend-ci-cd-config.sh` — test guard workflow/WIF/digest/IAP.
- `docs/plan/2026-09-24-backend-cicd-cron.md` — implementation plan.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — cập nhật trạng thái và ranh giới DB VM/tunnel/cron.
- `history/2026-09-24-trien-khai-cicd-backend-cron.md` — entry này.

## Quyết định và ranh giới

- VM ứng dụng chỉ chạy Backend/Crawler; PostgreSQL ở VM DB riêng bằng image riêng.
- CI/CD không stop/reset/start VM, không tác động VM DB, không chạy Compose có service `postgres`, không tạo systemd timer.
- Cron hiện hữu là scheduler; workflow chỉ cập nhật managed cron entry sang crawler digest.
- Backend/Crawler yêu cầu SSH tunnel local `127.0.0.1:15432`; GitHub runner không giữ tunnel.
- Workflow cần GitHub Environment `staging` với WIF, Artifact Registry image base, VM instance/zone/user, Compose file app-only và health URL.

## Kiểm tra đã chạy

- `bash -n scripts/*.sh scripts/tests/*.sh` → PASS.
- `bash scripts/tests/test-install-vota-cron.sh` → PASS; chạy installer hai lần vẫn một managed block và giữ cron không liên quan.
- `bash scripts/tests/test-deploy-backend-vm.sh` → PASS; tunnel đóng thì không gọi Docker, tunnel mở dry-run chỉ cập nhật Backend/Crawler/cron.
- `bash scripts/tests/test-backend-ci-cd-config.sh` → PASS.
- PyYAML parse `.github/workflows/backend-ci-cd.yml` → PASS; `actionlint` chưa cài trong môi trường local.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → PASS: 77 schemas, 53 fixtures và CDP checks.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q src/backend src/data_collection` → FAIL do conflict marker có sẵn trong `src/backend/app/application/ports/unit_index.py` và `src/data_collection/seed/report.py`.
- `python3 -m pytest -q src/backend/tests` → FAIL khi collection do conflict marker có sẵn trong `src/backend/app/application/ports/unit_index.py`; worktree đang `UU` thêm nhiều file. Không sửa/resolution các file đó trong task này.

## Còn lại trước deploy thật

- Resolve merge conflict của worktree rồi chạy lại toàn bộ Backend test suite.
- Tạo GitHub Environment `staging` và khai báo WIF/Artifact Registry/VM variables theo spec.
- Provision long-running autossh/supervisor và `/etc/vota/backend.env`, `/etc/vota/daily.env` trên VM ứng dụng; xác nhận user deploy có Docker và IAP SSH.
- Xác nhận Compose file target không chứa PostgreSQL service và cron runner path tồn tại.
- Chạy một deploy dry-run trên VM, sau đó mới cho phép push vào nhánh staging kích hoạt CD.

<!-- END SOURCE: history/2026-09-24-trien-khai-cicd-backend-cron.md -->


