#!/usr/bin/env bash
# Compatibility entrypoint: the VM job now crawls fresh Trip.com room JSON,
# normalizes a fresh multi-source catalog and upserts PostgreSQL immediately.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/run_fresh_catalog_vm.sh" "$@"
