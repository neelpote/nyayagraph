#!/bin/sh
set -eu

backup=${1:?Usage: CONFIRM_RESTORE=nyayagraph ./scripts/restore.sh /path/to/backup.dump}
[ "${CONFIRM_RESTORE:-}" = nyayagraph ] || {
  echo "Restore replaces current database objects. Set CONFIRM_RESTORE=nyayagraph to continue." >&2
  exit 2
}
[ -f "$backup" ] && [ ! -L "$backup" ] || { echo "Backup must be a regular, non-symlink file" >&2; exit 2; }

docker compose exec -T postgres pg_restore --list <"$backup" >/dev/null
docker compose exec -T postgres pg_restore \
  --username="${POSTGRES_USER:-nyayagraph}" \
  --dbname="${POSTGRES_DB:-nyayagraph}" \
  --clean --if-exists --no-owner --no-privileges --exit-on-error --single-transaction <"$backup"
