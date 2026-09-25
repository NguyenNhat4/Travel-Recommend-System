#!/usr/bin/env bash
# Runs in the crawler image; the VM host needs only Docker and a mounted data directory.
set -euo pipefail

mode="${1:-auto}"
[[ "$#" -le 1 && "$mode" =~ ^(auto|full|daily|index|status|due|tick|--auto|--full|--daily|--index|--status|--due|--tick)$ ]] || {
  echo 'Usage: crawler image [auto|full|daily|index|status|due|tick]' >&2
  exit 2
}
mode="${mode#--}"
if [[ "$mode" == tick ]]; then
  due="$(python /app/src/data_collection/fresh_catalog.py due)"
  [[ -n "$due" ]] || exit 0
fi
if [[ "$mode" == status || "$mode" == index || "$mode" == due ]]; then
  exec python /app/src/data_collection/fresh_catalog.py "$mode"
fi
exec xvfb-run -a -s '-screen 0 1366x768x24' python /app/src/data_collection/fresh_catalog.py "$mode"
