# Staging Monitoring SLOs Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with the native execution method already chosen by the user.

**Goal:** Add staging availability, HTTP error-rate, and latency SLOs and show their compliance/error budget on the existing Cloud Monitoring dashboard.

**Architecture:** Define one Cloud Monitoring custom service for the staging public API. Measure availability from the existing public readiness uptime check, error rate from Backend Uvicorn access-log counters, and latency from the uptime-check request-latency metric. Manage the service, SLOs, log-based metrics, and dashboard widgets together in the existing staging-only Terraform root.

**Tech Stack:** Terraform Google provider 6.x, Cloud Monitoring Service Monitoring API, Cloud Logging log-based metrics, Cloud Monitoring dashboard JSON.

**Spec:** `docs/prd/requirements.md` NFR-PERF-01 and NFR-REL-01; `docs/prd/deployment-plan.md` §5–6.

## Global Constraints

- Staging only: `infra/monitoring` accepts `environment = "staging"`.
- Preserve all existing VM, uptime, container, crawler, and watcher alerts.
- Do not log or commit secrets.
- Use the existing remote Terraform state and review plan before apply.
- SLO window: rolling 30 days; staging targets are operational monitoring targets, not a production SLA.

## Review Focus

- Uptime check labels must select only `vota-staging-readiness-oX87RfZ2ntw`; test the filter in the live time series before apply.
- HTTP request counters must match Uvicorn access logs and distinguish all requests from 5xx requests.
- Latency threshold must use the uptime request-latency metric's millisecond unit; pin `max = 1000`.
- Dashboard SLO selectors must reference the SLO resource names, not guessed metric types.
- Terraform migration must not destroy existing alert policies or the dashboard.

### Task 1: Add telemetry metrics and custom service

**Files:**
- Modify: `infra/monitoring/main.tf`
- Test: `infra/monitoring/tests/test_staging_layout.sh`

- [x] Add log-based DELTA/INT64 metrics for total Backend HTTP access requests and HTTP 5xx requests, scoped to the app VM and Uvicorn access-log pattern.
- [x] Add `google_monitoring_custom_service.staging_api` with stable service ID `vota-staging-api`.
- [x] Add layout assertions for both metrics and the custom service.
- [x] Run the layout test and verify it fails before the implementation is complete, then make it pass.

### Task 2: Add three SLO resources

**Files:**
- Modify: `infra/monitoring/main.tf`
- Test: `infra/monitoring/tests/test_staging_layout.sh`

- [x] Add availability SLO `vota-staging-availability`, goal `0.995`, using a 60-second windows-based SLI over uptime `check_passed`.
- [x] Add error-rate SLO `vota-staging-error-rate`, goal `0.995`, using total HTTP requests and HTTP 5xx requests.
- [x] Add latency SLO `vota-staging-latency`, goal `0.95`, using uptime `request_latency` with a 1-second maximum and 60-second windows.
- [x] Add layout assertions for the service and all three SLO IDs.

### Task 3: Add SLO dashboard widgets

**Files:**
- Modify: `infra/monitoring/main.tf`
- Test: `infra/monitoring/tests/test_staging_layout.sh`

- [x] Add dashboard scorecards for compliance and remaining error budget for availability, error rate, and latency using `select_slo_compliance` and `select_slo_budget`.
- [x] Keep existing dashboard widgets unchanged.
- [x] Add layout assertions for the three SLO widget titles.

### Task 4: Validate and deploy staging

- [x] Run `terraform fmt -check -recursive`, layout tests, and `git diff --check`. Local `terraform validate` remains blocked by the cached darwin provider handshake; remote Terraform plan parsed the configuration successfully.
- [x] Run remote-state Terraform plans and review the targeted plans: 3 telemetry/service resources, then 3 SLOs plus the dashboard; no destroys.
- [x] Apply staging through reviewed targeted plans; 6 resources created and dashboard updated.
- [x] Verify live service/SLO resources, metric descriptors, and dashboard selectors through Cloud Monitoring APIs.
