#!/usr/bin/env bash
# Đặt update policy của MIG app về OPPORTUNISTIC TRƯỚC khi Terraform đổi template, để lần apply đầu tiên (khi MIG
# còn PROACTIVE) không tự thay hết VM. Idempotent: đã OPPORTUNISTIC thì không làm gì.
# Dùng bởi .github/workflows/staging-ha-{backend,frontend}-cd.yml, trước bước apply.
#
# Biến môi trường: GCP_PROJECT_ID (bắt buộc), MIG_NAME (vota-ha-app), MIG_REGION (asia-southeast1)
set -euo pipefail

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID là bắt buộc}"
MIG_NAME="${MIG_NAME:-vota-ha-app}"
MIG_REGION="${MIG_REGION:-asia-southeast1}"

current="$(gcloud compute instance-groups managed describe "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" \
  --format='value(updatePolicy.type)')"
if [ "$current" = "OPPORTUNISTIC" ]; then
  echo "MIG $MIG_NAME đã là OPPORTUNISTIC."
  exit 0
fi

echo "MIG $MIG_NAME đang là '${current:-?}': đặt OPPORTUNISTIC để đổi template không thay VM."
token="$(gcloud auth print-access-token)"
# Giữ nguyên các trường khác của policy (khớp main.tf) để Terraform không thấy drift.
curl -fsS -X PATCH \
  -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  "https://compute.googleapis.com/compute/v1/projects/$GCP_PROJECT_ID/regions/$MIG_REGION/instanceGroupManagers/$MIG_NAME" \
  -d '{"updatePolicy":{"type":"OPPORTUNISTIC","minimalAction":"REPLACE","replacementMethod":"SUBSTITUTE","maxSurge":{"fixed":0},"maxUnavailable":{"fixed":3}}}' >/dev/null

# PATCH là thao tác bất đồng bộ; đợi policy hiện ra rồi mới cho Terraform chạy.
for _ in $(seq 1 30); do
  current="$(gcloud compute instance-groups managed describe "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" \
    --format='value(updatePolicy.type)')"
  [ "$current" = "OPPORTUNISTIC" ] && { echo "Đã đặt OPPORTUNISTIC."; exit 0; }
  sleep 2
done
echo "Không đặt được OPPORTUNISTIC (hiện: ${current:-?})." >&2
exit 1
