#!/usr/bin/env bash
# Đổi image app trên mọi VM của MIG vota-ha-app mà không gián đoạn, theo hai pha (xem slot-deploy.sh):
#   1. prepare: song song trên mọi VM, dựng slot mới bên cạnh slot đang phục vụ, chép /_next/static vào kho chung,
#      đợi ready. Một VM lỗi thì `abort` trên mọi VM (slot đang phục vụ không bị đụng) và dừng.
#   2. switch: VM đầu tiên trước (canary), rồi các VM còn lại song song. Mỗi switch chỉ đổi proxy cục bộ (vài giây).
# Sau đó liệt kê lại MIG: VM mới xuất hiện trong lúc roll (autoscaler, autohealing) cũng được đưa về image đích,
# và mọi VM phải báo đúng image đích.
#
# Script slot gửi qua stdin, kèm checksum; VM chỉ ghi lại khi nội dung khác. (Trước 2026-10-13 script ~27 KB nằm
# trong tham số --command; mỗi VM chờ 240 s giữa lúc mở phiên SSH và lệnh đầu tiên, đo bằng journal của VM.)
#
# Biến môi trường (bắt buộc): BACKEND_REF, FRONTEND_REF (image@sha256:...), GCP_PROJECT_ID
# Tuỳ chọn: MIG_NAME (vota-ha-app), MIG_REGION (asia-southeast1), SLOT_SCRIPT, ROLL_LOG_DIR
set -euo pipefail

: "${BACKEND_REF:?BACKEND_REF là bắt buộc}"
: "${FRONTEND_REF:?FRONTEND_REF là bắt buộc}"
: "${GCP_PROJECT_ID:?GCP_PROJECT_ID là bắt buộc}"
MIG_NAME="${MIG_NAME:-vota-ha-app}"
MIG_REGION="${MIG_REGION:-asia-southeast1}"
SLOT_SCRIPT="${SLOT_SCRIPT:-$(dirname "$0")/../infra/terraform/environments/staging-ha/slot-deploy.sh}"

die() {
  printf 'roll-staging-ha-app-slots.sh: %s\n' "$*" >&2
  exit 1
}

