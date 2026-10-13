#!/usr/bin/env bash
# Cài phụ thuộc Python của một job vào thư mục riêng theo hash các file requirements, thay cho Python hệ thống dùng
# chung giữa mọi runner (PIP_BREAK_SYSTEM_PACKAGES làm các job cài đè lên nhau). Thư mục đã có thì dùng lại; tạo
# trong thư mục tạm rồi mv để hai job cùng lúc không thấy bản cài dở. Xoá bản không dùng trong 14 ngày.
#
#   scripts/ci/py-deps.sh <tên> [--torch-cpu <file ghim torch>] <requirements...>   -> in đường dẫn cho PYTHONPATH
set -euo pipefail

name="$1"; shift
torch_file=""
if [ "${1:-}" = --torch-cpu ]; then torch_file="$2"; shift 2; fi
root="${PY_DEPS_ROOT:-$HOME/.vota-pydeps}"
key="$(cat "$@" ${torch_file:+"$torch_file"} | sha256sum | cut -c1-16)-$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
dir="$root/$name-$key"

if [ ! -d "$dir" ]; then
  mkdir -p "$root"
  tmp="$(mktemp -d "$root/.tmp-$name-XXXXXX")"
  args=()
  for f in "$@"; do args+=(-r "$f"); done
  if [ -n "$torch_file" ]; then
    # Một lần resolve: torch bản CPU ghim đúng như image (index PyTorch; bản PyPI kéo CUDA vài GB). --target không coi
    # gói đã cài là có sẵn, nên cài torch riêng rồi mới -r requirements sẽ kéo lại torch CUDA từ PyPI.
    torch_pin="$(grep -E '^torch==' "$torch_file" | sed -E 's/[[:space:]]*#.*//')+cpu"
    python3 -m pip install -q --disable-pip-version-check --target "$tmp" \
      --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
      "$torch_pin" "${args[@]}" >&2
  else
    python3 -m pip install -q --disable-pip-version-check --target "$tmp" "${args[@]}" >&2
  fi
  mv -T "$tmp" "$dir" 2>/dev/null || rm -rf "$tmp"   # job khác đã tạo xong trước: dùng bản đó
fi
touch "$dir"
find "$root" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null || true
echo "$dir"
