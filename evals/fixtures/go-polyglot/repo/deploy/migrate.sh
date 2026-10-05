#!/usr/bin/env bash
# Applies pending migrations in order. Never edits or re-runs an applied file (ADR 0001).
set -euo pipefail
. "$(dirname "$0")/lib.sh"
require_env DATABASE_URL

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"

for f in $(ls migrations/*.up.sql | sort); do
  v=$(basename "$f" .up.sql)
  sum=$(shasum -a 256 "$f" | cut -d' ' -f1)
  applied=$(psql "$DATABASE_URL" -tAc "SELECT sha256 FROM schema_migrations WHERE version = '$v'")
  if [ -n "$applied" ]; then
    [ "$applied" = "$sum" ] || die "migration $v was edited after being applied (sha mismatch)"
    continue
  fi
  log "applying $v"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
  psql "$DATABASE_URL" -c "INSERT INTO schema_migrations (version, sha256) VALUES ('$v', '$sum')"
done
