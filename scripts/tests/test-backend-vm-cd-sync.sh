#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose="$repo_root/ops/docker-compose.backend-vm.yml"
deploy="$repo_root/scripts/deploy-backend-vm.sh"
frontend_deploy="$repo_root/scripts/deploy-frontend-vm.sh"

for file in "$compose" "$deploy" "$frontend_deploy"; do
  test -f "$file" || { echo "missing required file: $file" >&2; exit 1; }
done


tar -czf - \
  -C "$repo_root/scripts" deploy-backend-vm.sh check-db-tunnel.sh \
  -C "$repo_root/ops" docker-compose.backend-vm.yml \
  | tar -tzf - >/dev/null

grep -q 'network_mode: host' "$compose"
grep -q '/etc/vota/backend.env' "$compose"
grep -q '/etc/vota/backend-secrets:/app/secrets:ro' "$compose"
grep -q 'vota-backend@sha256:0000000000000000000000000000000000000000000000000000000000000000' "$compose"
! grep -q ':latest' "$compose"
grep -Fq 'PULL=0 $runner run' "$repo_root/scripts/install-vota-cron.sh"
grep -Fq 'PULL=0 $runner fresh-run tick' "$repo_root/scripts/install-vota-cron.sh"
grep -Fq "backend_health_url='http://127.0.0.1:8000/health/ready'" "$frontend_deploy"
if grep -Eq '^  (postgres|redis|weaviate):' "$compose"; then
  echo 'application VM Compose must not manage database or dependency services' >&2
  exit 1
fi

grep -q 'JWT_PRIVATE_KEY_PATH' "$deploy"
grep -q 'AUTH_REDIS_URL' "$deploy"
grep -Fq 'ALLOWED_ORIGINS: ${ALLOWED_ORIGINS:-}' "$compose"
grep -Fq 'read_backend_optional_value ALLOWED_ORIGINS' "$frontend_deploy"
grep -q '/app/secrets' "$deploy"
grep -q -- '--no-deps' "$deploy"
grep -Fq 'db/migrations/run.py' "$deploy"
grep -Fq 'SEED_DATABASE_URL' "$deploy"
grep -Fq -- '--migrate-dsn-stdin' "$deploy"
if grep -Eq 'migrate\.env|--env-file' "$deploy"; then
  echo 'migration DSN must come from stdin, not an env file' >&2
  exit 1
fi
grep -Fq 'COPY db/migrations' "$repo_root/Dockerfile.backend"
# Migration phải chạy trước khi recreate container.
migrate_line=$(grep -n 'db/migrations/run.py' "$deploy" | grep -v DRY-RUN | head -1 | cut -d: -f1)
recreate_line=$(grep -n 'up -d --force-recreate --no-deps "\$backend_service"; then' "$deploy" | head -1 | cut -d: -f1)
[ -n "$migrate_line" ] && [ -n "$recreate_line" ] && [ "$migrate_line" -lt "$recreate_line" ] || { echo 'migration must run before Backend recreate' >&2; exit 1; }
grep -Fq 'IMAGE@sha256:DIGEST' "$deploy"

sync_action="$repo_root/.github/actions/sync-env-from-secret-manager/action.yml"
test -f "$sync_action"
grep -Fq 'gcloud secrets versions access latest --secret "$SECRET"' "$sync_action"
grep -Fq 'sudo -n tee "$f"' "$sync_action"

echo 'backend VM CD sync checks passed'
