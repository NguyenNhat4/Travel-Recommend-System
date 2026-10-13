#!/usr/bin/env bash
# Content key của một image: hash các đối tượng git (tree/blob) của mọi đường dẫn đầu vào của image đó.
# Hai commit có cùng đầu vào cho cùng key, nên CD tái dùng image đã build thay vì build lại, và biết thành phần nào
# đổi so với bản đang chạy (key trong last-good). Thêm đường dẫn vào đây khi Dockerfile COPY thêm thư mục.
#
#   scripts/ci/image-key.sh backend|frontend|crawler|slot   -> in 20 ký tự hex
set -euo pipefail

case "${1:-}" in
  backend)  paths=(Dockerfile.backend .dockerignore src/backend src/shared/contracts src/shared/mocks db/migrations) ;;
  frontend) paths=(src/frontend .dockerignore src/shared/mocks src/shared/contracts/tests) ;;
  crawler)  paths=(Dockerfile.fresh-catalog Dockerfile.fresh-catalog.dockerignore src/backend src/data_collection) ;;
  # Không phải image: cơ chế deploy trên VM (proxy, slot, roll). Đổi thì App CD roll lại với image hiện có.
  slot)     paths=(infra/terraform/environments/staging-ha/slot-deploy.sh scripts/roll-staging-ha-app-slots.sh) ;;
  *) echo "dùng: $0 backend|frontend|crawler|slot" >&2; exit 2 ;;
esac

for p in "${paths[@]}"; do
  printf '%s %s\n' "$p" "$(git rev-parse "HEAD:$p")"
done | sha256sum | cut -c1-20
