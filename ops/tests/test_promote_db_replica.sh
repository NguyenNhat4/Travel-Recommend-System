#!/usr/bin/env bash
# Chạy ops/promote-db-replica.sh với một cặp Postgres primary/replica streaming THẬT trong Docker (gcloud là bản giả
# ghi lại lời gọi và dừng container primary). Kiểm: dry run, thứ tự dừng primary -> promote -> đổi DNS, dữ liệu còn
# nguyên trên replica mới, replica mới ghi được, chạy lại không làm gì, và thiếu biến thì từ chối.
set -euo pipefail
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
script="$repo_root/ops/promote-db-replica.sh"
command -v docker >/dev/null && docker info >/dev/null 2>&1 || { echo 'SKIP: cần Docker'; exit 0; }

id=$$; net=vota-promote-net-$id; pri=vota-promote-primary-$id; rep=vota-promote-replica-$id; vol=vota-promote-vol-$id
tmp=$(mktemp -d)
cleanup() { docker rm -f "$pri" "$rep" >/dev/null 2>&1 || true; docker volume rm "$vol" >/dev/null 2>&1 || true
            docker network rm "$net" >/dev/null 2>&1 || true; rm -rf "$tmp"; }
trap cleanup EXIT

docker network create "$net" >/dev/null
docker run -d --name "$pri" --network "$net" -e POSTGRES_PASSWORD=pw postgres:16 \
  -c wal_level=replica -c max_wal_senders=5 -c hot_standby=on >/dev/null
for _ in $(seq 40); do docker exec "$pri" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
sleep 2
docker exec "$pri" sh -c 'echo "host replication all all trust" >> "$PGDATA/pg_hba.conf"'
docker exec -u postgres "$pri" psql -U postgres -qc 'SELECT pg_reload_conf()' >/dev/null
docker exec -u postgres "$pri" psql -U postgres -qc "CREATE TABLE booking_demo(id int primary key, ref text); INSERT INTO booking_demo VALUES (1,'VP-12M-PHUQUOC')"

docker volume create "$vol" >/dev/null
docker run --rm --network "$net" -v "$vol":/var/lib/postgresql/data -u postgres postgres:16 \
  pg_basebackup -h "$pri" -U postgres -D /var/lib/postgresql/data -R -X stream >/dev/null
docker run -d --name "$rep" --network "$net" -v "$vol":/var/lib/postgresql/data postgres:16 >/dev/null
for _ in $(seq 40); do docker exec "$rep" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
sleep 2

rq() { docker exec -u postgres "$rep" psql -X -U postgres -d postgres -Atqc "$1"; }
for _ in $(seq 20); do [[ "$(rq 'SELECT count(*) FROM booking_demo' 2>/dev/null || echo 0)" == 1 ]] && break; sleep 1; done
[[ "$(rq 'SELECT pg_is_in_recovery()')" == t ]] || { echo 'replica phải là standby ban đầu'; exit 1; }

# gcloud giả: ghi lại, và "tắt VM primary" bằng cách dừng container.
log="$tmp/gcloud.log"; : > "$log"
cat > "$tmp/gcloud" <<FAKE
#!/usr/bin/env bash
case "\$*" in
  *"instances stop"*) echo "stop \$4 replica_in_recovery=\$(docker exec -u postgres $rep psql -X -U postgres -Atqc 'SELECT pg_is_in_recovery()')" >> "$log"; docker stop $pri >/dev/null ;;
  *"dns record-sets update"*) echo "dns \$*  replica_in_recovery=\$(docker exec -u postgres $rep psql -X -U postgres -Atqc 'SELECT pg_is_in_recovery()')" >> "$log" ;;
  *) echo "lệnh gcloud không mong đợi: \$*" >> "$log"; exit 9 ;;
esac
FAKE
chmod +x "$tmp/gcloud"

run() {
  env PRIMARY_VM=vm-primary REPLICA_VM=vm-replica REPLICA_IP=10.148.0.4 ZONE=asia-southeast1-a DNS_ZONE=vota-ha-internal \
      GCLOUD="$tmp/gcloud" REPLICA_PSQL_TEST="docker exec -u postgres $rep psql -X -U postgres -d postgres -Atqc" \
      CATCHUP_SECONDS=10 "$script" "$@"
}

echo '1. dry run: không gọi gcloud, replica vẫn là standby'
run > "$tmp/out1" 2>&1
grep -q 'Dry run' "$tmp/out1"
[[ ! -s "$log" ]]
[[ "$(rq 'SELECT pg_is_in_recovery()')" == t ]]

echo '2. thiếu biến bắt buộc thì từ chối'
if env -u REPLICA_IP PRIMARY_VM=a REPLICA_VM=b ZONE=z DNS_ZONE=d "$script" --yes >/dev/null 2>&1; then echo 'phải fail'; exit 1; fi

echo '3. failover thật: dừng primary -> promote -> đổi DNS'
start=$(date +%s)
bash -c "$(declare -f run); tmp='$tmp'; rep='$rep'; script='$script'; run --yes" > "$tmp/out3" 2>&1 || { cat "$tmp/out3"; exit 1; }
elapsed=$(( $(date +%s) - start ))
grep -q '^stop vm-primary replica_in_recovery=t' "$log"         # lúc dừng primary replica còn là standby
grep -q 'replica_in_recovery=f' <(grep '^dns ' "$log")          # lúc đổi DNS replica đã được nâng
grep -q -- '--rrdatas 10.148.0.4' "$log"
[[ "$(sed -n 1p "$log" | cut -d' ' -f1)" == stop && "$(sed -n 2p "$log" | cut -d' ' -f1)" == dns ]]
[[ "$(rq 'SELECT pg_is_in_recovery()')" == f ]]
[[ "$(rq 'SELECT ref FROM booking_demo WHERE id = 1')" == VP-12M-PHUQUOC ]]   # dữ liệu còn nguyên
rq "INSERT INTO booking_demo VALUES (2,'sau-failover')" >/dev/null           # replica mới ghi được
[[ "$(rq 'SELECT count(*) FROM booking_demo')" == 2 ]]
grep -q 'KHÔNG bật lại vm-primary' "$tmp/out3"
echo "   failover xong sau ${elapsed}s (cục bộ; trên cloud cộng thời gian dừng VM và TTL DNS 30s)"

echo '4. chạy lại khi replica đã là primary: không làm gì thêm'
before=$(wc -l < "$log")
if bash -c "$(declare -f run); tmp='$tmp'; rep='$rep'; script='$script'; run --yes" >"$tmp/out4" 2>&1; then echo 'phải fail'; exit 1; fi
grep -q 'không ở chế độ standby' "$tmp/out4"
[[ "$(wc -l < "$log")" == "$before" ]]
echo 'PASS'
