#!/bin/sh
set -euC
umask 077

backup_dir=${BACKUP_DIR:?Set BACKUP_DIR to a protected directory outside the repository}
case "$backup_dir" in /|.) echo "Refusing unsafe BACKUP_DIR: $backup_dir" >&2; exit 2;; esac
mkdir -p "$backup_dir"
backup_dir=$(cd "$backup_dir" && pwd -P)
repo_dir=$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)
case "$backup_dir" in /|"$repo_dir"|"$repo_dir"/*) echo "BACKUP_DIR must be outside the repository" >&2; exit 2;; esac
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$backup_dir/nyayagraph-postgres-$timestamp.dump"
partial="$target.partial"
[ ! -e "$target" ] && [ ! -e "$partial" ] || { echo "Backup target already exists" >&2; exit 2; }
trap 'rm -f "$partial"' EXIT HUP INT TERM

docker compose exec -T postgres pg_dump \
  --username="${POSTGRES_USER:-nyayagraph}" \
  --dbname="${POSTGRES_DB:-nyayagraph}" \
  --format=custom --no-owner --no-privileges >"$partial"
test -s "$partial"
mv "$partial" "$target"
trap - EXIT HUP INT TERM
printf '%s\n' "$target"
