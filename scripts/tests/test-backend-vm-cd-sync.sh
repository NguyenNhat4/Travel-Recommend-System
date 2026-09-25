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

echo 'backend VM CD sync checks passed'
