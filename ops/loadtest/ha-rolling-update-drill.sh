#!/usr/bin/env bash
# Diễn tập rolling update dưới tải (docs/plan/2026-10-07-ha-vung-crawler-rolling.md §5.1): chạy k6 150 VU, tới đoạn bằng phẳng
# thì ép MIG thay toàn bộ VM với đúng update_policy của main.tf (max_surge 3, max_unavailable 0, min_ready_sec >= boot-to-ready),
# trong lúc đó lấy mẫu số backend HEALTHY của LB mỗi SAMPLE_SECONDS. Đạt khi: không mẫu nào còn 0 backend sẵn sàng
# (và không tụt dưới MIN_HEALTHY), và k6 qua ngưỡng lỗi < 1%, p95 < 800 ms.
#
#   BASE_URL=http://<lb-ip> PROJECT=... REGION=asia-southeast1 MIG=vota-ha-app BACKEND_SERVICE=vota-ha-app \
#   MIN_HEALTHY=3 ops/loadtest/ha-rolling-update-drill.sh --yes
#
# Không có --yes chỉ in kế hoạch (dry run). Cần k6 và gcloud đã đăng nhập. KHÔNG chạy trên production.
set -Eeuo pipefail

BASE_URL=${BASE_URL:?set BASE_URL}
PROJECT=${PROJECT:?set PROJECT}
REGION=${REGION:?set REGION}
MIG=${MIG:?set MIG}
BACKEND_SERVICE=${BACKEND_SERVICE:?set BACKEND_SERVICE}
MIN_READY_SECONDS=${MIN_READY_SECONDS:-360}  # = boot_to_ready_seconds trong Terraform
MIN_HEALTHY=${MIN_HEALTHY:-1}            # = min_replicas: surge thêm VM nên không bao giờ được thấp hơn
WARMUP_SECONDS=${WARMUP_SECONDS:-300}    # k6-ha.js lên 150 VU sau ~2 phút; đợi tới đoạn bằng phẳng
SAMPLE_SECONDS=${SAMPLE_SECONDS:-10}
MAX_DRILL_SECONDS=${MAX_DRILL_SECONDS:-1500}
GCLOUD=${GCLOUD:-gcloud}
K6=${K6:-k6}
K6_SCRIPT=${K6_SCRIPT:-$(dirname "$0")/k6-ha.js}  # 150 VU mặc định; 1 VM dùng k6-ha-1vm.js (20 VU)
OUT=${OUT:-$(mktemp -d)/rolling-drill}
CONFIRM=0; [[ "${1:-}" == "--yes" ]] && CONFIRM=1
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

cat <<PLAN
Kế hoạch diễn tập:
  1. k6 -e BASE_URL=$BASE_URL k6-ha.js (nền)
  2. đợi ${WARMUP_SECONDS}s tới đoạn 150 VU
  3. $GCLOUD compute instance-groups managed rolling-action replace $MIG --region $REGION --max-surge 3 --max-unavailable 0  (min_ready_sec lấy từ update_policy trong main.tf = ${MIN_READY_SECONDS}s; gcloud GA không có cờ --min-ready)
  4. mỗi ${SAMPLE_SECONDS}s đếm backend HEALTHY của $BACKEND_SERVICE, kết thúc khi MIG ổn định hoặc sau ${MAX_DRILL_SECONDS}s
  5. đạt khi min(HEALTHY) >= $MIN_HEALTHY và k6 qua ngưỡng. Kết quả: $OUT.*
PLAN
[[ $CONFIRM -eq 1 ]] || { echo 'Dry run: thêm --yes để thực hiện.'; exit 0; }

"$K6" run -e BASE_URL="$BASE_URL" "$K6_SCRIPT" > "$OUT.k6.txt" 2>&1 &
k6_pid=$!
trap 'kill "$k6_pid" 2>/dev/null || true' EXIT
sleep "$WARMUP_SECONDS"

"$GCLOUD" compute instance-groups managed rolling-action replace "$MIG" --project "$PROJECT" --region "$REGION" \
  --max-surge 3 --max-unavailable 0 --quiet
echo "ts,healthy" > "$OUT.healthy.csv"
min_seen=999
end=$(( $(date +%s) + MAX_DRILL_SECONDS ))
while (( $(date +%s) < end )); do
  healthy=$("$GCLOUD" compute backend-services get-health "$BACKEND_SERVICE" --global --project "$PROJECT" --format=json 2>/dev/null \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(1 for g in d for s in g.get("status",{}).get("healthStatus",[]) if s.get("healthState")=="HEALTHY"))' || echo 0)
  echo "$(date +%s),$healthy" >> "$OUT.healthy.csv"
  (( healthy < min_seen )) && min_seen=$healthy
  stable=$("$GCLOUD" compute instance-groups managed describe "$MIG" --project "$PROJECT" --region "$REGION" --format='value(status.isStable)' 2>/dev/null || echo False)
  [[ "$stable" == True ]] && break
  sleep "$SAMPLE_SECONDS"
done

wait "$k6_pid" && k6_ok=1 || k6_ok=0
trap - EXIT
echo "Backend HEALTHY thấp nhất trong lúc thay: $min_seen (cần >= $MIN_HEALTHY); k6 $( ((k6_ok)) && echo 'QUA ngưỡng' || echo 'TRƯỢT ngưỡng' )"
(( min_seen >= MIN_HEALTHY && k6_ok == 1 )) || { echo 'KHÔNG ĐẠT: xem '"$OUT"'.healthy.csv và '"$OUT"'.k6.txt'; exit 1; }
echo 'ĐẠT'
