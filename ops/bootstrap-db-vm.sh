#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ID=${PROJECT_ID:-vinpearl-508801}
REGISTRY_HOST=${REGISTRY_HOST:-asia-southeast1-docker.pkg.dev}
IMAGE=${IMAGE:-$REGISTRY_HOST/$PROJECT_ID/v-ota/vota-db:pg16}
CONTAINER_NAME=${CONTAINER_NAME:-vota-postgres}
NETWORK_NAME=${NETWORK_NAME:-app-private}
VOLUME_NAME=${VOLUME_NAME:-vota-pg16}
SECRETS_DIR=${SECRETS_DIR:-/etc/vota/secrets}
PG_PASSWORD_FILE=${PG_PASSWORD_FILE:-$SECRETS_DIR/pg_password}

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

if [[ ! -f /etc/debian_version ]]; then
  echo 'This bootstrap currently supports Debian/Ubuntu Compute Engine images.' >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo 'Installing Docker'
  "${SUDO[@]}" apt-get update
  DEBIAN_FRONTEND=noninteractive "${SUDO[@]}" apt-get install -y \
    ca-certificates curl docker.io jq openssl
fi
"${SUDO[@]}" systemctl enable --now docker

metadata_get() {
  curl --fail --silent --show-error \
    -H 'Metadata-Flavor: Google' \
    "http://metadata.google.internal/computeMetadata/v1/$1"
}

service_account_email=$(metadata_get instance/service-accounts/default/email)
echo "VM service account: $service_account_email"
echo 'The VM service account must have Artifact Registry Reader (roles/artifactregistry.reader) on the repository.'

access_token=$(metadata_get instance/service-accounts/default/token | jq -er .access_token)
printf '%s' "$access_token" | "${SUDO[@]}" docker login \
  --username oauth2accesstoken --password-stdin "https://$REGISTRY_HOST"
"${SUDO[@]}" docker pull "$IMAGE"

db_private_ip=${DB_PRIVATE_IP:-$(metadata_get instance/network-interfaces/0/ip)}
echo "DB private IP: $db_private_ip"

"${SUDO[@]}" install -d -m 700 "$SECRETS_DIR"
if [[ ! -s "$PG_PASSWORD_FILE" ]]; then
  "${SUDO[@]}" sh -c 'umask 077; openssl rand -base64 48 > "$1"' sh "$PG_PASSWORD_FILE"
fi
"${SUDO[@]}" chmod 600 "$PG_PASSWORD_FILE"

if ! "${SUDO[@]}" docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
  "${SUDO[@]}" docker network create "$NETWORK_NAME" >/dev/null
fi
if ! "${SUDO[@]}" docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
  "${SUDO[@]}" docker volume create "$VOLUME_NAME" >/dev/null
fi

if ! "${SUDO[@]}" docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  "${SUDO[@]}" docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --log-opt max-size=50m --log-opt max-file=5 \
    --network "$NETWORK_NAME" \
    --publish="${db_private_ip}:5432:5432" \
    --env POSTGRES_DB=vota \
    --env POSTGRES_USER=postgres \
    --env POSTGRES_PASSWORD_FILE=/run/secrets/pg_password \
    --env POSTGRES_INITDB_ARGS='--auth-local=peer --auth-host=scram-sha-256' \
    --mount type=bind,src="$PG_PASSWORD_FILE",dst=/run/secrets/pg_password,readonly \
    --mount source="$VOLUME_NAME",target=/var/lib/postgresql \
    --health-cmd='pg_isready -h 127.0.0.1 -U postgres -d vota' \
    --health-interval=10s \
    --health-timeout=5s \
    --health-retries=6 \
    "$IMAGE" >/dev/null
else
  echo "Container $CONTAINER_NAME already exists; preserving it and its volume"
  if ! "${SUDO[@]}" docker network inspect \
      --format '{{range .Containers}}{{.Name}}{{end}}' "$NETWORK_NAME" 2>/dev/null | grep -qx "$CONTAINER_NAME"; then
    "${SUDO[@]}" docker network connect "$NETWORK_NAME" "$CONTAINER_NAME" 2>/dev/null || true
  fi
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
      echo "PostgreSQL container is $status" >&2
      exit 1
      ;;
  esac
  sleep 2
  if [[ "$attempt" == 60 ]]; then
    "${SUDO[@]}" docker logs --tail=80 "$CONTAINER_NAME" >&2
    echo 'Timed out waiting for PostgreSQL healthcheck' >&2
    exit 1
  fi
done

"${SUDO[@]}" docker run --rm \
  --network "$NETWORK_NAME" \
  --entrypoint /usr/local/bin/vota-db-bootstrap \
  --env PGHOST="$CONTAINER_NAME" \
  --env PGPORT=5432 \
  --env PGUSER=postgres \
  --env PGPASSWORD_FILE=/run/secrets/pg_password \
  --mount type=bind,src="$PG_PASSWORD_FILE",dst=/run/secrets/pg_password,readonly \
  "$IMAGE"

echo 'DB VM bootstrap complete'
echo "PostgreSQL is reachable privately at ${db_private_ip}:5432"
