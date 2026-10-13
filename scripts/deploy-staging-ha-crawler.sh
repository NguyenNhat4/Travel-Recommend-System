#!/usr/bin/env bash
# Cài job cào (fresh catalog) lên VM crawler của staging-ha qua IAP SSH: copy runner, cài cron, khởi động monitor.
# Dùng bởi .github/workflows/staging-ha-crawler-cd.yml.
#
# Biến môi trường (bắt buộc):
#   GCP_PROJECT_ID, CRAWLER_INSTANCE, CRAWLER_ZONE
#   CRAWLER_REF   image@sha256:...   (digest bất biến của crawler)
# Tuỳ chọn (mặc định giống VM staging cũ):
#   CRAWLER_RUNNER    /opt/vota/bin/run_daily_docker.sh
#   CRAWLER_DATA_DIR  /srv/vota/fresh-catalog-data
#   CRAWLER_ENV_FILE  /etc/vota/fresh-catalog.env
#   CRAWLER_LOG_DIR   /srv/vota/fresh-catalog-logs
#
# Env file phải có sẵn trên VM (đặt tay hoặc qua sync Secret Manager). Script không tạo env file và dừng nếu thiếu.
set -euo pipefail

die() {
  printf 'deploy-staging-ha-crawler.sh: %s\n' "$*" >&2
  exit 1
}

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID là bắt buộc}"
: "${CRAWLER_INSTANCE:?CRAWLER_INSTANCE là bắt buộc}"
: "${CRAWLER_ZONE:?CRAWLER_ZONE là bắt buộc}"
: "${CRAWLER_REF:?CRAWLER_REF là bắt buộc}"

CRAWLER_RUNNER="${CRAWLER_RUNNER:-/opt/vota/bin/run_daily_docker.sh}"
CRAWLER_DATA_DIR="${CRAWLER_DATA_DIR:-/srv/vota/fresh-catalog-data}"
CRAWLER_ENV_FILE="${CRAWLER_ENV_FILE:-/etc/vota/fresh-catalog.env}"
CRAWLER_LOG_DIR="${CRAWLER_LOG_DIR:-/srv/vota/fresh-catalog-logs}"

