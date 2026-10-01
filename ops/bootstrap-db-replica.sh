#!/usr/bin/env bash
# Run on the REPLICA DB VM (created by infra/terraform/environments/staging).
# Same image, network and layout as ops/bootstrap-db-vm.sh, but the data volume is
# filled with pg_basebackup from the primary and the container starts as a hot standby.
# Re-running preserves an existing container and volume. To rebuild the replica from
# scratch, remove the container and volume first (see docs/guide/van-hanh-db-replica.md).
set -Eeuo pipefail

PRIMARY_HOST=${PRIMARY_HOST:?set PRIMARY_HOST to the primary DB VM private IP}
# The replica must run the same image (same major version and extensions) as the primary.
# Read it from the primary: sudo docker inspect vota-postgres --format '{{.Config.Image}}'
IMAGE=${IMAGE:?set IMAGE to the exact image the primary runs}
REGISTRY_HOST=${REGISTRY_HOST:-asia-southeast1-docker.pkg.dev}
CONTAINER_NAME=${CONTAINER_NAME:-vota-postgres}
NETWORK_NAME=${NETWORK_NAME:-app-private}
VOLUME_NAME=${VOLUME_NAME:-vota-pg18}
SLOT_NAME=${SLOT_NAME:-vota_replica}
SECRETS_DIR=${SECRETS_DIR:-/etc/vota/secrets}
REPL_PASSWORD_FILE=${REPL_PASSWORD_FILE:-$SECRETS_DIR/replicator_password}
# Must match the primary PGDATA (sudo docker exec vota-postgres printenv PGDATA); the volume mounts its parent.
PGDATA_DIR=${PGDATA_DIR:-/var/lib/postgresql/18/docker}

[[ "$PRIMARY_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'PRIMARY_HOST must be an IPv4 address' >&2; exit 2; }

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then SUDO=(); else SUDO=(sudo); fi

if [[ ! -f /etc/debian_version ]]; then
  echo 'This bootstrap currently supports Debian/Ubuntu Compute Engine images.' >&2
  exit 2
fi
if [[ ! -s "$REPL_PASSWORD_FILE" ]]; then
  echo "missing $REPL_PASSWORD_FILE: copy it from the primary VM (mode 600)" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo 'Installing Docker'
  "${SUDO[@]}" apt-get update
  DEBIAN_FRONTEND=noninteractive "${SUDO[@]}" apt-get install -y ca-certificates curl docker.io jq openssl
fi
"${SUDO[@]}" systemctl enable --now docker

metadata_get() {
  curl --fail --silent --show-error -H 'Metadata-Flavor: Google' \
    "http://metadata.google.internal/computeMetadata/v1/$1"
}

if [[ "$IMAGE" == "$REGISTRY_HOST"/* ]]; then
  access_token=$(metadata_get instance/service-accounts/default/token | jq -er .access_token)
  printf '%s' "$access_token" | "${SUDO[@]}" docker login \
    --username oauth2accesstoken --password-stdin "https://$REGISTRY_HOST"
fi
"${SUDO[@]}" docker pull "$IMAGE"

replica_ip=${DB_PRIVATE_IP:-$(metadata_get instance/network-interfaces/0/ip)}
echo "Replica private IP: $replica_ip (allow it on the primary: REPLICA_IP=$replica_ip ops/bootstrap-db-primary-replication.sh)"

"${SUDO[@]}" docker network inspect "$NETWORK_NAME" >/dev/null 2>&1 || "${SUDO[@]}" docker network create "$NETWORK_NAME" >/dev/null
"${SUDO[@]}" docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1 || "${SUDO[@]}" docker volume create "$VOLUME_NAME" >/dev/null

if ! "${SUDO[@]}" docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  has_data=$("${SUDO[@]}" docker run --rm --entrypoint sh --mount source="$VOLUME_NAME",target=/var/lib/postgresql \
    "$IMAGE" -c "test -f $PGDATA_DIR/PG_VERSION && echo yes || echo no")
  if [[ "$has_data" == no ]]; then
    echo "Taking base backup from $PRIMARY_HOST (slot $SLOT_NAME)"
    # -R writes standby.signal and primary_conninfo; -X stream keeps WAL consistent.
    # Run as the postgres user so file ownership matches the server process.
    "${SUDO[@]}" docker run --rm --user postgres --entrypoint sh \
      --mount source="$VOLUME_NAME",target=/var/lib/postgresql \
      --mount type=bind,src="$REPL_PASSWORD_FILE",dst=/run/secrets/replicator_password,readonly \
      "$IMAGE" -c "
        set -eu
        mkdir -p $PGDATA_DIR && chmod 700 $PGDATA_DIR
        PGPASSWORD=\$(cat /run/secrets/replicator_password) \
          pg_basebackup -h '$PRIMARY_HOST' -U replicator -D $PGDATA_DIR -R -X stream -S '$SLOT_NAME' -P"
  else
    echo 'Volume already holds a data directory; skipping base backup'
  fi

  # hot_standby_feedback avoids cancelled long reads at the cost of delayed vacuum on the primary.
  "${SUDO[@]}" docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --network "$NETWORK_NAME" \
    --publish="${replica_ip}:5432:5432" \
    --mount source="$VOLUME_NAME",target=/var/lib/postgresql \
    --health-cmd='pg_isready -h 127.0.0.1 -U postgres' \
    --health-interval=10s --health-timeout=5s --health-retries=6 \
    "$IMAGE" \
    postgres -c hot_standby=on -c hot_standby_feedback=on -c max_standby_streaming_delay=60s >/dev/null
else
  echo "Container $CONTAINER_NAME already exists; preserving it and its volume"
  if [[ "$("${SUDO[@]}" docker inspect --format '{{.State.Status}}' "$CONTAINER_NAME")" != 'running' ]]; then
    "${SUDO[@]}" docker start "$CONTAINER_NAME" >/dev/null
  fi
fi

for attempt in $(seq 1 60); do
  status=$("${SUDO[@]}" docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER_NAME")
  case "$status" in
    healthy) break ;;
    unhealthy|exited|dead)
      "${SUDO[@]}" docker logs --tail=80 "$CONTAINER_NAME" >&2
      echo "PostgreSQL replica container is $status" >&2
      exit 1
      ;;
  esac
  sleep 2
  if [[ "$attempt" == 60 ]]; then
    "${SUDO[@]}" docker logs --tail=80 "$CONTAINER_NAME" >&2
    echo 'Timed out waiting for the replica healthcheck' >&2
    exit 1
  fi
done

in_recovery=$("${SUDO[@]}" docker exec -u postgres "$CONTAINER_NAME" psql -X -U postgres -Atqc 'SELECT pg_is_in_recovery()')
[[ "$in_recovery" == t ]] || { echo 'Replica is not in recovery mode' >&2; exit 1; }
echo 'DB replica bootstrap complete (hot standby streaming from the primary)'
echo "Read-only PostgreSQL is reachable privately at ${replica_ip}:5432"
