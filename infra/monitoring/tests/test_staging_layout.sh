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
  'staging_docker_watcher_absent'; do
  grep -R -q -F "$required" "$root_dir" || {
    echo "missing crawler monitoring component: $required" >&2
    exit 1
  }
done

grep -q -F '/srv/vota/fresh-catalog-logs/*.log' "$root_dir/ops-agent-staging.yaml"
grep -q -F '/var/log/vota/docker-events.jsonl' "$root_dir/ops-agent-staging.yaml"
python3 -m py_compile "$root_dir/vota-docker-event-watcher.py"

echo 'staging monitoring layout: PASS'
