#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
primary="$repo_root/ops/bootstrap-db-primary-replication.sh"
replica="$repo_root/ops/bootstrap-db-replica.sh"
probe="$repo_root/ops/db-replica-lag-probe.sh"
tf_root="$repo_root/infra/terraform/environments/staging"

ci_repl="$repo_root/ops/ci-db-replication.sh"
for file in "$primary" "$replica" "$probe" "$ci_repl" "$tf_root/main.tf" "$tf_root/variables.tf" "$tf_root/addresses.tf"; do
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
grep -q 'pg_basebackup -w' "$replica"
grep -q 'gosu postgres' "$replica"
if grep -q 'PGPASSWORD=\\$(cat' "$replica"; then echo 'replica script must read the password in its own statement so a failure aborts' >&2; exit 1; fi
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

# Primary and app are adopted production-like VMs: they must be protected from
# deletion, never be stopped by Terraform, and never have metadata (ssh-keys) overwritten.
for vm in primary app; do
  f="$tf_root/$vm.tf"
  test -f "$f" || { echo "missing $f" >&2; exit 1; }
  grep -q 'prevent_destroy = true' "$f"
  grep -q 'deletion_protection = true' "$f"
  grep -q 'key_revocation_action_type = "NONE"' "$f"
  grep -Eq 'ignore_changes = \[' "$f"
  grep -q 'metadata,' "$f"
  if grep -Eq '^[[:space:]]*allow_stopping_for_update[[:space:]]*=' "$f"; then
    echo "$vm.tf must not set allow_stopping_for_update" >&2; exit 1
  fi
done
grep -q 'resource "google_compute_instance" "db_primary"' "$tf_root/primary.tf"
grep -q 'resource "google_compute_instance" "app"' "$tf_root/app.tf"
grep -q 'to = google_compute_instance.db_primary' "$tf_root/imports.tf"
grep -q 'to = google_compute_instance.app' "$tf_root/imports.tf"
test ! -e "$tf_root/data.tf" || { echo 'data.tf is gone: primary is a resource now' >&2; exit 1; }

# Static addresses: the tunnel, pg_hba and DNS depend on these never changing.
for addr in 10.148.0.2 10.148.0.3 10.148.0.4 34.142.132.251; do grep -q "\"$addr\"" "$tf_root/addresses.tf"; done

# Local-only files must not be committed.
if git -C "$repo_root" ls-files --error-unmatch "$tf_root/staging.tfvars" "$tf_root/backend.staging.hcl" >/dev/null 2>&1; then
  echo 'staging.tfvars and backend.staging.hcl must not be tracked' >&2; exit 1
fi
grep -q 'prefix = "infra/staging"' "$tf_root/backend.staging.hcl.example"

# CI replication driver: password never printed, primary never restarted, exit status kept.
if grep -Eq 'docker (restart|stop|rm)' "$ci_repl"; then
  echo 'ci-db-replication.sh must not restart or remove containers' >&2; exit 1
fi
grep -q 'set +x' "$ci_repl"
grep -q 'bootstrap-db-primary-replication.sh' "$ci_repl"
grep -q 'bootstrap-db-replica.sh' "$ci_repl"
grep -q 'install -m 600 /dev/stdin' "$ci_repl"
grep -q 'retry_ssh' "$ci_repl"
grep -q 'copy_secret' "$ci_repl"
grep -q 'pg_stat_replication' "$ci_repl"
if grep -Eq 'echo[^|]*(replicator_password|repl_password)|cat[^|]*replicator_password[^|]*\$' "$ci_repl"; then
  echo 'ci-db-replication.sh must not print the replicator password' >&2; exit 1
fi

wf="$repo_root/.github/workflows/infra-terraform-staging.yml"
grep -q 'allow_destroy' "$wf"
grep -q 'index("delete")' "$wf"
grep -q 'apply -input=false -auto-approve staging.tfplan' "$wf"
grep -q 'allow_vm_update' "$wf"
grep -q 'ALLOW_VM_UPDATE' "$wf"
# Job replication_staging đã gỡ (cặp DB cũ đã nghỉ, cụm Patroni thay thế): workflow không còn job này.
! grep -q 'replication_staging' "$wf"

echo 'infra layout, db replica scripts and terraform guards: PASS'
