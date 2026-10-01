#!/usr/bin/env bash
# Run on the PRIMARY DB VM. Idempotent: prepares the primary to feed one streaming replica.
# Creates the replicator role (password from a file), a physical replication slot,
# a pg_hba rule for the replica IP, and caps WAL kept for the slot so an offline
# replica cannot fill the primary disk. No restart needed on PostgreSQL 16.
set -Eeuo pipefail

REPLICA_IP=${REPLICA_IP:?set REPLICA_IP to the replica private IP}
CONTAINER_NAME=${CONTAINER_NAME:-vota-postgres}
SLOT_NAME=${SLOT_NAME:-vota_replica}
SECRETS_DIR=${SECRETS_DIR:-/etc/vota/secrets}
REPL_PASSWORD_FILE=${REPL_PASSWORD_FILE:-$SECRETS_DIR/replicator_password}
MAX_SLOT_WAL_KEEP_SIZE=${MAX_SLOT_WAL_KEEP_SIZE:-2GB}

[[ "$REPLICA_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'REPLICA_IP must be an IPv4 address' >&2; exit 2; }
[[ "$SLOT_NAME" =~ ^[a-z_][a-z0-9_]*$ ]] || { echo 'SLOT_NAME must be a simple identifier' >&2; exit 2; }
[[ "$MAX_SLOT_WAL_KEEP_SIZE" =~ ^[0-9]+(MB|GB)$ ]] || { echo 'MAX_SLOT_WAL_KEEP_SIZE must look like 2GB' >&2; exit 2; }

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then SUDO=(); else SUDO=(sudo); fi

psql_exec() {
  "${SUDO[@]}" docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 "$@"
}

"${SUDO[@]}" install -d -m 700 "$SECRETS_DIR"
if [[ ! -s "$REPL_PASSWORD_FILE" ]]; then
  "${SUDO[@]}" sh -c 'umask 077; openssl rand -base64 36 | tr -d "\n" > "$1"' sh "$REPL_PASSWORD_FILE"
  echo "Generated $REPL_PASSWORD_FILE"
fi
"${SUDO[@]}" chmod 600 "$REPL_PASSWORD_FILE"
repl_password=$("${SUDO[@]}" cat "$REPL_PASSWORD_FILE")
[[ "$repl_password" =~ ^[A-Za-z0-9+/=]+$ ]] || { echo 'replicator password has unexpected characters' >&2; exit 1; }

# Password is passed as a psql variable, not on a command line or in a heredoc literal.
psql_exec -d postgres -v pw="$repl_password" <<'SQL'
SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'replicator')
            THEN 'ALTER ROLE replicator WITH REPLICATION LOGIN PASSWORD ' || quote_literal(:'pw')
            ELSE 'CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD ' || quote_literal(:'pw')
       END AS stmt \gset
:stmt
SQL

psql_exec -d postgres -Atqc "SELECT pg_create_physical_replication_slot('$SLOT_NAME') WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = '$SLOT_NAME')" >/dev/null
psql_exec -d postgres -qc "ALTER SYSTEM SET max_slot_wal_keep_size = '$MAX_SLOT_WAL_KEEP_SIZE'"

hba_file=$(psql_exec -d postgres -Atqc 'SHOW hba_file')
hba_line="host replication replicator ${REPLICA_IP}/32 scram-sha-256"
if "${SUDO[@]}" docker exec "$CONTAINER_NAME" grep -qxF "$hba_line" "$hba_file"; then
  echo 'pg_hba rule already present'
else
  "${SUDO[@]}" docker exec "$CONTAINER_NAME" sh -c "printf '%s\n' '$hba_line' >> '$hba_file'"
  echo 'pg_hba rule added'
fi
psql_exec -d postgres -Atqc 'SELECT pg_reload_conf()' >/dev/null

echo "wal_level=$(psql_exec -d postgres -Atqc 'SHOW wal_level') max_wal_senders=$(psql_exec -d postgres -Atqc 'SHOW max_wal_senders')"
echo 'Primary ready for replication.'
echo "Copy $REPL_PASSWORD_FILE to the replica VM at the same path (mode 600) before running ops/bootstrap-db-replica.sh."