[[ "$CRAWLER_REF" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'CRAWLER_REF phải là image@sha256:<64 hex>'
for p in "$CRAWLER_RUNNER" "$CRAWLER_DATA_DIR" "$CRAWLER_ENV_FILE" "$CRAWLER_LOG_DIR"; do
  [[ "$p" =~ ^/[a-zA-Z0-9._/-]+$ ]] || die "đường dẫn không hợp lệ: $p"
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
remote_dir="/tmp/vota-crawler-cd-${GITHUB_RUN_ID:-local-$(date +%s)}-${GITHUB_RUN_ATTEMPT:-0}"
ssh_flags=(--project "$GCP_PROJECT_ID" --zone "$CRAWLER_ZONE" --tunnel-through-iap --quiet)

# 0. Docker trên VM đăng nhập Artifact Registry bằng access token của CI.
access_token="$(gcloud auth print-access-token)"
printf '%s' "$access_token" | gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" \
  --command 'docker login --username oauth2accesstoken --password-stdin https://asia-southeast1-docker.pkg.dev >/dev/null 2>&1 && echo docker-login-ok'

# 1. Copy script runner và installer lên VM.
tar -czf - -C "$REPO_ROOT/scripts" install-vota-cron.sh check-db-tunnel.sh \
  -C "$REPO_ROOT/src/data_collection" run_daily_docker.sh \
  | gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" \
      --command "umask 077; mkdir -m 700 '$remote_dir' && tar -xzf - -C '$remote_dir' && sudo -n install -D -m 0755 '$remote_dir/run_daily_docker.sh' '$CRAWLER_RUNNER' && sudo -n install -D -m 0755 '$remote_dir/install-vota-cron.sh' /opt/vota/bin/install-vota-cron.sh && sudo -n install -D -m 0755 '$remote_dir/check-db-tunnel.sh' /opt/vota/bin/check-db-tunnel.sh"

# 1b. Cấu hình Ops Agent của crawler vào cùng thư mục tạm (thư mục đã tạo ở bước 1).
tar -czf - -C "$REPO_ROOT/infra/monitoring" ops-agent-crawler.yaml \
  | gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" \
      --command "umask 077; tar -xzf - -C '$remote_dir'"

# 2. Env file phải đã có; không có thì dừng (crawler không được chạy với cấu hình thiếu).
# Cron chạy dưới user SSH, nên file phải đọc được bởi user đó (mode 600, cùng cách với VM cũ).
gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" \
  --command "sudo -n test -s '$CRAWLER_ENV_FILE' || { echo 'Thiếu env file $CRAWLER_ENV_FILE trên VM' >&2; exit 1; }; sudo -n chown \"\$(id -u):\$(id -g)\" '$CRAWLER_ENV_FILE' && chmod 600 '$CRAWLER_ENV_FILE'"

# 2b. Thư mục log thuộc user SSH (runner ghi log bằng user này). Thư mục dữ liệu thuộc UID/GID 10001 của container
# crawler (image chạy user 10001, xem run_daily_docker.sh: "tạo với UID/GID 10001 cho app trong image").
gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" \
  --command "sudo -n mkdir -p '$CRAWLER_DATA_DIR' '$CRAWLER_LOG_DIR' && sudo -n chown 10001:10001 '$CRAWLER_DATA_DIR' && sudo -n chown \"\$(id -u):\$(id -g)\" '$CRAWLER_LOG_DIR'"

# 2c. chown thư mục không đổi owner của file đã có. Nếu monitor-cd.log do user khác tạo (ví dụ chạy tay), lần
# `nohup ... > monitor-cd.log` sẽ lỗi Permission denied. Đưa file đó về user SSH trước khi khởi động monitor.
gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" \
  --command "f='$CRAWLER_LOG_DIR/monitor-cd.log'; [ ! -e \"\$f\" ] || sudo -n chown \"\$(id -u):\$(id -g)\" \"\$f\""

# 2d. Ops Agent đọc log các lượt cào (fresh-catalog-2*.log) và đưa JSON lên Cloud Logging, để ba cảnh báo crawler
# (infra/terraform/environments/staging-ha/crawler_monitoring.tf) có dữ liệu. Cấu hình riêng: infra/monitoring/ops-agent-crawler.yaml.
# Lỗi ở đây không chặn cài cron và monitor: cảnh báo "job cào không chạy" sẽ báo nếu log không lên.
ops_cmd='set -eu
if ! systemctl is-active --quiet google-cloud-ops-agent; then
  curl -fsSo /tmp/add-ops-agent-repo.sh https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
  sudo -n bash /tmp/add-ops-agent-repo.sh --also-install
fi
conf=/etc/google-cloud-ops-agent/config.yaml
if sudo -n test -f "$conf"; then sudo -n cp -a "$conf" "$conf.default"; fi
sudo -n install -D -m 0644 "__SRC__" "$conf"
if ! sudo -n systemctl restart google-cloud-ops-agent; then
  echo "Ops Agent không khởi động với cấu hình crawler, khôi phục cấu hình trước đó" >&2
  if sudo -n test -f "$conf.default"; then sudo -n cp -a "$conf.default" "$conf"; else sudo -n rm -f "$conf"; fi
  sudo -n systemctl restart google-cloud-ops-agent || true
  exit 1
fi
echo ops-agent-ok'
ops_cmd="${ops_cmd//__SRC__/$remote_dir/ops-agent-crawler.yaml}"
gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" --command "$ops_cmd" \
  || echo 'WARNING: cấu hình Ops Agent của crawler lỗi; xem journalctl -u google-cloud-ops-agent trên VM' >&2

# 3. Cài cron (thay khối cron cũ, giữ dòng khác của crontab).
gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" \
  --command "/opt/vota/bin/install-vota-cron.sh --job fresh --image '$CRAWLER_REF' --runner '$CRAWLER_RUNNER' --data-dir '$CRAWLER_DATA_DIR' --env-file '$CRAWLER_ENV_FILE' --log-dir '$CRAWLER_LOG_DIR'"

# 4. Khởi động monitor job cào.
# staging-ha tắt realtime: BACKEND_URL trống (xem history/2026-10-09-realtime-tat-staging-ha.md).
remote_monitor="set -eu; docker rm -f vota-daily-monitor vota-fresh-catalog-monitor 2>/dev/null || true; docker pull '$CRAWLER_REF'; mkdir -p '$CRAWLER_DATA_DIR' '$CRAWLER_LOG_DIR'; nohup env FRESH_IMAGE='$CRAWLER_REF' FRESH_DATA_DIR='$CRAWLER_DATA_DIR' CATALOG_ENV_FILE='$CRAWLER_ENV_FILE' CATALOG_LOG_DIR='$CRAWLER_LOG_DIR' PULL=0 MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1 BACKEND_URL='' '$CRAWLER_RUNNER' fresh-monitor > '$CRAWLER_LOG_DIR/monitor-cd.log' 2>&1 < /dev/null & for attempt in \$(seq 1 30); do status=\$(docker inspect --format '{{.State.Status}}' vota-fresh-catalog-monitor 2>/dev/null || true); if [ \"\$status\" = running ]; then '$CRAWLER_RUNNER' prune-images '$CRAWLER_REF' || true; exit 0; fi; sleep 1; done; tail -n 100 '$CRAWLER_LOG_DIR/monitor-cd.log' || true; exit 1"
gcloud compute ssh "$CRAWLER_INSTANCE" "${ssh_flags[@]}" --command "$remote_monitor"
