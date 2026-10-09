#!/bin/bash
# Sinh cấu hình pgbouncer cho một VM từ env của backend. Dùng:
#   pgbouncer-setup.sh <backend.env> <thư mục cấu hình> <pgbouncer.ini mẫu> [uid chủ sở hữu]
# Cần trong env: PGBOUNCER_UPSTREAM_HOST (db.vota.internal), DATABASE_URL và CDP_DATABASE_URL (trỏ 127.0.0.1:6432).
# Mật khẩu role phải là ký tự thường dùng trong URL, không có % @ : / ". Không in mật khẩu ra log.
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
  creds=${url#*://}; creds=${creds%%@*}; user=${creds%%:*}; pass=${creds#*:}
  [[ "$user" =~ ^[A-Za-z0-9_]+$ ]] || fail "$var: tên role không hợp lệ"
  [[ -n "$pass" && ! "$pass" =~ [%@:/\"\ ] ]] || fail "$var: mật khẩu rỗng hoặc chứa ký tự cần mã hoá URL"
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