[[ "$BACKEND_REF" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'BACKEND_REF phải là image@sha256:<64 hex>'
[[ "$FRONTEND_REF" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'FRONTEND_REF phải là image@sha256:<64 hex>'
[ -s "$SLOT_SCRIPT" ] || die "không có script slot: $SLOT_SCRIPT"
bash -n "$SLOT_SCRIPT" || die "script slot lỗi cú pháp"

script_sum="$(sha256sum "$SLOT_SCRIPT" | cut -c1-64)"
log_dir="${ROLL_LOG_DIR:-$(mktemp -d)}"
mkdir -p "$log_dir"
t0=$(date +%s)
stamp() { printf '[roll +%ss] %s\n' "$(( $(date +%s) - t0 ))" "$*"; }

list_vms() { # "tên zone" của VM RUNNING
  gcloud compute instance-groups managed list-instances "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" --format=json \
    | jq -r '.[] | select(.instanceStatus == "RUNNING") | "\(.instance | split("/") | last) \(.instance | split("/") | .[-3])"'
}

# Không ghim khoá host: VM bị MIG tạo lại sinh khoá SSH host mới (xem lịch sử 2026-10-12). Kênh vẫn qua IAP tới đúng instance.
ssh_vm() { # tên zone mode
  local name="$1" zone="$2" mode="$3" remote
  remote="set -e; echo \"REMOTE_START \$(date +%s)\"; f=/usr/local/sbin/vota-slot-deploy.sh; tmp=\$(mktemp); cat > \"\$tmp\"
[ \"\$(sha256sum \"\$tmp\" | cut -c1-64)\" = '$script_sum' ] || { echo 'script slot truyền thiếu' >&2; exit 1; }
if ! sudo -n cmp -s \"\$tmp\" \"\$f\"; then sudo -n install -m 0755 \"\$tmp\" \"\$f\"; echo SCRIPT_UPDATED; fi; rm -f \"\$tmp\"
sudo -n env BACKEND_IMAGE='$BACKEND_REF' FRONTEND_IMAGE='$FRONTEND_REF' \"\$f\" $mode"
  gcloud compute ssh "$name" --project "$GCP_PROJECT_ID" --zone "$zone" --tunnel-through-iap --quiet \
    --strict-host-key-checking=no --command "$remote" < "$SLOT_SCRIPT"
}

# Chạy một mode trên các VM song song; in log từng VM theo thứ tự; trả khác 0 nếu một VM lỗi.
run_phase() { # mode "tên zone"...
  local mode="$1" vm name rc=0 i
  shift
  local -a pids=() names=()
  for vm in "$@"; do
    name="${vm% *}"
    ssh_vm "$name" "${vm#* }" "$mode" > "$log_dir/$name.$mode.log" 2>&1 &
    pids+=("$!")
    names+=("$name")
  done
  for i in "${!pids[@]}"; do
    if ! wait "${pids[$i]}"; then
      rc=1
      echo "LỖI $mode ${names[$i]}" >> "$log_dir/failed"
    fi
    sed "s/^/[${names[$i]} $mode] /" "$log_dir/${names[$i]}.$mode.log"
  done
  return "$rc"
}

# Mọi VM đã switch phải báo đúng image đích (dòng SLOT_RESULT cuối cùng của log mode đó).
check_result() { # mode tên...
  local mode="$1" name line
  shift
  for name in "$@"; do
    line="$(grep -E '^SLOT_RESULT ' "$log_dir/$name.$mode.log" | tail -n 1 || true)"
    [ -n "$line" ] || die "$name không trả SLOT_RESULT ($mode)"
    [[ "$line" == *" backend=$BACKEND_REF "* && "$line" == *" frontend=$FRONTEND_REF" ]] || die "$name chạy image khác image đích: $line"
    echo "OK $name: $line"
  done
}

names_of() { local vm; for vm in "$@"; do printf '%s\n' "${vm% *}"; done; }

mapfile -t vms < <(list_vms)
[ "${#vms[@]}" -gt 0 ] || die "MIG $MIG_NAME không có VM RUNNING"
stamp "VM: $(names_of "${vms[@]}" | tr '\n' ' ')"

stamp "pha 1: prepare trên ${#vms[@]} VM (song song)"
if ! run_phase prepare "${vms[@]}"; then
  stamp "prepare lỗi: huỷ slot chờ trên mọi VM, giữ bản đang phục vụ"
  run_phase abort "${vms[@]}" || true
  die "prepare lỗi; mọi VM vẫn phục vụ bằng bản cũ"
fi
stamp "pha 1 xong"

canary="${vms[0]}"
rest=("${vms[@]:1}")
stamp "pha 2: switch canary ${canary% *}"
run_phase switch "$canary" || die "switch lỗi trên canary ${canary% *}; VM đó đã tự đổi lại slot cũ, các VM sau chưa đổi"
check_result switch "${canary% *}"
if [ "${#rest[@]}" -gt 0 ]; then
  stamp "pha 2: switch ${#rest[@]} VM còn lại (song song)"
  run_phase switch "${rest[@]}" || die "switch lỗi trên một VM (xem log); VM đó đã tự đổi lại slot cũ"
  mapfile -t rest_names < <(names_of "${rest[@]}")
  check_result switch "${rest_names[@]}"
fi
stamp "pha 2 xong"

# VM xuất hiện trong lúc roll khởi động theo image mong muốn (all-instances config) nhưng vẫn phải kiểm.
mapfile -t now < <(list_vms)
mapfile -t now_names < <(names_of "${now[@]}")
new_vms=()
for vm in "${now[@]}"; do
  printf '%s\n' "${vms[@]}" | grep -Fxq "$vm" || new_vms+=("$vm")
done
if [ "${#new_vms[@]}" -gt 0 ]; then
  stamp "VM mới trong lúc roll: $(names_of "${new_vms[@]}" | tr '\n' ' '); đưa về image đích"
  run_phase deploy "${new_vms[@]}" || die "deploy VM mới lỗi"
fi
stamp "kiểm image trên mọi VM"
run_phase report "${now[@]}" || die "không đọc được trạng thái một VM"
check_result report "${now_names[@]}"
stamp "xong: ${#now[@]} VM chạy image đích"
