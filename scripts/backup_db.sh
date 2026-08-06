#!/usr/bin/env bash
# PostgreSQL Automated Database Backup Script
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/seo_agent}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-seo_agent_prod}"
DB_USER="${POSTGRES_USER:-seo_prod_admin}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] Starting PostgreSQL database backup for ${DB_NAME}..."

PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-acl \
    | gzip -9 > "${BACKUP_FILE}"

echo "[$(date -Iseconds)] Backup created successfully at ${BACKUP_FILE} ($(du -sh "${BACKUP_FILE}" | cut -f1))"

# Prune backups older than RETENTION_DAYS
echo "[$(date -Iseconds)] Pruning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete
echo "[$(date -Iseconds)] Backup process complete."
