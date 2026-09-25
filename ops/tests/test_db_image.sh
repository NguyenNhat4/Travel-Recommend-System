#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
dockerfile="$repo_root/Dockerfile.db"
schema_script="$repo_root/ops/bootstrap-db-schema.sh"
vm_script="$repo_root/ops/bootstrap-db-vm.sh"

for file in "$dockerfile" "$schema_script" "$vm_script"; do
  test -f "$file" || { echo "missing required file: $file" >&2; exit 1; }
done

for schema_file in "$repo_root/db/init/01_vota.sql" "$repo_root/db/init/02_insider.sql"; do
  if grep -qi 'pgvector\|CREATE EXTENSION.*vector\|vector(768)\|product_vectors' "$schema_file"; then
    echo "schema must not require an in-PostgreSQL vector store: $schema_file" >&2
    exit 1
  fi
done

grep -q '^FROM postgres:16-bookworm$' "$dockerfile"
if grep -qi 'pgvector\|CREATE EXTENSION.*vector\|vector(768)' "$dockerfile"; then
  echo 'DB image must not depend on pgvector' >&2
  exit 1
fi
grep -q '00_create_insider.sql' "$dockerfile"
grep -q '01_vota.sql' "$dockerfile"
grep -q '02_insider.sql' "$dockerfile"
grep -q 'PGPASSWORD_FILE' "$schema_script"
grep -q 'to_regclass' "$schema_script"
grep -q 'ensure_vota_roles' "$schema_script"
grep -q 'CREATE ROLE cdp_reader' "$schema_script"
grep -q 'GRANT cdp_reader TO cdp_writer' "$schema_script"
grep -q -- '--publish=' "$vm_script"
grep -q '5432:5432' "$vm_script"
grep -q 'pg_isready -h 127.0.0.1' "$vm_script"
grep -q 'roles/artifactregistry.reader' "$vm_script"
if grep -Eq 'POSTGRES_PASSWORD=[A-Za-z0-9]|PGPASSWORD=[A-Za-z0-9]' "$dockerfile" "$schema_script" "$vm_script"; then
  echo 'database password must not be embedded in image/bootstrap scripts' >&2
  exit 1
fi

echo 'db image/bootstrap checks passed'
