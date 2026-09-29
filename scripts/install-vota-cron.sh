#!/usr/bin/env bash
# Install or replace the managed data-collection cron entry without touching
# unrelated crontab entries. The managed entry pins the published image digest.
set -euo pipefail

BEGIN_MARKER='# BEGIN VOTA CRAWLER'
END_MARKER='# END VOTA CRAWLER'
schedule='0 2 * * *'
image=''
runner=''
data_dir='/srv/vota/daily-data'
env_file='/etc/vota/daily.env'
crontab_file=''
dry_run=0

usage() {
  cat <<'EOF'
Usage:
  install-vota-cron.sh --image IMAGE@sha256:DIGEST --runner /absolute/path/run_daily_docker.sh
                       [--data-dir PATH] [--env-file PATH] [--schedule '0 2 * * *']
                       [--crontab-file PATH] [--dry-run]

The managed block is replaced atomically. Unrelated crontab lines are preserved.
EOF
}

die() {
  printf 'install-vota-cron.sh: %s\n' "$*" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --image)
      [ "$#" -ge 2 ] || die '--image requires a value'
      image="$2"
      shift 2
      ;;
    --runner)
      [ "$#" -ge 2 ] || die '--runner requires a value'
      runner="$2"
      shift 2
      ;;
    --data-dir)
      [ "$#" -ge 2 ] || die '--data-dir requires a value'
      data_dir="$2"
      shift 2
      ;;
    --env-file)
      [ "$#" -ge 2 ] || die '--env-file requires a value'
      env_file="$2"
      shift 2
      ;;
    --schedule)
      [ "$#" -ge 2 ] || die '--schedule requires a value'
      schedule="$2"
      shift 2
      ;;
    --crontab-file)
      [ "$#" -ge 2 ] || die '--crontab-file requires a value'
      crontab_file="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[ -n "$image" ] || die '--image is required'
[ -n "$runner" ] || die '--runner is required'
[[ "$image" =~ ^asia-southeast1-docker\.pkg\.dev/[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die '--image must use an Artifact Registry digest'
[[ "$runner" == /* ]] || die '--runner must be an absolute path'
if [[ "$runner" == *" "* || "$runner" == *$'\t'* || "$runner" == *"'"* ]]; then
  die '--runner cannot contain whitespace or single quotes'
fi
[[ "$data_dir" == /* ]] || die '--data-dir must be an absolute path'
[[ "$env_file" == /* ]] || die '--env-file must be an absolute path'
[ "$(wc -w <<< "$schedule")" -eq 5 ] || die '--schedule must contain five cron fields'

read_crontab() {
  if [ -n "$crontab_file" ]; then
    [ -e "$crontab_file" ] && cat "$crontab_file" || true
  else
    crontab -l 2>/dev/null || true
  fi
}

existing_crontab="$(read_crontab)"
filtered_crontab="$(awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
  $0 == begin { inside=1; next }
  $0 == end { inside=0; next }
  !inside { print }
' <<< "$existing_crontab")"

cron_line="$schedule IMAGE='$image' DATA_DIR='$data_dir' ENV_FILE='$env_file' PULL=0 $runner run"
updated_crontab="$(printf '%s\n%s\n%s\n%s\n' "$filtered_crontab" "$BEGIN_MARKER" "$cron_line" "$END_MARKER")"

if [ "$dry_run" -eq 1 ]; then
  printf '%s' "$updated_crontab"
  exit 0
fi

if [ -n "$crontab_file" ]; then
  target_dir="$(dirname -- "$crontab_file")"
  mkdir -p "$target_dir"
  temp_file="$(mktemp "$target_dir/.vota-crontab.XXXXXX")"
  trap 'rm -f "$temp_file"' EXIT
  printf '%s' "$updated_crontab" > "$temp_file"
  mv "$temp_file" "$crontab_file"
else
  temp_file="$(mktemp)"
  trap 'rm -f "$temp_file"' EXIT
  printf '%s' "$updated_crontab" > "$temp_file"
  crontab "$temp_file"
fi

printf 'Installed managed VOTA crawler cron at %s.\n' "${schedule}"
