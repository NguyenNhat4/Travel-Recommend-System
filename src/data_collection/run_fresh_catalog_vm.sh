#!/usr/bin/env bash
# Fresh catalog entrypoint for a console-only VM. The Trip.com collector lives
# in the sibling tripcom-hotel-crawler checkout; normalization and DB helpers
# come from this repository. No historical products or interim are inputs.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${CATALOG_ENV_FILE:-}" ]]; then
  if [[ ! -r "$CATALOG_ENV_FILE" ]]; then
    echo "Cannot read CATALOG_ENV_FILE: $CATALOG_ENV_FILE" >&2
    exit 2
  fi
  set -a
  # This file is operator-owned shell configuration and must not be committed.
  . "$CATALOG_ENV_FILE"
  set +a
fi
crawler_root="${TRIP_CRAWLER_ROOT:-$repo_root/../tripcom-hotel-crawler}"
if [[ "$crawler_root" != /* ]]; then crawler_root="$repo_root/$crawler_root"; fi
if [[ ! -f "$crawler_root/scripts/run_catalog_vm.sh" ]]; then
  echo "Trip.com crawler checkout missing at $crawler_root" >&2
  exit 2
fi
export COLLECTION_ROOT="$repo_root/src/data_collection"
export DB_COMPOSE_FILE="${DB_COMPOSE_FILE:-$repo_root/docker-compose.yml}"
if [[ "${DB_TARGET:-local}" == local ]]; then
  export START_POSTGRES="${START_POSTGRES:-1}"
else
  export START_POSTGRES=0
fi
exec "$crawler_root/scripts/run_catalog_vm.sh" "$@"
