#!/usr/bin/env bash
# Install or replace the managed data-collection cron entry without touching
# unrelated crontab entries. Images must be an immutable digest reference (IMAGE@sha256:DIGEST);
# the :latest tag is rejected.
# Exactly ONE crawler job may write to the catalog DB: --job legacy (daily.py, `run`; the default, so the current
# CD keeps its behaviour) or --job fresh (fresh_catalog.py, `fresh-run tick` every 15 minutes). Both use the same
# managed block, so installing one replaces the other (docs/guide/trien-khai-job-cao-du-lieu.md).
set -euo pipefail

BEGIN_MARKER='# BEGIN VOTA CRAWLER'
END_MARKER='# END VOTA CRAWLER'
job='legacy'
schedule=''
image=''
runner=''
data_dir=''
env_file=''
log_dir='/srv/vota/fresh-catalog-logs'
crontab_file=''
dry_run=0

usage() {
  cat <<'EOF'
Usage:
  install-vota-cron.sh --image IMAGE@sha256:DIGEST --runner /absolute/path/run_daily_docker.sh
                       [--job legacy|fresh] [--data-dir PATH] [--env-file PATH] [--log-dir PATH]
                       [--schedule CRON] [--crontab-file PATH] [--dry-run]

  --job legacy  daily.py (`run`) at 02:00; defaults /srv/vota/daily-data, /etc/vota/daily.env
  --job fresh   fresh_catalog.py (`fresh-run tick`) every 15 minutes (run time is set in the monitor);
                defaults /srv/vota/fresh-catalog-data, /etc/vota/fresh-catalog.env, --log-dir /srv/vota/fresh-catalog-logs

The managed block is replaced atomically, so only one crawler job is ever scheduled. Unrelated crontab lines are
preserved.
EOF
}

die() {
  printf 'install-vota-cron.sh: %s\n' "$*" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --job)
      [ "$#" -ge 2 ] || die '--job requires a value'
      job="$2"
      shift 2
      ;;
    --log-dir)
      [ "$#" -ge 2 ] || die '--log-dir requires a value'
      log_dir="$2"
      shift 2
      ;;
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

case "$job" in
  legacy) : "${schedule:=0 2 * * *}" "${data_dir:=/srv/vota/daily-data}" "${env_file:=/etc/vota/daily.env}" ;;
  fresh) : "${schedule:=*/15 * * * *}" "${data_dir:=/srv/vota/fresh-catalog-data}" "${env_file:=/etc/vota/fresh-catalog.env}" ;;
  *) die '--job must be legacy or fresh' ;;
esac
[ -n "$image" ] || die '--image is required'
[ -n "$runner" ] || die '--runner is required'
[[ "$image" =~ @sha256:[a-f0-9]{64}$ ]] || die '--image must be an immutable sha256 digest (IMAGE@sha256:DIGEST); :latest is not accepted'
[[ "$runner" == /* ]] || die '--runner must be an absolute path'
if [[ "$runner" == *" "* || "$runner" == *$'\t'* || "$runner" == *"'"* ]]; then
  die '--runner cannot contain whitespace or single quotes'
fi
[[ "$data_dir" == /* ]] || die '--data-dir must be an absolute path'
[[ "$env_file" == /* ]] || die '--env-file must be an absolute path'
[[ "$log_dir" == /* ]] || die '--log-dir must be an absolute path'
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
if [ "$job" = fresh ]; then
  cron_line="$schedule FRESH_IMAGE='$image' FRESH_DATA_DIR='$data_dir' CATALOG_ENV_FILE='$env_file' CATALOG_LOG_DIR='$log_dir' PULL=0 $runner fresh-run tick"
else
  cron_line="$schedule IMAGE='$image' DATA_DIR='$data_dir' ENV_FILE='$env_file' PULL=0 $runner run"
fi
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

printf 'Installed managed VOTA crawler cron (%s job) at %s.\n' "$job" "${schedule}"
