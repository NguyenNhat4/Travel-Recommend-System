#!/usr/bin/env bash
# Chạy ops/check-db-direct.sh với một Postgres Docker tạm: đường đạt, loopback bị từ chối, thiếu chỗ kết nối, sai mật khẩu.
set -euo pipefail
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
script="$repo_root/ops/check-db-direct.sh"
command -v docker >/dev/null && docker info >/dev/null 2>&1 || { echo 'SKIP: cần Docker'; exit 0; }

name=vota-check-db-test; port=${TEST_PG_PORT:-55433}
tmp=$(mktemp -d); trap 'docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$tmp"' EXIT
# Máy chưa cài psql: shim chạy psql trong container client, đổi -h sang host.docker.internal để tới cổng publish.
if ! command -v psql >/dev/null; then
  mkdir "$tmp/bin"
  cat > "$tmp/bin/psql" <<'SHIM'
#!/usr/bin/env bash
args=(); skip=0
for a in "$@"; do
  if [[ $skip -eq 1 ]]; then args+=("host.docker.internal"); skip=0; continue; fi
  if [[ "$a" == "-h" ]]; then args+=("-h"); skip=1; continue; fi
  args+=("$a")
done
exec docker run --rm -e PGPASSWORD -e PGCONNECT_TIMEOUT postgres:16 psql "${args[@]}"
SHIM
  chmod +x "$tmp/bin/psql"; export PATH="$tmp/bin:$PATH"
fi
printf 'secret' > "$tmp/pw"; printf 'wrong' > "$tmp/bad"
docker run -d --name "$name" -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=vota -p "127.0.0.1:$port:5432" \
  postgres:16 -c max_connections=30 >/dev/null
for _ in $(seq 40); do docker exec "$name" pg_isready -U postgres -d vota >/dev/null 2>&1 && break; sleep 1; done
sleep 2
# Dùng 127.0.0.2 làm "tên khác loopback" để vượt kiểm tra loopback của script mà vẫn nối được container local.
host=127.0.0.2

run() { env DB_HOST="$host" DB_PORT="$port" DB_USER=postgres "$@" "$script"; }

echo '1. đạt: 1 VM × 2 worker × 5 kết nối + 10 dự trữ = 20 ≤ 30'
run DB_PASSWORD_FILE="$tmp/pw" VMS=1 WORKERS=2 CONNS_PER_WORKER=5 | grep -q 'OK: đủ chỗ kết nối'

echo '2. loopback bị từ chối (tunnel SSH)'
if DB_HOST=127.0.0.1 DB_PORT="$port" DB_USER=postgres DB_PASSWORD_FILE="$tmp/pw" "$script" 2>"$tmp/err"; then echo 'phải fail'; exit 1; fi
grep -q 'tunnel SSH' "$tmp/err"

echo '3. vượt max_connections: 4 VM × 2 worker × 10 + 10 = 90 > 30'
if run DB_PASSWORD_FILE="$tmp/pw" 2>"$tmp/err"; then echo 'phải fail'; exit 1; fi
grep -q 'vượt max_connections=30' "$tmp/err"

echo '4. sai mật khẩu'
if run DB_PASSWORD_FILE="$tmp/bad" 2>"$tmp/err"; then echo 'phải fail'; exit 1; fi
grep -q 'không kết nối được' "$tmp/err"
echo 'PASS'
