#!/usr/bin/env bash
# Run once as root on the application (backend) VM, from a checkout of this repo:
#   sudo bash infra/monitoring/install-backend-monitoring.sh
# Installs/updates Ops Agent and the Ops Agent config to parse backend JSON logs.
set -euo pipefail

root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Install Ops Agent if not already present
if ! systemctl list-unit-files google-cloud-ops-agent.service >/dev/null 2>&1 || ! systemctl cat google-cloud-ops-agent.service >/dev/null 2>&1; then
  curl -fsSL https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh -o /tmp/add-ops-agent-repo.sh
  bash /tmp/add-ops-agent-repo.sh --also-install
  rm -f /tmp/add-ops-agent-repo.sh
fi

# Install the Ops Agent config for backend JSON logging (two-tier parser: Docker + app JSON)
install -D -m 0644 "$root_dir/ops-agent-staging.yaml" /etc/google-cloud-ops-agent/config.yaml

# Ensure log directory exists
install -d -m 0755 /var/log/vota

# Restart Ops Agent to load the new config
systemctl restart google-cloud-ops-agent.service
systemctl --no-pager is-active google-cloud-ops-agent.service

echo "✓ Ops Agent config updated on backend VM"
echo "  - Backend logs will now parse two-tier JSON (Docker wrapper + app JSON)"
echo "  - Fields: ts_utc, severity, service, event"
echo "  - Restart backend container if it was not running during install"
