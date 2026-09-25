# Backend CI/CD và cron crawler Implementation Plan

> **For agentic workers:** Thực thi trực tiếp theo từng task trong checkout hiện tại; không dừng VM, không chạm VM DB và không thêm scheduler thứ hai.

**Goal:** Tự động kiểm tra, build, publish và deploy Backend/Crawler image lên VM ứng dụng qua GitHub Actions, giữ cron crawler hiện có và bắt buộc Backend đi qua SSH tunnel tới VM PostgreSQL riêng.

**Architecture:** GitHub Actions chạy CI trên pull request và CD trên nhánh staging/manual dispatch. Google Workload Identity Federation cấp quyền push Artifact Registry; `gcloud compute ssh --tunnel-through-iap` chỉ gọi script trên VM ứng dụng. Script remote pull image digest, kiểm tra local DB tunnel, cập nhật riêng Backend service bằng Compose override, chờ `/health`, rollback Backend image nếu readiness thất bại và cập nhật đúng một block cron crawler. VM DB, PostgreSQL image, volume và các service khác không nằm trong deploy path.

**Tech Stack:** GitHub Actions, Docker Buildx, Artifact Registry, Google Cloud Workload Identity Federation, `gcloud compute ssh`, Bash, Docker Compose, user crontab, `autossh`/supervisor đã provision trên VM.

**Spec:** `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md`

## Global Constraints

- PostgreSQL chạy ở VM riêng bằng image riêng; VM ứng dụng không build/pull/run/recreate PostgreSQL.
- Không gọi `gcloud compute instances stop/reset/start`, `docker compose down`, `docker compose down -v`, `docker system prune` hoặc thao tác xoá volume.
- Deploy chỉ restart service Backend; không restart PostgreSQL, Weaviate, Redis hoặc service khác.
- Backend/Crawler dùng DSN `127.0.0.1:15432` qua SSH tunnel; tunnel phải sẵn sàng trước health check.
- Cron hiện hữu là nguồn sự thật; installer chỉ thay block có marker và không tạo lịch trùng.
- Secrets không nằm trong image, workflow log, crontab hoặc command line; env file trên VM có quyền `0600`.
- Không thay đổi API contract, database schema, frontend hoặc crawler behavior.
- Mọi thay đổi `src/`, `docs/` hoặc `db/` phải có history entry; plan/spec không được thay thế PRD.

## Review Focus

- VM DB không bị chạm: test tĩnh và remote command không chứa stop/reset/Compose postgres; task 3 kiểm tra fail-closed.
- Tunnel chết: deploy dừng trước khi restart Backend; task 3 test cổng `127.0.0.1:15432` không mở.
- Cron trùng: chạy installer hai lần vẫn chỉ có một managed block và giữ nguyên dòng cron khác; task 1 test idempotency.
- Backend khởi động lâu: health polling đủ thời gian và rollback dùng image trước; task 2 test timeout/rollback path.
- Tag mutable: workflow push cả SHA và `latest`; Backend deploy và cron crawler dùng `latest`, còn rollback giữ digest trước; task 3 kiểm tra YAML và shell argument.

### Task 1: Idempotent cron installer và runner contract

**Files:**
- Create: `scripts/install-vota-cron.sh`
- Create: `scripts/tests/test-install-vota-cron.sh`
- Modify: `src/data_collection/README.md` — chỉ khi cần ghi contract marker/immutable digest; không thay đổi lịch hiện hữu ngoài tài liệu.

**Interfaces:**
- Consumes: `--image`, `--runner`, `--data-dir`, `--env-file`, optional `--schedule`, `--crontab-file`, `--dry-run`.
- Produces: một block cron có marker `# BEGIN VOTA CRAWLER` / `# END VOTA CRAWLER`, gọi `run_daily_docker.sh run` với image `:latest`, `PULL=1`, data dir và env file.

- [ ] **Step 1: Write the failing shell test**

  Test file tạo crontab fixture có một dòng cron không liên quan, chạy installer hai lần với cùng `:latest`, rồi assert: dòng cũ còn nguyên, có đúng một marker block, block có `PULL=1`, và image xuất hiện đúng một lần.

- [ ] **Step 2: Run the test to verify it fails**

  Run: `bash scripts/tests/test-install-vota-cron.sh`

  Expected: FAIL vì `scripts/install-vota-cron.sh` chưa tồn tại.

- [ ] **Step 3: Implement the minimal installer**

  Implement strict Bash parsing, validate image reference/absolute runner path, remove only the managed marker block, preserve all other crontab lines, write atomically to a temporary file, and support fixture mode via `--crontab-file`. Never print env file contents.

- [ ] **Step 4: Run the test to verify it passes**

  Run: `bash scripts/tests/test-install-vota-cron.sh`

  Expected: PASS with one managed block and preserved unrelated cron line.

- [ ] **Step 5: Run shell syntax checks**

  Run: `bash -n scripts/install-vota-cron.sh scripts/tests/test-install-vota-cron.sh`

  Expected: exit 0.

### Task 2: Safe remote Backend/Crawler deploy script

**Files:**
- Create: `scripts/deploy-backend-vm.sh`
- Create: `scripts/tests/test-deploy-backend-vm.sh`
- Create: `scripts/check-db-tunnel.sh`

**Interfaces:**
- Consumes: `--backend-image`, `--crawler-image`, `--compose-file`, `--backend-service`, `--backend-health-url`, `--db-tunnel-host`, `--db-tunnel-port`, `--cron-runner`, `--dry-run`.
- Produces: backend-only Compose override, health-gated deploy, rollback to the previously running Backend image on failure, tunnel preflight, and cron installer invocation.

