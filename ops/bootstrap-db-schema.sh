#!/usr/bin/env bash
set -Eeuo pipefail

SCHEMA_DIR=${SCHEMA_DIR:-/opt/vota/db-init}
PGHOST=${PGHOST:-vota-postgres}
PGPORT=${PGPORT:-5432}
PGUSER=${PGUSER:-postgres}
export PGHOST PGPORT PGUSER

if [[ -n "${PGPASSWORD_FILE:-}" ]]; then
  if [[ ! -r "$PGPASSWORD_FILE" ]]; then
    echo "password file is not readable: $PGPASSWORD_FILE" >&2
    exit 2
  fi
  export PGPASSWORD
  PGPASSWORD=$(cat "$PGPASSWORD_FILE")
fi

if [[ -z "${PGPASSWORD:-}" ]]; then
  echo 'set PGPASSWORD_FILE to a mounted secret file' >&2
  exit 2
fi

psql_cmd() {
  psql -X -v ON_ERROR_STOP=1 "$@"
}

wait_for_postgres() {
  local attempt
  for attempt in $(seq 1 "${PG_WAIT_ATTEMPTS:-60}"); do
    if pg_isready -q -h "$PGHOST" -p "$PGPORT" -U "$PGUSER"; then
      return 0
    fi
    sleep "${PG_WAIT_SECONDS:-2}"
  done
  echo "PostgreSQL did not become ready at ${PGHOST}:${PGPORT}" >&2
  exit 1
}

database_exists() {
  [[ "$(psql_cmd -d postgres -Atqc "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_database WHERE datname = '$1') THEN '1' ELSE '0' END")" == '1' ]]
}

vota_schema_ready() {
  [[ "$(psql_cmd -d vota -Atqc "SELECT CASE WHEN to_regclass('cdp.products') IS NOT NULL AND to_regclass('catalog.combo_items') IS NOT NULL AND to_regclass('app.users') IS NOT NULL THEN '1' ELSE '0' END")" == '1' ]]
}

insider_schema_ready() {
  [[ "$(psql_cmd -d insider -Atqc "SELECT CASE WHEN to_regclass('public.partners') IS NOT NULL AND to_regclass('public.insider_profiles') IS NOT NULL AND to_regclass('public.live_events') IS NOT NULL THEN '1' ELSE '0' END")" == '1' ]]
}

ensure_vota_roles() {
  # A pre-existing volume can have all tables but miss the NOLOGIN parent roles
  # (for example when it was initialized from an older image). Keep this
  # repair idempotent and apply it on every bootstrap run.
  psql_cmd -d vota <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cdp_reader') THEN
      CREATE ROLE cdp_reader NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cdp_writer') THEN
      CREATE ROLE cdp_writer NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vota_app') THEN
      CREATE ROLE vota_app NOLOGIN;
    END IF;
END $$;
GRANT cdp_reader TO cdp_writer;
GRANT USAGE ON SCHEMA cdp TO cdp_reader, vota_app;
GRANT SELECT ON ALL TABLES IN SCHEMA cdp TO cdp_reader;
GRANT INSERT, DELETE ON cdp.events TO cdp_writer;
GRANT INSERT, UPDATE ON cdp.profiles TO cdp_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA cdp TO cdp_writer;
GRANT SELECT ON cdp.products TO vota_app;
GRANT USAGE ON SCHEMA catalog, app TO vota_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA catalog, app TO vota_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO vota_app;
SQL
}

wait_for_postgres

if ! database_exists insider; then
  echo 'Creating database insider'
  psql_cmd -d postgres -f "$SCHEMA_DIR/00_create_insider.sql"
else
  echo 'Database insider already exists'
fi

if vota_schema_ready; then
  echo 'Schema vota already exists; leaving existing objects and data unchanged'
else
  echo 'Applying schema vota'
  psql_cmd -d vota -f "$SCHEMA_DIR/01_vota.sql"
fi

if insider_schema_ready; then
  echo 'Schema insider already exists; leaving existing objects and data unchanged'
else
  echo 'Applying schema insider'
  psql_cmd -d insider -f "$SCHEMA_DIR/02_insider.sql"
fi

echo 'Ensuring vota role hierarchy and grants'
ensure_vota_roles

echo 'Database schema bootstrap complete'
