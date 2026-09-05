#!/bin/sh
set -eu

backup_dir=${BACKUP_DIR:?Set BACKUP_DIR to the backup directory}
retention_days=${RETENTION_DAYS:-30}
case "$retention_days" in ''|*[!0-9]*) echo "RETENTION_DAYS must be a non-negative integer" >&2; exit 2;; esac
[ -d "$backup_dir" ] && [ ! -L "$backup_dir" ] || { echo "BACKUP_DIR must be a real directory" >&2; exit 2; }
backup_dir=$(cd "$backup_dir" && pwd -P)
[ "$backup_dir" != / ] || { echo "Refusing filesystem root" >&2; exit 2; }
repo_dir=$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)
case "$backup_dir" in "$repo_dir"|"$repo_dir"/*) echo "BACKUP_DIR must be outside the repository" >&2; exit 2;; esac

if [ "${CONFIRM_RETENTION:-}" = delete ]; then
  find "$backup_dir" -type f -name 'nyayagraph-postgres-*.dump' -mtime "+$retention_days" -delete
else
  echo "Dry run; set CONFIRM_RETENTION=delete to remove these files:" >&2
  find "$backup_dir" -type f -name 'nyayagraph-postgres-*.dump' -mtime "+$retention_days" -print
fi