- [ ] **Step 1: Write the failing shell tests**

  Test the dry-run contract with fake `docker`, `docker compose`, `curl`, and `nc` commands in a temporary `PATH`. Assert the generated command stream contains `pull backend` and `up -d --no-deps backend`, rejects a closed tunnel before any restart, and contains none of `docker compose down`, `postgres`, `gcloud compute instances stop`, `reset`, or `start`.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `bash scripts/tests/test-deploy-backend-vm.sh`

  Expected: FAIL because the deploy and tunnel-check scripts do not exist.

- [ ] **Step 3: Implement tunnel preflight and deploy**

  `check-db-tunnel.sh` must check only a loopback host/port and return non-zero with a safe message when unavailable. `deploy-backend-vm.sh` must:

  1. Validate required `:latest` image references and paths.
  2. Check the tunnel before touching the Backend container.
  3. Capture the current Backend image reference.
  4. Pull only the Backend and crawler images.
  5. Use a temporary Compose override to set the Backend image and run `docker compose ... up -d --no-deps "$backend_service"`.
  6. Poll `GET /health` for a configurable timeout suitable for model/index startup.
  7. On failure, restore the captured Backend image with the same `--no-deps` path and re-check health.
  8. Update the managed cron block to the crawler `:latest` reference only after Backend health passes.

  The script must not read or echo secret values, must not run `docker compose` with a database service, and must clean temporary override files with `trap`.

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `bash scripts/tests/test-deploy-backend-vm.sh`

  Expected: PASS for successful dry-run, closed-tunnel fail-closed, and forbidden-command guards.

- [ ] **Step 5: Run script syntax and safety scans**

  Run: `bash -n scripts/check-db-tunnel.sh scripts/deploy-backend-vm.sh scripts/tests/test-deploy-backend-vm.sh && rg -n 'instances (stop|reset|start)|compose down|compose down -v|systemctl.*(stop|reboot)|docker system prune' scripts/deploy-backend-vm.sh scripts/install-vota-cron.sh`

  Expected: syntax exit 0 and the safety scan produces no forbidden command matches.

### Task 3: GitHub Actions CI/CD workflow

**Files:**
- Create: `.github/workflows/backend-ci-cd.yml`
- Create: `scripts/tests/test-backend-ci-cd-config.sh`

**Interfaces:**
- Consumes: repository/environment variables `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_SERVICE_ACCOUNT`, `GAR_BACKEND_IMAGE`, `GAR_DAILY_IMAGE`, `GCE_INSTANCE`, `GCE_ZONE`, `GCE_DEPLOY_USER`, `GCE_COMPOSE_FILE`, `GCE_BACKEND_HEALTH_URL`; no secret value is embedded.
- Produces: PR CI, SHA-plus-`latest` image publish and IAP SSH invocation of the remote deploy script.

- [ ] **Step 1: Write the failing workflow config test**

  Test asserts the YAML text contains pull-request CI, `permissions: id-token: write`, Workload Identity auth, Buildx, both Dockerfiles, SHA and `latest` tags, `gcloud compute ssh --tunnel-through-iap`, and no `docker compose up` with a postgres service.

- [ ] **Step 2: Run the test to verify it fails**

  Run: `bash scripts/tests/test-backend-ci-cd-config.sh`

  Expected: FAIL because the workflow does not exist.

- [ ] **Step 3: Implement the workflow**

  Use `actions/checkout`, `actions/setup-python`, targeted backend tests/contract validation, `docker/setup-buildx-action`, `google-github-actions/auth`, `docker/login-action`, and `docker/build-push-action`. PRs build without publishing; pushes to `dev` or manual dispatch publish both SHA and `latest` tags. The deploy job copies the remote scripts and invokes the remote deploy with `:latest`. Workflow must fail when required repository variables are missing rather than guessing a DB or VM target.

- [ ] **Step 4: Run config and YAML validation**

  Run: `bash scripts/tests/test-backend-ci-cd-config.sh`

  Expected: PASS. If `actionlint` is installed, also run `actionlint .github/workflows/backend-ci-cd.yml`; otherwise parse the YAML with the available YAML parser and record actionlint as unavailable.

### Task 4: Documentation, history, and final verification

**Files:**
- Modify: `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — reconcile exact implemented variables/commands.
- Modify: `src/data_collection/README.md` — document the managed cron marker, digest update and SSH tunnel precondition if implementation changes the operator contract.
- Create: `history/2026-09-24-trien-khai-cicd-backend-cron.md`

**Interfaces:**
- Consumes: outputs of Tasks 1–3 and the approved design spec.
- Produces: reproducible operator instructions and evidence-backed history entry.

- [ ] **Step 1: Run targeted verification**

  Run: `bash scripts/tests/test-install-vota-cron.sh && bash scripts/tests/test-deploy-backend-vm.sh && bash scripts/tests/test-backend-ci-cd-config.sh && bash -n scripts/*.sh scripts/tests/*.sh && git diff --check`

  Expected: all tests exit 0 and no whitespace errors.

- [ ] **Step 2: Run repository checks in scope**

  Run: `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` and `python3 -m compileall -q src/backend src/data_collection`

  Expected: contract validator and compile checks pass; no live DB write or crawler run is claimed.

- [ ] **Step 3: Record exact evidence**

  Record changed files from `git status --short`, commands and real results, the fact that no VM/DB deployment was executed without target details, and any unavailable actionlint/runtime checks in the history entry.

- [ ] **Step 4: Final worktree review**

  Run: `git diff --check && git status --short --branch && git diff --stat`

  Expected: only scoped CI/CD/spec/history changes plus pre-existing crawler/Docker work are present; no `.env` or secret is changed.
