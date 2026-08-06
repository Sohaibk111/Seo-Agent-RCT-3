# Disaster Recovery & Backup Guide

This document outlines procedure protocols for backing up, restoring, and recovering the SEO Agent SaaS infrastructure.

## 1. Automated Database Backups

Database backups are handled via `scripts/backup_db.sh`. It produces gzipped SQL dumps (`pg_dump`) with timestamps and prunes backups older than the configured retention period (`RETENTION_DAYS=7`).

### Running a Manual Backup:
```bash
./scripts/backup_db.sh
```

### Setting up Daily Backup Cron Job:
Copy `scripts/cron_backup.example` to system crontab:
```bash
crontab -e
# Add line:
0 2 * * * /bin/bash /path/to/app/scripts/backup_db.sh >> /var/log/seo_agent_backup.log 2>&1
```

---

## 2. Database Restoration & Recovery

If a database failure, data corruption, or disaster occurs, follow these recovery steps:

1. **Locate the target backup file**:
   ```bash
   ls -la /var/backups/seo_agent/
   ```

2. **Execute restoration script**:
   ```bash
   ./scripts/restore_db.sh /var/backups/seo_agent/seo_agent_prod_20260804_020000.sql.gz
   ```

3. **Verify DB Connectivity & Health**:
   ```bash
   curl -f http://localhost:8000/ready
   ```

---

## 3. Redis Queue & Cache Persistence Recovery

Redis state is persisted to disk using **Append-Only File (AOF)** and RDB snapshots as configured in `redis/redis.conf`:
- AOF file: `/data/appendonly.aof`
- Snapshots: `/data/dump.rdb`

If Redis crashes or restarts, it automatically reloads state from the persistent volume (`redis_prod_data`).

If Redis state is lost:
- Background jobs in PostgreSQL (`jobs` table) retain state (`pending`, `running`).
- The worker will automatically recover jobs or recreate them.
- Caching will seamlessly fallback to in-memory TTL caching.
