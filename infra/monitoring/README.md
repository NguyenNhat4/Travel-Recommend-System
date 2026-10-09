# Staging Managed Monitoring

This root configures only the staging monitoring environment. It does not contain live-environment resources or a live state path.

## Resources

- Cloud Monitoring dashboard (`dashboard.tf`, 12-column mosaic) read top to bottom: Overview (readiness + SLO gauges), Backend API, one block per VM (App, DB, DB replica when it exists) with CPU/memory/fullest-disk scorecards and CPU, memory-by-state, disk-by-device, network charts, per-container CPU/RAM/disk for the App VM, container and crawler events, logs. Nothing is averaged across VMs or containers.
- Per-container CPU and RAM: `vota-container-stats-collector` runs `docker stats --no-stream` every 60 s and writes custom metrics `custom.googleapis.com/vota/container/{cpu_percent,memory_bytes,memory_percent}` (declared in `container_metrics.tf`; CPU 100% = one vCPU). The `container metrics collector silent` alert fires if the samples stop.
- Dashboard log panels for backend, frontend, crawler, Redis and Weaviate containers, filtered by container name where the emitted log entry provides it.
- Per-container disk usage: `vota-container-disk-collector` samples every 5 minutes (writable layer, json-file logs incl. rotations, named volumes) into `/var/log/vota/container-disk.jsonl`; a log-based distribution metric feeds a dashboard chart and the `container disk usage high` alert (`container_disk_alert_gib`, default 5 GiB), and a logs panel shows the exact byte values.
- Alert policies for uptime, CPU, memory, disk, per-container disk and error-level VM logs.
- Cloud Monitoring HTTPS uptime check for the staging readiness endpoint.
- Cloud Logging user metric for error-level Compute Engine logs.
- Docker lifecycle event watcher and crawler log metrics for container stop, OOM, partial crawler runs and watcher heartbeat absence.
- Daily log rotation for watcher, crawler and daily-job logs: 14 compressed rotations with a 100 MB per-file cap.
- Optional email notification channel, supplied as a sensitive variable.

Container disk numbers exclude shared image layers and bind mounts; a named volume mounted by several containers is counted in each. The chart reads percentiles of 10%-wide buckets (about ±5%) and shows containers under 1 MiB as 0; use the logs panel or `tail /var/log/vota/container-disk.jsonl` for exact bytes. Collection failures are logged as `event=container_disk_error`.

The crawler monitor UI is not part of this package. This package monitors the crawler and container lifecycle only.

The named container log panels depend on `jsonPayload.container_name` being present in the Cloud Logging entry. Docker `json-file` logs are parsed by the Ops Agent but are not automatically enriched with a Compose service name; verify the live entry shape in Logs Explorer before treating an empty named panel as an ingestion failure.

## Local validation

```bash
bash infra/monitoring/tests/test_staging_layout.sh
terraform -chdir=infra/monitoring fmt -check -recursive
terraform -chdir=infra/monitoring init -backend=false
terraform -chdir=infra/monitoring validate
```

## Staging plan/apply

Create the state bucket and configure credentials outside the repository. Then either use the GitHub Actions staging environment or run:

```bash
terraform -chdir=infra/monitoring init \
  -backend-config=backend.staging.hcl

terraform -chdir=infra/monitoring plan \
  -var-file=staging.tfvars

terraform -chdir=infra/monitoring apply \
  -var-file=staging.tfvars
```

Never commit `backend.staging.hcl`, `staging.tfvars`, state files or generated plans.

Install the VM-side Docker event watcher separately after reviewing the staging plan:

```bash
sudo bash infra/monitoring/install-vota-docker-event-watcher.sh
sudo systemctl is-active vota-docker-event-watcher.service
sudo tail -n 20 /var/log/vota/docker-events.jsonl
sudo systemctl is-active vota-container-disk-collector.service
sudo tail -n 5 /var/log/vota/container-disk.jsonl
sudo systemctl is-active vota-container-stats-collector.service
sudo journalctl -u vota-container-stats-collector -n 20 --no-pager
```
