#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
workflow="$repo_root/.github/workflows/backend-ci-cd.yml"
compose="$repo_root/ops/docker-compose.backend-vm.yml"
deploy="$repo_root/scripts/deploy-backend-vm.sh"
frontend_deploy="$repo_root/scripts/deploy-frontend-vm.sh"
frontend_workflow="$repo_root/.github/workflows/frontend-ci-cd.yml"
crawler_workflow="$repo_root/.github/workflows/crawler-ci-cd.yml"

for file in "$workflow" "$frontend_workflow" "$crawler_workflow" "$compose" "$deploy" "$frontend_deploy"; do
  test -f "$file" || { echo "missing required file: $file" >&2; exit 1; }
done

grep -q 'docker-compose.backend-vm.yml' "$workflow"
grep -q 'install -D -m 0644' "$workflow"
grep -q 'GCE_COMPOSE_FILE' "$workflow"
grep -q '\$GITHUB_WORKSPACE/scripts' "$workflow"
grep -q '\$GITHUB_WORKSPACE/ops' "$workflow"

tar -czf - \
  -C "$repo_root/scripts" deploy-backend-vm.sh check-db-tunnel.sh \
  -C "$repo_root/ops" docker-compose.backend-vm.yml \
  | tar -tzf - >/dev/null

grep -q 'network_mode: host' "$compose"
grep -q '/etc/vota/backend.env' "$compose"
grep -q '/etc/vota/backend-secrets:/app/secrets:ro' "$compose"
grep -q 'vota-backend@sha256:0000000000000000000000000000000000000000000000000000000000000000' "$compose"
! grep -q ':latest' "$compose"
grep -q 'BACKEND_DIGEST: \${{ needs.publish.outputs.backend_digest }}' "$workflow"
grep -Fq 'backend_ref="$BACKEND_IMAGE@$BACKEND_DIGEST"' "$workflow"
grep -Fq 'docker pull '\''$crawler_ref'\''' "$crawler_workflow"
grep -Fq 'PULL=0' "$crawler_workflow"
grep -Fq 'crawler_ref="$CRAWLER_IMAGE@$CRAWLER_DIGEST"' "$crawler_workflow"
grep -Fq -- '--image '\''$crawler_ref'\''' "$crawler_workflow"
grep -Fq 'PULL=0 $runner run' "$repo_root/scripts/install-vota-cron.sh"
grep -Fq 'PULL=0 $runner fresh-run tick' "$repo_root/scripts/install-vota-cron.sh"
grep -Fq -- '--frontend-image '\''$FRONTEND_IMAGE@$FRONTEND_DIGEST'\''' "$frontend_workflow"
grep -Fq 'FRONTEND_DIGEST: ${{ needs.publish_vm.outputs.frontend_digest }}' "$frontend_workflow"
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
grep -Fq -- '--migrate-dsn-stdin' "$workflow"
grep -Fq 'gcloud secrets versions access latest --secret "$MIGRATE_DB_SECRET"' "$workflow"
if grep -Fq 'secrets.MIGRATE_DATABASE_URL' "$workflow"; then
  echo 'migration DSN must come from Secret Manager, not a GitHub secret' >&2
  exit 1
fi
if grep -Eq 'migrate\.env|--env-file' "$deploy"; then
  echo 'migration DSN must come from stdin, not an env file' >&2
  exit 1
fi
grep -Fq 'COPY db/migrations' "$repo_root/Dockerfile.backend"
grep -Fq "'db/migrations/**'" "$workflow"
# Migration phải chạy trước khi recreate container.
migrate_line=$(grep -n 'db/migrations/run.py' "$deploy" | grep -v DRY-RUN | head -1 | cut -d: -f1)
recreate_line=$(grep -n 'up -d --force-recreate --no-deps "\$backend_service"; then' "$deploy" | head -1 | cut -d: -f1)
[ -n "$migrate_line" ] && [ -n "$recreate_line" ] && [ "$migrate_line" -lt "$recreate_line" ] || { echo 'migration must run before Backend recreate' >&2; exit 1; }
grep -Fq 'IMAGE@sha256:DIGEST' "$deploy"
if grep -Eq 'crawler|CRAWLER|Dockerfile.daily|run_daily_docker' "$workflow"; then
  echo 'backend workflow must not deploy the crawler' >&2
  exit 1
fi

sync_action="$repo_root/.github/actions/sync-env-from-secret-manager/action.yml"
test -f "$sync_action"
grep -Fq 'gcloud secrets versions access latest --secret "$SECRET"' "$sync_action"
grep -Fq 'sudo -n tee "$f"' "$sync_action"
grep -Fq 'name: Sync backend env from Secret Manager' "$workflow"
grep -Fq 'name: Sync backend env from Secret Manager' "$frontend_workflow"
grep -Fq 'name: Sync crawler env from Secret Manager' "$crawler_workflow"
for wf in "$workflow" "$frontend_workflow" "$crawler_workflow"; do
  grep -Fq 'uses: ./.github/actions/sync-env-from-secret-manager' "$wf"
done
grep -Fq 'vars.GCE_BACKEND_ENV_SECRET' "$workflow"
grep -Fq 'vars.GCE_BACKEND_ENV_SECRET' "$frontend_workflow"
grep -Fq 'vars.GCE_CRAWLER_ENV_SECRET' "$crawler_workflow"

echo 'backend VM CD sync checks passed'
