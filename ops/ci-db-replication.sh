#!/usr/bin/env bash
# Runs on the CI runner (gcloud already authenticated) and brings primary and replica to
# the replicating state. Every step is idempotent: if the replica already streams from the
# primary, only the monitoring install is refreshed. Nothing here restarts the primary.
#
# Required env: GCP_PROJECT_ID GCE_ZONE PRIMARY_VM REPLICA_VM
# Optional env: DB_IMAGE (must be the exact image the primary runs)
#               GCE_REPLICA_ZONE (zone of the replica VM; default GCE_ZONE). The replica should live in a DIFFERENT zone
#               of the same region, otherwise losing the primary zone loses the replica too.
set -Eeuo pipefail
set +x

: "${GCP_PROJECT_ID:?}" "${GCE_ZONE:?}" "${PRIMARY_VM:?}" "${REPLICA_VM:?}"
GCE_REPLICA_ZONE=${GCE_REPLICA_ZONE:-$GCE_ZONE}
DB_IMAGE=${DB_IMAGE:-pgvector/pgvector:0.8.6-pg18-bookworm}
CONTAINER_NAME=${CONTAINER_NAME:-vota-postgres}
SECRET_PATH=/etc/vota/secrets/replicator_password
MAX_LAG_SECONDS=${MAX_LAG_SECONDS:-60}
summary=${GITHUB_STEP_SUMMARY:-/dev/null}

repo_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

# Exit status 255 means ssh could not connect or authenticate. With OS Login, a key imported a
# moment ago can be rejected for a few seconds, so retry that status (and only that one) a few
# times with growing waits. Anything else (the remote command failing) is returned as is.
retry_ssh() {
  local attempt=1 rc
  while true; do
    if "$@"; then return 0; else rc=$?; fi
    if [[ $rc -ne 255 || $attempt -ge 4 ]]; then return "$rc"; fi
    echo "SSH failed with 255 (attempt $attempt of 4); retrying in $((attempt * 15))s" >&2
    sleep $((attempt * 15))
    attempt=$((attempt + 1))
  done
}

zone_of() { if [[ "$1" == "$REPLICA_VM" ]]; then echo "$GCE_REPLICA_ZONE"; else echo "$GCE_ZONE"; fi; }

ssh_vm_in() { # ssh_vm_in <vm> <command>; forwards stdin to the remote command (no retry here)
  gcloud compute ssh "$1" --project "$GCP_PROJECT_ID" --zone "$(zone_of "$1")" \
    --tunnel-through-iap --quiet --command "$2"
}

# No stdin, so ssh never swallows the script's input; safe to retry.
ssh_vm() { retry_ssh ssh_vm_in "$@" </dev/null; }

# Run a script on a VM, remove its upload dir, and keep the script's exit status.
run_remote() { # run_remote <vm> <dir> <env assignments + command>
  ssh_vm "$1" "$3; rc=\$?; rm -rf '$2'; exit \$rc"
}

vm_ip() {
  gcloud compute instances describe "$1" --project "$GCP_PROJECT_ID" --zone "$(zone_of "$1")" \
    --format='value(networkInterfaces[0].networkIP)'
}

psql_primary() {
  ssh_vm "$PRIMARY_VM" "sudo docker exec -u postgres $CONTAINER_NAME psql -X -U postgres -Atqc \"$1\""
}

psql_replica() {
  ssh_vm "$REPLICA_VM" "sudo docker exec -u postgres $CONTAINER_NAME psql -X -U postgres -Atqc \"$1\" 2>/dev/null || echo none"
}

push_files_once() {
  local vm=$1 dir=$2
  shift 2
  tar -C "$repo_root" -czf - "$@" |
    ssh_vm_in "$vm" "umask 077; rm -rf '$dir'; mkdir -m 700 '$dir' && tar -xzf - -C '$dir'"
}

push_files() { retry_ssh push_files_once "$@"; } # push_files <vm> <remote_dir> <files...>

# Read the secret on the primary first, then write it to the replica, so two gcloud ssh
# processes never run at once. It only lives in a shell variable (set +x, never echoed).
copy_secret() {
  local secret
  secret=$(ssh_vm "$PRIMARY_VM" "sudo cat '$SECRET_PATH'") || return $?
  [[ -n $secret ]] || { echo "::error::Replicator password file on the primary is empty" >&2; return 1; }
  printf '%s' "$secret" |
    ssh_vm_in "$REPLICA_VM" "sudo install -d -m 700 /etc/vota/secrets && sudo install -m 600 /dev/stdin '$SECRET_PATH'"
}

