#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"

test -f "$root_dir/versions.tf"
test -f "$root_dir/backend.tf"
test -f "$root_dir/main.tf"
test -f "$root_dir/variables.tf"
test -f "$root_dir/outputs.tf"
test -f "$root_dir/staging.tfvars.example"
test -f "$root_dir/ops-agent-staging.yaml"
test -f "$root_dir/vota-docker-event-watcher.py"
test -f "$root_dir/vota-docker-event-watcher.service"
test -f "$root_dir/install-vota-docker-event-watcher.sh"
test -f "$root_dir/vota-monitoring-logrotate.conf"
test -f "$root_dir/vota-container-disk-collector.py"
test -f "$root_dir/vota-container-disk-collector.service"
test -f "$root_dir/dashboard.tf"
test -f "$root_dir/container_metrics.tf"
test -f "$root_dir/vota-container-stats-collector.py"
test -f "$root_dir/vota-container-stats-collector.service"
test -f "$root_dir/replica.tf"
test -f "$root_dir/ops-agent-db-replica.yaml"
test -f "$root_dir/install-db-replica-monitoring.sh"

test -d "$root_dir/modules"
test -f "$root_dir/main.tf"

if grep -R -n -i -E \
  --include='*.tf' \
  --include='*.yaml' \
  --include='*.yml' \
  --include='*.tfvars*' \
  'production|prod(uction)?_state|prod_state' "$root_dir"; then
  echo 'production configuration must not be present in the staging package' >&2
  exit 1
fi

for required in \
  'google_monitoring_dashboard' \
  'google_monitoring_alert_policy' \
  'google_monitoring_uptime_check_config' \
  'google_logging_metric' \
  'google_monitoring_notification_channel'; do
  grep -R -q -F "$required" "$root_dir" || {
    echo "missing required monitoring resource: $required" >&2
    exit 1
  }
done

for required in \
  'fresh_catalog_logs' \
  'docker_events' \
  'staging_crawler_warning' \
  'staging_crawler_failure' \
  'staging_container_stop' \
  'staging_docker_watcher_absent' \
  'staging_http_requests_total' \
  'staging_http_requests_5xx' \
  'google_monitoring_custom_service' \
  'google_monitoring_slo' \
  'vota-staging-availability' \
  'vota-staging-error-rate' \
  'vota-staging-latency'; do
  grep -R -q -F "$required" "$root_dir" || {
    echo "missing crawler monitoring component: $required" >&2
    exit 1
  }
done

grep -q -F '/srv/vota/fresh-catalog-logs/*.log' "$root_dir/ops-agent-staging.yaml"
grep -q -F '/var/log/vota/docker-events.jsonl' "$root_dir/ops-agent-staging.yaml"
grep -q -F 'rotate 14' "$root_dir/vota-monitoring-logrotate.conf"
grep -q -F 'maxsize 100M' "$root_dir/vota-monitoring-logrotate.conf"
grep -q -F 'jsonPayload.message:\"fresh-catalog.exit=3\"' "$root_dir/main.tf"
grep -q -F 'Docker watcher heartbeat' "$root_dir/dashboard.tf"
grep -q -F 'mosaicLayout' "$root_dir/dashboard.tf"
grep -q -F 'CPU by container' "$root_dir/dashboard.tf"
grep -q -F 'RAM by container' "$root_dir/dashboard.tf"
grep -q -F 'custom.googleapis.com/vota/container/' "$root_dir/container_metrics.tf"
grep -q -F 'vota-container-stats-collector' "$root_dir/install-vota-docker-event-watcher.sh"
grep -q -F 'Crawler warnings and failures' "$root_dir/dashboard.tf"
grep -q -F 'Container OOM kills' "$root_dir/dashboard.tf"
grep -q -F 'container_name = "EXTRACT(jsonPayload.container_name)"' "$root_dir/main.tf"
grep -q -F 'Availability SLO' "$root_dir/dashboard.tf"
grep -q -F 'Error-rate SLO' "$root_dir/dashboard.tf"
grep -q -F 'Latency SLO' "$root_dir/dashboard.tf"
grep -q -F 'Backend container logs' "$root_dir/dashboard.tf"
grep -q -F 'Frontend container logs' "$root_dir/dashboard.tf"
grep -q -F 'Crawler container logs' "$root_dir/dashboard.tf"
grep -q -F 'Redis container logs' "$root_dir/dashboard.tf"
grep -q -F 'Weaviate container logs' "$root_dir/dashboard.tf"
grep -q -F 'jsonPayload.container_name=\"vota-backend\"' "$root_dir/dashboard.tf"
grep -q -F 'jsonPayload.container_name=\"vota-frontend\"' "$root_dir/dashboard.tf"
grep -q -F 'jsonPayload.container_name=\"vota-fresh-catalog\"' "$root_dir/dashboard.tf"
grep -q -F 'jsonPayload.container_name=\"vota-redis\"' "$root_dir/dashboard.tf"
grep -q -F 'jsonPayload.container_name=\"vota-weaviate\"' "$root_dir/dashboard.tf"
grep -q -F '/var/log/vota/container-disk.jsonl' "$root_dir/ops-agent-staging.yaml"
grep -q -F '/var/log/vota/container-disk.jsonl' "$root_dir/vota-monitoring-logrotate.conf"
grep -q -F 'vota-container-disk-collector' "$root_dir/install-vota-docker-event-watcher.sh"
grep -q -F 'staging_container_disk_bytes' "$root_dir/main.tf"
grep -q -F 'staging_container_disk' "$root_dir/outputs.tf"
grep -q -F 'EXTRACT(jsonPayload.total_bytes)' "$root_dir/main.tf"
grep -q -F 'Container disk usage (writable + logs + volumes)' "$root_dir/dashboard.tf"
grep -q -F 'Container disk usage (exact samples)' "$root_dir/dashboard.tf"
grep -q -F 'container_disk_alert_gib' "$root_dir/variables.tf"
grep -q -F '/var/log/vota/pg-replica.jsonl' "$root_dir/ops-agent-db-replica.yaml"
grep -q -F 'local.replica_enabled' "$root_dir/replica.tf"
bash -n "$root_dir/install-db-replica-monitoring.sh"
python3 -m py_compile "$root_dir/vota-docker-event-watcher.py" "$root_dir/vota-container-disk-collector.py" "$root_dir/vota-container-stats-collector.py"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q "$root_dir/tests/test_watcher_datetime.py" "$root_dir/tests/test_container_disk.py" "$root_dir/tests/test_container_stats.py"

echo 'staging monitoring layout: PASS'
