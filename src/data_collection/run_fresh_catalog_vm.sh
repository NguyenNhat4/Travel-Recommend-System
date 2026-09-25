#!/usr/bin/env bash
# Compatibility entrypoint: the fresh crawler now runs entirely in Docker.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/run_daily_docker.sh" fresh-run "$@"
