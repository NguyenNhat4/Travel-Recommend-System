#!/usr/bin/env bash
# Cổng sẵn sàng sau khi roll (dùng chung cho staging-ha-app-cd.yml và staging-ha-infra-cd.yml):
#   1. MIG stable, số VM = targetSize, mọi VM RUNNING và MIG không thao tác.
#   2. LB báo đủ targetSize instance HEALTHY (tối đa 10 phút; min_ready_sec = 0 nên MIG có thể stable sớm hơn LB).
#   3. /health/ready qua public endpoint (Cloudflare -> LB) đạt READY_STREAK lần 200 liên tiếp, cách READY_INTERVAL giây.
# Image trên từng VM đã được roll-staging-ha-app-slots.sh đối chiếu (mode report trên mọi VM).
#
# Biến môi trường (bắt buộc): GCP_PROJECT_ID, STAGING_HA_URL
# Tuỳ chọn: MIG_NAME (vota-ha-app), MIG_REGION (asia-southeast1), BACKEND_SERVICE (vota-ha-app), READY_STREAK (3), READY_INTERVAL (5)
set -euo pipefail

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID là bắt buộc}"
: "${STAGING_HA_URL:?STAGING_HA_URL là bắt buộc}"
MIG_NAME="${MIG_NAME:-vota-ha-app}"
MIG_REGION="${MIG_REGION:-asia-southeast1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-vota-ha-app}"
READY_STREAK="${READY_STREAK:-3}"
READY_INTERVAL="${READY_INTERVAL:-5}"

gcloud compute instance-groups managed wait-until "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" --stable --timeout=1800

mig_json="$(gcloud compute instance-groups managed describe "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" --format=json)"
target_size="$(jq -er .targetSize <<< "$mig_json")"
instances="$(gcloud compute instance-groups managed list-instances "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" --format=json)"
[ "$(jq 'length' <<< "$instances")" = "$target_size" ] || { echo "Số VM khác targetSize $target_size" >&2; exit 1; }
bad="$(jq -r '.[] | select(.instanceStatus != "RUNNING" or .currentAction != "NONE") | .instance | split("/") | last' <<< "$instances")"
[ -z "$bad" ] || { echo "VM chưa RUNNING hoặc MIG đang thao tác: $bad" >&2; exit 1; }

healthy=0
for _ in $(seq 1 60); do
  health="$(gcloud compute backend-services get-health "$BACKEND_SERVICE" --global --project "$GCP_PROJECT_ID" --format=json)"
  # get-health trả về mảng (một mục mỗi backend group), không phải object.
  healthy="$(jq '[(if type == "array" then .[] else . end) | .status.healthStatus[]? | select(.healthState == "HEALTHY")] | length' <<< "$health")"
  [ "$healthy" = "$target_size" ] && break
  sleep 10
done
[ "$healthy" = "$target_size" ] || { echo "LB chỉ có $healthy/$target_size instance HEALTHY sau 10 phút" >&2; exit 1; }
echo "LB: $healthy/$target_size HEALTHY"

ok=0
for i in $(seq 1 90); do
  code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$STAGING_HA_URL/health/ready" || true)"
  if [ "$code" = 200 ]; then
    ok=$((ok + 1))
  else
    ok=0
    echo "attempt $i: $code"
  fi
  [ "$ok" -ge "$READY_STREAK" ] && break
  sleep "$READY_INTERVAL"
done
[ "$ok" -ge "$READY_STREAK" ] || { echo "Readiness chưa đạt $READY_STREAK lần liên tiếp." >&2; exit 1; }
echo "Readiness công khai: $READY_STREAK lần 200 liên tiếp"
