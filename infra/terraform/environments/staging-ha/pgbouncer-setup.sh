#!/bin/bash
# Sinh cấu hình pgbouncer cho một VM từ env của backend. Dùng:
#   pgbouncer-setup.sh <backend.env> <thư mục cấu hình> <pgbouncer.ini mẫu> [uid chủ sở hữu]
# Cần trong env: PGBOUNCER_UPSTREAM_HOST (db.vota.internal), DATABASE_URL và CDP_DATABASE_URL (trỏ 127.0.0.1:6432).
# Mật khẩu trong URL có thể mã hoá phần trăm (%40 cho @, %2F cho /...): script giải mã trước khi ghi userlist.txt của pgbouncer
# (userlist cần mật khẩu thô). Ký tự thô @ : / " \ hoặc dấu cách phải mã hoá. Không in mật khẩu ra log.
set -euo pipefail
ENV_FILE=${1:?backend.env}; OUT_DIR=${2:?thư mục cấu hình}; TEMPLATE=${3:?pgbouncer.ini mẫu}; OWNER=${4:-70}

fail() { echo "pgbouncer-setup: $*" >&2; exit 1; }
get() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -1 | sed -e 's/^"//' -e 's/"$//'; }

upstream=$(get PGBOUNCER_UPSTREAM_HOST)
[[ "$upstream" =~ ^[A-Za-z0-9.-]+$ ]] || fail 'PGBOUNCER_UPSTREAM_HOST thiếu hoặc không hợp lệ (ví dụ db.vota.internal)'
[[ "$upstream" != "127.0.0.1" && "$upstream" != "localhost" ]] || fail 'PGBOUNCER_UPSTREAM_HOST không được là loopback'

umask 077
install -d -m 755 "$OUT_DIR"
tmp_users=$(mktemp)
seen=""; count=0
for var in DATABASE_URL CDP_DATABASE_URL; do
  url=$(get "$var")
  [[ "$url" == postgres*://*:*@* ]] || fail "$var thiếu hoặc không có dạng postgresql://user:mật-khẩu@host/db"
  creds=${url#*://}; creds=${creds%%@*}; user=${creds%%:*}; pass_raw=${creds#*:}
  [[ "$user" =~ ^[A-Za-z0-9_]+$ ]] || fail "$var: tên role không hợp lệ"
  [[ "$pass_raw" =~ ^([^%@:/\"\\\ ]|%[0-9A-Fa-f]{2})+$ ]] || fail "$var: mật khẩu rỗng hoặc chứa ký tự thô cần mã hoá URL (@ : / \" \\ dấu cách) hoặc % không theo sau bởi 2 chữ số hex"
  pass=$(printf '%b' "${pass_raw//%/\\x}")
  pass=${pass//\"/\"\"}   # userlist.txt: dấu " trong mật khẩu viết thành ""
  case " $seen " in
    *" $user "*) ;;   # role đã có (vd. hai URL dùng chung role)
    *) printf '"%s" "%s"\n' "$user" "$pass" >> "$tmp_users"; seen="$seen $user"; count=$((count + 1)) ;;
  esac
done

sed "s/__UPSTREAM_HOST__/$upstream/" "$TEMPLATE" > "$OUT_DIR/pgbouncer.ini"
install -m 600 "$tmp_users" "$OUT_DIR/userlist.txt"
rm -f "$tmp_users"
chown "$OWNER:$OWNER" "$OUT_DIR/userlist.txt" "$OUT_DIR/pgbouncer.ini" 2>/dev/null || true
echo "pgbouncer-setup: $count role, upstream $upstream"