echo "== Preflight: SSH to both VMs through IAP"
ssh_vm "$PRIMARY_VM" true || {
  echo "::error::Cannot SSH to $PRIMARY_VM. The CI service account needs roles/compute.instanceAdmin.v1, roles/iap.tunnelResourceAccessor and roles/iam.serviceAccountUser on the VM's service account." >&2
  exit 1
}
ssh_vm "$REPLICA_VM" true

primary_ip=$(vm_ip "$PRIMARY_VM")
replica_ip=$(vm_ip "$REPLICA_VM")
[[ $primary_ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ && $replica_ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  { echo "unexpected VM IPs: '$primary_ip' '$replica_ip'" >&2; exit 1; }
echo "primary=$primary_ip replica=$replica_ip image=$DB_IMAGE"

streaming() { psql_primary "select count(*) from pg_stat_replication where client_addr='$replica_ip' and state='streaming'"; }

echo "== Current state"
if [[ $(streaming) == 1 && $(psql_replica 'select pg_is_in_recovery()') == t ]]; then
  echo "Replica already streams from the primary; skipping bootstrap"
else
  tag=$(date +%s)
  remote_dir=/tmp/vota-replication-$tag

  echo "== Primary: role, slot, pg_hba (reload only, no restart)"
  push_files "$PRIMARY_VM" "$remote_dir" ops/bootstrap-db-primary-replication.sh
  run_remote "$PRIMARY_VM" "$remote_dir" "REPLICA_IP='$replica_ip' CONTAINER_NAME='$CONTAINER_NAME' sudo -E bash '$remote_dir/ops/bootstrap-db-primary-replication.sh'"

  echo "== Copy replicator password primary -> replica (through the runner pipe, never printed)"
  retry_ssh copy_secret

  echo "== Replica: base backup and hot standby"
  push_files "$REPLICA_VM" "$remote_dir" ops/bootstrap-db-replica.sh
  run_remote "$REPLICA_VM" "$remote_dir" "IMAGE='$DB_IMAGE' PRIMARY_HOST='$primary_ip' CONTAINER_NAME='$CONTAINER_NAME' sudo -E bash '$remote_dir/ops/bootstrap-db-replica.sh'"
fi

echo "== Replica monitoring (Ops Agent, lag probe)"
remote_dir=/tmp/vota-replica-monitoring-$(date +%s)
push_files "$REPLICA_VM" "$remote_dir" \
  ops/db-replica-lag-probe.sh \
  infra/monitoring/install-db-replica-monitoring.sh \
  infra/monitoring/ops-agent-db-replica.yaml
run_remote "$REPLICA_VM" "$remote_dir" "sudo bash '$remote_dir/infra/monitoring/install-db-replica-monitoring.sh'"

echo "== Verify"
ok=false
for _ in $(seq 1 12); do
  if [[ $(streaming) == 1 ]]; then ok=true; break; fi
  sleep 5
done
in_recovery=$(psql_replica 'select pg_is_in_recovery()')
slot=$(psql_primary "select active from pg_replication_slots where slot_name='vota_replica'")
last=$(ssh_vm "$REPLICA_VM" 'sudo tail -n 1 /var/log/vota/pg-replica.jsonl')
lag=$(printf '%s' "$last" | sed -n 's/.*"lag_seconds":\([0-9.]*\).*/\1/p')

{
  echo '### DB replication (staging)'
  echo "| check | result |"
  echo "|---|---|"
  echo "| primary sees replica streaming | $ok |"
  echo "| replica in recovery | $in_recovery |"
  echo "| slot vota_replica active | $slot |"
  echo "| lag_seconds (last probe) | ${lag:-n/a} |"
} >>"$summary"

[[ $ok == true && $in_recovery == t && $slot == t ]] || { echo "::error::Replication verification failed" >&2; exit 1; }
if [[ -n $lag ]] && awk -v l="$lag" -v m="$MAX_LAG_SECONDS" 'BEGIN{exit !(l>m)}'; then
  echo "::error::Replica lag ${lag}s exceeds ${MAX_LAG_SECONDS}s" >&2
  exit 1
fi
echo "Replication OK"
