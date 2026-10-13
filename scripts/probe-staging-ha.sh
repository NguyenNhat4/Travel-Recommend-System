#!/usr/bin/env bash
# Đo gián đoạn trong lúc deploy: `start` chạy nền, mỗi giây gọi /health/ready và trang chủ qua public endpoint;
# `stop` dừng và in tóm tắt (vào $GITHUB_STEP_SUMMARY nếu có): số request, số request khác 200, chuỗi lỗi dài nhất.
# Chỉ đo, không làm job lỗi: một lần chập chờn của Cloudflare không được kích hoạt rollback.
#
# Biến môi trường: STAGING_HA_URL (bắt buộc), PROBE_LOG (mặc định $RUNNER_TEMP/probe.log), PROBE_MAX_SECONDS (3600)
set -euo pipefail

: "${STAGING_HA_URL:?STAGING_HA_URL là bắt buộc}"
PROBE_LOG="${PROBE_LOG:-${RUNNER_TEMP:-/tmp}/probe.log}"
PROBE_MAX_SECONDS="${PROBE_MAX_SECONDS:-3600}"
pid_file="$PROBE_LOG.pid"

case "${1:-}" in
  start)
    : > "$PROBE_LOG"
    (
      end=$(( $(date +%s) + PROBE_MAX_SECONDS ))
      while [ "$(date +%s)" -lt "$end" ]; do
        for path in /health/ready /; do
          code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$STAGING_HA_URL$path" || true)"
          printf '%s %s %s\n' "$(date +%s)" "$path" "${code:-000}" >> "$PROBE_LOG"
        done
        sleep 1
      done
    ) > /dev/null 2>&1 < /dev/null &
    echo "$!" > "$pid_file"
    echo "probe chạy nền (pid $(cat "$pid_file")), log $PROBE_LOG"
    ;;
  stop)
    [ -f "$pid_file" ] && kill "$(cat "$pid_file")" 2>/dev/null || true
    rm -f "$pid_file"
    [ -s "$PROBE_LOG" ] || { echo "probe không có dữ liệu"; exit 0; }
    summary="$(awk '
      { total++; if ($3 != "200") { bad++; if (start[$2] == "") start[$2] = $1; last[$2] = $1; run[$2] = $1 - start[$2] + 1; if (run[$2] > worst) worst = run[$2] }
        else { start[$2] = "" }
        if (first == "") first = $1; end = $1 }
      END { printf "Probe %d giây: %d request, %d khác 200, chuỗi lỗi dài nhất %d giây\n", end - first + 1, total, bad + 0, worst + 0 }' "$PROBE_LOG")"
    echo "$summary"
    grep -v ' 200$' "$PROBE_LOG" | head -20 || true
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
      { echo "### Đo gián đoạn trong lúc deploy"; echo; echo "$summary"; } >> "$GITHUB_STEP_SUMMARY"
    fi
    if grep -qv ' 200$' "$PROBE_LOG"; then echo "::warning::$summary"; fi
    ;;
  *) echo "dùng: $0 start|stop" >&2; exit 2 ;;
esac
