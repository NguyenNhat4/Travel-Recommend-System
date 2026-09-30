#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install -D -m 0750 "$root_dir/vota-docker-event-watcher.py" /usr/local/libexec/vota-docker-event-watcher.py
install -D -m 0644 "$root_dir/vota-docker-event-watcher.service" /etc/systemd/system/vota-docker-event-watcher.service
install -d -m 0750 /var/log/vota
touch /var/log/vota/docker-events.jsonl
chmod 0640 /var/log/vota/docker-events.jsonl
systemctl daemon-reload
systemctl enable --now vota-docker-event-watcher.service
systemctl --no-pager --full status vota-docker-event-watcher.service
