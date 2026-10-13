#!/usr/bin/env bash
# Builder BuildKit cố định trên runner tự host (mọi runner chung một VM và một Docker daemon). setup-buildx-action
# tạo builder mới mỗi job nên mất toàn bộ cache cục bộ (build frontend mất 210 s chỉ để tải cache GHA, 2026-10-12).
# Builder này giữ state qua các job: PR build làm nóng cache, CD sau merge build lại gần như toàn bộ từ cache.
# Định nghĩa builder để ở BUILDX_CONFIG dùng chung; DOCKER_CONFIG (đăng nhập registry) vẫn riêng từng job.
#
# In ra GITHUB_ENV: BUILDX_CONFIG. In ra GITHUB_OUTPUT: name.
set -euo pipefail

NAME="${BUILDER_NAME:-vota-builder}"
export BUILDX_CONFIG="${BUILDX_CONFIG:-$HOME/.vota-buildx}"
mkdir -p "$BUILDX_CONFIG"

# docker-buildx là CLI plugin; DOCKER_CONFIG riêng của job không có thư mục cli-plugins.
if [ -n "${DOCKER_CONFIG:-}" ] && [ -x "$HOME/.docker/cli-plugins/docker-buildx" ]; then
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  ln -sf "$HOME/.docker/cli-plugins/docker-buildx" "$DOCKER_CONFIG/cli-plugins/docker-buildx"
fi

if ! docker buildx inspect "$NAME" >/dev/null 2>&1; then
  # Hai job tạo cùng lúc: một lệnh create lỗi "existing instance", kiểm lại thay vì dừng.
  docker buildx create --name "$NAME" --driver docker-container >/dev/null 2>&1 || docker buildx inspect "$NAME" >/dev/null
fi
docker buildx inspect --bootstrap "$NAME" >/dev/null

[ -z "${GITHUB_ENV:-}" ] || echo "BUILDX_CONFIG=$BUILDX_CONFIG" >> "$GITHUB_ENV"
[ -z "${GITHUB_OUTPUT:-}" ] || echo "name=$NAME" >> "$GITHUB_OUTPUT"
echo "builder $NAME sẵn sàng"
