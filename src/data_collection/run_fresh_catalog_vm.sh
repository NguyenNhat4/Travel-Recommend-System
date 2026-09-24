#!/usr/bin/env bash
# One-repository fresh catalog entrypoint for a console-only Ubuntu VM.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../.." && pwd)"
if [[ -n "${CATALOG_ENV_FILE:-}" ]]; then
  [[ -r "$CATALOG_ENV_FILE" ]] || { echo "Cannot read $CATALOG_ENV_FILE" >&2; exit 2; }
  set -a
  . "$CATALOG_ENV_FILE"
  set +a
fi
python_bin="${PYTHON_BIN:-python3}"
mode="${1:-auto}"
[[ "$#" -le 1 && "$mode" =~ ^(auto|full|daily|status|--auto|--full|--daily|--status)$ ]] || {
  echo 'Usage: run_fresh_catalog_vm.sh [auto|full|daily|status]' >&2; exit 2;
}
mode="${mode#--}"
if [[ "$mode" != status ]]; then
  if [[ "${DB_TARGET:-local}" == local && "${START_POSTGRES:-1}" == 1 ]]; then
    docker compose -f "${DB_COMPOSE_FILE:-$repo_root/docker-compose.yml}" up -d --wait postgres
  fi
  command -v xvfb-run >/dev/null || { echo 'Install xvfb for console VM' >&2; exit 2; }
  exec xvfb-run -a -s '-screen 0 1366x768x24' "$python_bin" "$here/fresh_catalog.py" "$mode"
fi
exec "$python_bin" "$here/fresh_catalog.py" status
