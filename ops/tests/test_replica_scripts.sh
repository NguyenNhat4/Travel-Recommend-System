#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
primary="$repo_root/ops/bootstrap-db-primary-replication.sh"
replica="$repo_root/ops/bootstrap-db-replica.sh"
probe="$repo_root/ops/db-replica-lag-probe.sh"
tf_root="$repo_root/infra/terraform/environments/staging"

for file in "$primary" "$replica" "$probe" "$tf_root/main.tf" "$tf_root/variables.tf"; do
  test -f "$file" || { echo "missing required file: $file" >&2; exit 1; }
  case "$file" in *.sh) bash -n "$file" ;; esac
done

# Primary: slot, WAL cap, hba rule limited to one /32, no restart, password from a file.
grep -q 'pg_create_physical_replication_slot' "$primary"
grep -q 'max_slot_wal_keep_size' "$primary"
grep -q 'host replication replicator \${REPLICA_IP}/32 scram-sha-256' "$primary"
grep -q 'pg_reload_conf' "$primary"
grep -q 'REPL_PASSWORD_FILE' "$primary"
grep -q 'exec -i -u postgres' "$primary"
grep -q 'exec -u postgres' "$probe"
if grep -Eq 'docker (restart|stop)' "$primary"; then
  echo 'primary preparation must not restart PostgreSQL' >&2; exit 1
fi

# Replica: same image/volume layout as the primary, base backup with -R and a slot, hot standby.
grep -q 'pg_basebackup' "$replica"
grep -q -- '-R -X stream -S' "$replica"
grep -q 'hot_standby=on' "$replica"
grep -q 'pg_is_in_recovery' "$replica"
grep -q 'IMAGE:?' "$replica"
grep -q '18/docker' "$replica"
grep -q -- '--publish="${replica_ip}:5432:5432"' "$replica"

# No password literal embedded anywhere in the new scripts.
if grep -Eq 'PGPASSWORD=[A-Za-z0-9]|PASSWORD=[A-Za-z0-9]{6,}' "$primary" "$replica" "$probe"; then
  echo 'passwords must not be embedded in scripts' >&2; exit 1
fi

# Probe: status vocabulary the monitoring metrics depend on.
for status in ok lagging broken; do grep -q "status=$status" "$probe"; done
grep -q '"event":"pg_replica"' "$probe"
grep -q 'jsonPayload.event=\\"pg_replica\\"' "$repo_root/infra/monitoring/replica.tf"

# Terraform root must never manage the hand-made VMs, only read them.
if grep -nE 'resource "google_compute_instance" "(db_primary|app)"' "$tf_root/main.tf"; then
  echo 'existing VMs must stay data sources' >&2; exit 1
fi
grep -q 'data "google_compute_instance" "db_primary"' "$tf_root/data.tf"
grep -q 'prefix = "infra/staging"' "$tf_root/backend.staging.hcl.example"

echo 'db replica scripts and terraform layout: PASS'
