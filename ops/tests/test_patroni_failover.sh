#!/usr/bin/env bash
# Failover Patroni THẬT trong Docker: 1 etcd + 2 node Patroni (đại diện hai zone). Kiểm:
#   1. cụm lên có đúng 1 leader + 1 replica đồng bộ; /primary chỉ 200 trên leader, /replica chỉ 200 trên replica;
#   2. ghi một đơn ("VP-12M-PHUQUOC") vào leader, rồi giết leader (docker kill = mất zone);
#   3. replica tự lên leader, dữ liệu còn nguyên, ghi được; in số giây từ lúc giết đến lúc /primary 200;
#   4. node cũ khởi động lại vào cụm như replica (pg_rewind/basebackup tự động) và thấy dữ liệu ghi sau failover.
#   5. cluster_probe.py báo ok khi đủ 2 node, no_replica khi chỉ còn leader mới, ok lại khi node cũ vào lại.
# Không đo được trên GCP; con số ở đây là cho cấu hình Patroni trong ops/patroni/patroni.yml. SKIP nếu không có Docker.
set -euo pipefail
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
command -v docker >/dev/null && docker info >/dev/null 2>&1 || { echo 'SKIP: cần Docker'; exit 0; }

id=$$; net=vota-patroni-net-$id; img=${PATRONI_TEST_IMAGE:-vota-patroni:test-$id}
etcd=vota-etcd-$id; n1=vota-pg1-$id; n2=vota-pg2-$id
cleanup() { docker rm -f "$etcd" "$n1" "$n2" >/dev/null 2>&1 || true
            docker volume rm "vol1-$id" "vol2-$id" >/dev/null 2>&1 || true
            docker network rm "$net" >/dev/null 2>&1 || true
            [[ -n "${PATRONI_TEST_IMAGE:-}" ]] || docker rmi "$img" >/dev/null 2>&1 || true; }
trap cleanup EXIT

[[ -n "${PATRONI_TEST_IMAGE:-}" ]] || docker build -q -t "$img" "$repo_root/ops/patroni" >/dev/null
docker network create "$net" >/dev/null
docker run -d --name "$etcd" --network "$net" quay.io/coreos/etcd:v3.5.17 etcd \
  --listen-client-urls http://0.0.0.0:2379 --advertise-client-urls "http://$etcd:2379" >/dev/null

start_node() { # start_node <name> <vol>
  docker run -d --name "$1" --network "$net" --hostname "$1" -v "$2:/var/lib/postgresql" \
    -e PATRONI_NAME="$1" -e PATRONI_NODE_IP="$1" -e PATRONI_ETCD3_HOSTS="$etcd:2379" \
    -e PATRONI_SUPERUSER_PASSWORD=su-pw -e PATRONI_REPLICATION_PASSWORD=repl-pw "$img" >/dev/null
}
rest() { docker exec "$1" curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8008/$2" 2>/dev/null || echo 000; }
psqln() { docker exec -u postgres "$1" psql -X -h /var/run/postgresql -U postgres -d postgres -Atqc "$2"; }
wait_for() { # wait_for <秒> <mô tả> <lệnh…>
  local limit=$1 what=$2; shift 2
  for _ in $(seq "$limit"); do if "$@" >/dev/null 2>&1; then return 0; fi; sleep 1; done
  echo "QUÁ HẠN: $what" >&2; docker logs --tail 25 "$n1" >&2 || true; docker logs --tail 25 "$n2" >&2 || true; exit 1
}
probe() { docker exec -e OUT=- "$1" /opt/patroni/bin/python /opt/vota/cluster_probe.py | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])'; }
is_leader() { [[ "$(rest "$1" primary)" == 200 ]]; }
is_replica() { [[ "$(rest "$1" replica)" == 200 ]]; }

docker volume create "vol1-$id" >/dev/null; docker volume create "vol2-$id" >/dev/null
echo '1. dựng cụm 2 node'
start_node "$n1" "vol1-$id"
wait_for 90 'node 1 thành leader' is_leader "$n1"
start_node "$n2" "vol2-$id"
wait_for 90 'node 2 thành replica' is_replica "$n2"
[[ "$(rest "$n1" replica)" != 200 && "$(rest "$n2" primary)" != 200 ]] || { echo '/primary và /replica phải loại trừ nhau'; exit 1; }
wait_for 60 'node 2 là replica đồng bộ' bash -c "docker exec $n1 curl -s http://127.0.0.1:8008/cluster | grep -q sync_standby"

[[ "$(probe "$n1")" == ok ]] || { echo 'probe phải báo ok khi đủ leader + replica'; exit 1; }
echo '2. ghi đơn rồi giết leader'
psqln "$n1" "CREATE TABLE booking_demo(id int primary key, ref text); INSERT INTO booking_demo VALUES (1,'VP-12M-PHUQUOC')"
t0=$(date +%s)
docker kill "$n1" >/dev/null

echo '3. replica tự lên leader'
wait_for 120 'node 2 thành leader sau khi mất node 1' is_leader "$n2"
rto=$(( $(date +%s) - t0 ))
[[ "$(psqln "$n2" 'SELECT ref FROM booking_demo WHERE id=1')" == VP-12M-PHUQUOC ]] || { echo 'mất dữ liệu sau failover'; exit 1; }
psqln "$n2" "INSERT INTO booking_demo VALUES (2,'SAU-FAILOVER')"
wait_for 60 'probe báo no_replica khi chỉ còn một node' bash -c "[[ \$(docker exec -e OUT=- $n2 /opt/patroni/bin/python /opt/vota/cluster_probe.py | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"status\"])') == no_replica ]]"
echo "   /primary 200 trên node mới sau ${rto}s kể từ lúc giết leader (local, chưa phải GCP)"
(( rto <= 90 )) || { echo "failover quá chậm: ${rto}s"; exit 1; }

echo '4. node cũ vào lại như replica'
docker start "$n1" >/dev/null
wait_for 150 'node cũ vào lại làm replica' is_replica "$n1"
wait_for 30 'node cũ có dữ liệu ghi sau failover' bash -c "[[ \$(docker exec -u postgres $n1 psql -X -h /var/run/postgresql -U postgres -d postgres -Atqc 'SELECT count(*) FROM booking_demo') == 2 ]]"
[[ "$(psqln "$n1" 'SELECT pg_is_in_recovery()')" == t ]] || { echo 'node cũ phải ở chế độ recovery'; exit 1; }
wait_for 60 'probe báo ok lại khi đủ 2 node' bash -c "[[ \$(docker exec -e OUT=- $n2 /opt/patroni/bin/python /opt/vota/cluster_probe.py | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"status\"])') == ok ]]"
echo "PASS: failover trong ${rto}s, không mất dữ liệu, node cũ tự vào lại"
