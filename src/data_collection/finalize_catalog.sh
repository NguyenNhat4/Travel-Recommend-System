#!/usr/bin/env bash
# Chốt catalog sau khi các terminal cào đã dừng: sao lưu → gộp job batch → chuẩn hoá → xuất catalog.
#   ./finalize_catalog.sh
# Xem trước con số mà không đụng catalog chính: nút "Tạo bản xem trước" trong `python monitor.py`.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-$HOME/miniconda3/envs/vsf/bin/python}"

if pgrep -f "python.*(batch|crawl)\.py" >/dev/null; then
  echo "Vẫn còn tiến trình cào đang chạy (batch.py/crawl.py). Dừng chúng (Ctrl+C trong terminal) rồi chạy lại." >&2
  exit 1
fi

stamp="$(date +%Y%m%d-%H%M%S)"
backup="data/backups/finalize-$stamp"
mkdir -p "$backup/interim"
cp -a data/interim/. "$backup/interim/"
for f in products.jsonl products.csv products.json stats.md SCHEMA.md BANGIAO.md template.json; do [ -f "data/$f" ] && cp -a "data/$f" "$backup/"; done
echo "Đã sao lưu vào $backup"

"$PY" batch.py merge
"$PY" normalise.py --no-plan --rooms-per-hotel 0 --flights-per-route 0
"$PY" catalog.py cities
"$PY" catalog.py split
"$PY" catalog.py merge
"$PY" make_template.py
"$PY" make_sample.py
"$PY" make_docs.py
"$PY" parse_combos.py
echo "Xong. Xem data/stats.md, data/excluded_auto.csv (điểm bị loại theo quy tắc), data/excluded_location.csv (dòng bị xoá vì cảnh báo vị trí) và data/quality_review.csv."
