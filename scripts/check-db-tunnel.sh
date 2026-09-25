#!/usr/bin/env bash
# Verify the loopback SSH forward to the separate PostgreSQL VM.
set -euo pipefail

host='127.0.0.1'
port='15432'
timeout_seconds='5'

usage() {
  cat <<'EOF'
Usage:
  check-db-tunnel.sh [--host 127.0.0.1] [--port 15432] [--timeout SECONDS]
EOF
}

die() {
  printf 'check-db-tunnel.sh: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      [ "$#" -ge 2 ] || die '--host requires a value'
      host="$2"
      shift 2
      ;;
    --port)
      [ "$#" -ge 2 ] || die '--port requires a value'
      port="$2"
      shift 2
      ;;
    --timeout)
      [ "$#" -ge 2 ] || die '--timeout requires a value'
      timeout_seconds="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ "$host" == 127.0.0.1 || "$host" == localhost ]] || die 'DB tunnel host must be loopback'
[[ "$port" =~ ^[0-9]+$ ]] || die 'DB tunnel port must be numeric'
[[ "$timeout_seconds" =~ ^[0-9]+$ ]] || die 'timeout must be numeric'
command -v nc >/dev/null 2>&1 || die 'nc is required to verify the DB tunnel'

if ! nc -z -w "$timeout_seconds" "$host" "$port" >/dev/null 2>&1; then
  die "DB SSH tunnel is unavailable at $host:$port"
fi

printf 'DB SSH tunnel is ready at %s:%s.\n' "$host" "$port"
