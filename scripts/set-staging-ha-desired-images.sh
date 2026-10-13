#!/usr/bin/env bash
# Ghi image mong muốn vào all-instances config của MIG vota-ha-app (metadata vota-backend-image, vota-frontend-image).
# VM do autoscaler hoặc autohealing tạo ra đọc hai khoá này khi boot (startup.sh.tftpl), nên luôn khởi động đúng bản
# đang triển khai mà không cần Terraform đổi template. MIG là OPPORTUNISTIC (pin-staging-ha-mig-opportunistic.sh chạy
# trước): đổi config không thay VM đang chạy; image trên VM đang chạy do roll-staging-ha-app-slots.sh đổi.
#
# Biến môi trường (bắt buộc): BACKEND_REF, FRONTEND_REF (image@sha256:...), GCP_PROJECT_ID
# Tuỳ chọn: MIG_NAME (vota-ha-app), MIG_REGION (asia-southeast1)
set -euo pipefail

: "${BACKEND_REF:?BACKEND_REF là bắt buộc}"
: "${FRONTEND_REF:?FRONTEND_REF là bắt buộc}"
: "${GCP_PROJECT_ID:?GCP_PROJECT_ID là bắt buộc}"
MIG_NAME="${MIG_NAME:-vota-ha-app}"
MIG_REGION="${MIG_REGION:-asia-southeast1}"

for ref in "$BACKEND_REF" "$FRONTEND_REF"; do
  [[ "$ref" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || { echo "ref không hợp lệ: $ref" >&2; exit 1; }
done

gcloud compute instance-groups managed all-instances-config update "$MIG_NAME" \
  --region "$MIG_REGION" --project "$GCP_PROJECT_ID" \
  --metadata="vota-backend-image=$BACKEND_REF,vota-frontend-image=$FRONTEND_REF" >/dev/null

got="$(gcloud compute instance-groups managed describe "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" --format=json \
  | jq -r '.allInstancesConfig.properties.metadata // {} | "\(."vota-backend-image") \(."vota-frontend-image")"')"
[ "$got" = "$BACKEND_REF $FRONTEND_REF" ] || { echo "all-instances config chưa nhận image mong muốn: $got" >&2; exit 1; }
echo "Image mong muốn của $MIG_NAME đã ghi."
