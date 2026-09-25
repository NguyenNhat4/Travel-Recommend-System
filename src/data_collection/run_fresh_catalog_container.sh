#!/usr/bin/env bash
# Runs in the crawler image; the VM host needs only Docker and a mounted data directory.
set -euo pipefail

mode="${1:-auto}"
[[ "$#" -le 1 && "$mode" =~ ^(auto|full|daily|index|status|--auto|--full|--daily|--index|--status)$ ]] || {
  echo 'Usage: crawler image [auto|full|daily|index|status]' >&2
  exit 2
}
mode="${mode#--}"
if [[ "$mode" == status || "$mode" == index ]]; then
  exec python /app/src/data_collection/fresh_catalog.py "$mode"
fi
exec xvfb-run -a -s '-screen 0 1366x768x24' python /app/src/data_collection/fresh_catalog.py "$mode"
