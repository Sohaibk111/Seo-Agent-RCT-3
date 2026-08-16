#!/usr/bin/env bash
# PostgreSQL Database Restoration Script
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path_to_backup.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-seo_agent_prod}"
DB_USER="${POSTGRES_USER:-seo_prod_admin}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file '${BACKUP_FILE}' not found."
    exit 1
fi

echo "[$(date -Iseconds)] WARNING: Restoring database '${DB_NAME}' from '${BACKUP_FILE}'..."
echo "This operation will overwrite existing database contents."
read -p "Are you sure you want to proceed? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restoration cancelled."
    exit 0
fi

echo "[$(date -Iseconds)] Restoring database schema and records..."
gunzip -c "${BACKUP_FILE}" | PGPASSWORD="${POSTGRES_PASSWORD:-}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}"

echo "[$(date -Iseconds)] Database restoration completed successfully."
