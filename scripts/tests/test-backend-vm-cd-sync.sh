#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
workflow="$repo_root/.github/workflows/backend-ci-cd.yml"
compose="$repo_root/ops/docker-compose.backend-vm.yml"
deploy="$repo_root/scripts/deploy-backend-vm.sh"

for file in "$workflow" "$compose" "$deploy"; do
  test -f "$file" || { echo "missing required file: $file" >&2; exit 1; }
done

grep -q 'docker-compose.backend-vm.yml' "$workflow"
grep -q 'install -D -m 0644' "$workflow"
grep -q 'GCE_COMPOSE_FILE' "$workflow"
grep -q '\$GITHUB_WORKSPACE/scripts' "$workflow"
grep -q '\$GITHUB_WORKSPACE/src/data_collection' "$workflow"
grep -q '\$GITHUB_WORKSPACE/ops' "$workflow"

tar -czf - \
  -C "$repo_root/scripts" deploy-backend-vm.sh install-vota-cron.sh check-db-tunnel.sh \
  -C "$repo_root/src/data_collection" run_daily_docker.sh \
  -C "$repo_root/ops" docker-compose.backend-vm.yml \
  | tar -tzf - >/dev/null

grep -q 'network_mode: host' "$compose"
grep -q '/etc/vota/backend.env' "$compose"
grep -q '/etc/vota/backend-secrets:/app/secrets:ro' "$compose"
grep -q 'v-ota-data-pipeline-crawler/vota-backend:latest' "$compose"
if grep -Eq '^  (postgres|redis|weaviate):' "$compose"; then
  echo 'application VM Compose must not manage database or dependency services' >&2
  exit 1
fi

grep -q 'JWT_PRIVATE_KEY_PATH' "$deploy"
grep -q 'AUTH_REDIS_URL' "$deploy"
grep -q '/app/secrets' "$deploy"
grep -q -- '--no-deps' "$deploy"
grep -q 'Restart crawler monitor with published image' "$workflow"
grep -q 'docker rm -f vota-daily-monitor' "$workflow"
grep -q 'CONTAINER_NAME=vota-daily' "$workflow"
grep -q 'PULL=0' "$workflow"
grep -q 'docker inspect --format' "$workflow"

echo 'backend VM CD sync checks passed'
