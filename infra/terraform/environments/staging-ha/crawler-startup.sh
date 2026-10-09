#!/bin/bash
# Khởi động VM job cào: chỉ cài Docker và cron, tạo thư mục dữ liệu. Không cài cron của crawler và không chạy job:
# CD (.github/workflows/staging-ha-cd.yml) cài cron bằng scripts/install-vota-cron.sh sau khi đã có env file.
# Env file (/etc/vota/fresh-catalog.env) đặt qua CD khi có GCE_CRAWLER_ENV_SECRET; chưa có thì giữ file đặt tay.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq docker.io cron jq curl ca-certificates
systemctl enable --now docker cron

mkdir -p /etc/vota /opt/vota/bin /srv/vota/fresh-catalog-data /srv/vota/fresh-catalog-logs
chmod 755 /etc/vota /opt/vota /opt/vota/bin
