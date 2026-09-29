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

echo 'staging monitoring layout: PASS'
