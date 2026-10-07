#!/usr/bin/env bash
# Run once as root on the DB replica VM, from a checkout of this repo:
#   sudo bash infra/monitoring/install-db-replica-monitoring.sh
# Installs Ops Agent (if missing), the Ops Agent config, the lag probe and its cron entry.
set -euo pipefail

root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$root_dir/../.." && pwd)"

if ! systemctl list-unit-files google-cloud-ops-agent.service >/dev/null 2>&1 || ! systemctl cat google-cloud-ops-agent.service >/dev/null 2>&1; then
  curl -fsSL https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh -o /tmp/add-ops-agent-repo.sh
  bash /tmp/add-ops-agent-repo.sh --also-install
  rm -f /tmp/add-ops-agent-repo.sh
fi

install -D -m 0644 "$root_dir/ops-agent-db-replica.yaml" /etc/google-cloud-ops-agent/config.yaml
install -D -m 0755 "$repo_root/ops/db-replica-lag-probe.sh" /usr/local/libexec/db-replica-lag-probe.sh
install -d -m 0750 /var/log/vota
touch /var/log/vota/pg-replica.jsonl
chmod 0640 /var/log/vota/pg-replica.jsonl

cat > /etc/cron.d/vota-db-replica-probe <<'CRON'
* * * * * root /usr/local/libexec/db-replica-lag-probe.sh
CRON
chmod 0644 /etc/cron.d/vota-db-replica-probe

cat > /etc/logrotate.d/vota-db-replica <<'LOGROTATE'
/var/log/vota/pg-replica.jsonl {
  daily
  rotate 7
  maxsize 50M
  missingok
  notifempty
  compress
  copytruncate
}
LOGROTATE

systemctl restart google-cloud-ops-agent.service
systemctl --no-pager is-active google-cloud-ops-agent.service
/usr/local/libexec/db-replica-lag-probe.sh || true
tail -n 1 /var/log/vota/pg-replica.jsonl
