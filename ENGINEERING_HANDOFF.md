# Engineering Handoff: FastAPI Multi-Tenant Authorization, Redis Queue & Production Deployment Platform (Milestone 5.2)

## Overview
This document details the Python FastAPI backend (`backend/`) ownership authorization model, resource access control, Redis-backed background job queue, unified caching architecture, rate limiting, structured logging, monitoring metrics, Docker deployment stack, PostgreSQL connection pooling, Nginx proxy, and CI/CD automation.

## Enterprise Monitoring & Observability (Milestone 5.3 - Part 2)

1. **OpenTelemetry Integration (`backend/telemetry.py`)**:
   - `OpenTelemetryManager`: Unified manager for distributed tracing across HTTP requests, PostgreSQL queries, Redis commands, background jobs, Gemini AI calls, web crawling, and technical audit execution.
   - Trace Context: Automatically injects and propagates 128-bit `trace_id` and 64-bit `span_id` headers (`X-Trace-ID`, `X-Span-ID`).

2. **Sentry Error Monitoring (`backend/sentry.py`)**:
   - `SentryManager`: Captures exceptions, worker failures, queue processing failures, API 5xx errors, and DB connection failures.
   - Sensitive Data Protection: Automatic recursive sanitization strips JWT tokens, passwords, API keys, and authorization headers prior to egress.

3. **Prometheus Metrics Expansion (`backend/metrics.py`)**:
   - Exposed via `/metrics` and `/api/v1/metrics`.
   - Metrics include: `seo_requests_total`, `seo_request_duration_seconds`, `active_users`, `worker_queue_size`, `queue_processing_time`, `crawl_duration`, `audit_duration`, `keyword_duration`, `rank_duration`, `ai_duration`, `redis_latency`, `database_latency`, `cache_hit_ratio`, `cache_miss_ratio`, `failed_jobs`, `successful_jobs`, `worker_restarts`, `worker_memory_usage`, `worker_cpu_usage`.

4. **Grafana Dashboard & Prometheus Alerting (`docs/grafana_dashboard.json`, `docs/prometheus_alerts.yml`)**:
   - Grafana JSON featuring 12 customized panels covering key performance indicators.
   - Alerting rules defining thresholds for worker offline, Redis/DB degradation, queue backlog (>50 items), high latency (>2s), memory/CPU (>90%), error rate (>5%), retries (>5/min), and DLQ growth.

5. **Enhanced Readiness Probe (`backend/main.py`)**:
   - `/ready` and `/api/v1/ready` probes Database, Redis, Worker Heartbeat, Queue, Disk Space, Memory, and Configuration. Returns HTTP 200 with `"status": "degraded"` for non-critical warnings or HTTP 503 for critical outages.

6. **Test Suite (`backend/tests/test_observability.py`)**:
   - Comprehensive Pytest unit and integration test suite validating metrics exposition, readiness probes, tracing spans, log sanitization, Sentry captures, and Prometheus alert rules YAML.

## Enterprise Worker Reliability (Milestone 6)

1. **Worker Heartbeat & Registration (`backend/worker_heartbeat.py`)**:
   - `WorkerHeartbeatManager`: Periodically updates worker heartbeat in Redis under `seo_agent:worker:{worker_id}` with TTL (`WORKER_HEARTBEAT_INTERVAL * 3`).
   - Fields: `worker_id`, `hostname`, `pid`, `status` ("starting", "idle", "busy", "stopping", "stopped"), `last_seen`, `running_jobs`, `cpu_usage`, `memory_usage`.
   - Inspection Endpoint: `GET /api/v1/workers` lists all active worker heartbeats from Redis.

2. **Exponential Backoff Retry Engine (`backend/retry.py`)**:
   - `RetryEngine` & `@with_retry` decorator: Retries failed jobs with exponential backoff (`initial_delay * backoff_factor^attempt`), clamped at `max_delay`, plus random jitter.
   - Non-Retryable Exceptions: Bypasses retries for validation errors (`ValueError`, `ValidationErrorException`, `ValidationError`, `TypeError`, `KeyError`).
   - Prometheus Tracking: Increments `retry_attempts` and `retry_failures`.

3. **Dead Letter Queue (DLQ) (`backend/dead_letter_queue.py`)**:
   - `DeadLetterQueue`: Redis list (`dead_letter_queue`) storing failed job details after max retries or non-retryable exceptions.
   - Payload: `job_id`, `job_type`, `user_id`, `failure_reason`, `stack_trace`, `retry_count`, `timestamp`, `extra_data`.
   - Inspection & Management: `GET /api/v1/dlq` returns dead letter items and count. `clear_dlq()` clears DLQ.

4. **Graceful Shutdown & Signal Handling (`backend/worker.py`)**:
   - Intercepts `SIGTERM` and `SIGINT` signals.
   - Sequence: Halts queue ingestion (`accepting_jobs = False`), sets status="stopping", waits for running job threads in `ThreadPoolExecutor` to finish, flushes log handlers, closes Redis and DB connection pools cleanly, sets status="stopped", and exits.

5. **Job Recovery (`backend/worker.py`)**:
   - `recover_interrupted_jobs()`: On worker startup, scans database for jobs stuck in `running` or `pending` state from crashed worker instances.
   - Moves timed out/stuck jobs to DLQ and updates job status to "failed" with clear failure trace.

6. **Worker Concurrency & Race Condition Protection**:
   - Process concurrency bounded by `WORKER_CONCURRENCY` setting.
   - Atomic state transitions and thread lock protection (`_running_jobs_lock`) prevent race conditions.
   - Gauges: `worker_jobs_running` and `worker_utilization_percent`.

7. **Job Cancellation API**:
   - `POST /api/v1/jobs/{id}/cancel`: Ownership-protected cancellation endpoint.
   - Immediately cancels queued jobs and signals running jobs to stop.

8. **Observability & Testing**:
   - Extended Prometheus metrics (`worker_active`, `worker_jobs_running`, `worker_jobs_completed`, `worker_jobs_failed`, `worker_restarts`, `dead_letter_jobs`, `retry_attempts`, `retry_failures`, `worker_uptime_seconds`).
   - Structured JSON logs include `worker_id`, `job_id`, `trace_id`, `user_id`, `retry_number`, and `duration`.
   - Test Suite: `backend/tests/test_worker_reliability.py` with 32 unit and integration tests.

## Directory Layout & Boundaries

```
seo-agent-saas/
├── Dockerfile.backend       # Multi-stage Python FastAPI container builder
├── Dockerfile.frontend      # Multi-stage React/Nginx container builder
├── docker-compose.yml       # Development stack orchestration (FastAPI, React, Redis, PostgreSQL, Worker)
├── docker-compose.prod.yml  # Production stack orchestration with healthchecks & volumes
├── .github/workflows/ci.yml # GitHub Actions CI/CD pipeline (linting, tests, build checks)
├── nginx/
│   ├── nginx.conf           # Main Nginx proxy configuration (gzip, security headers)
│   └── conf.d/default.conf  # Virtual host routing (/api/* proxying, static caching, WebSockets)
├── redis/
│   └── redis.conf           # Redis AOF & snapshot persistence configuration
├── scripts/
│   ├── backup_db.sh         # Automated PostgreSQL backup script with compression & retention
│   ├── restore_db.sh        # Disaster recovery restoration script
│   └── cron_backup.example  # System crontab schedule template
├── docs/
│   ├── architecture.md      # Platform Architecture & Layout Reference
│   ├── deployment.md        # Step-by-Step Production Deployment Guide
│   ├── disaster_recovery.md # Disaster Recovery & Restoration Protocols
│   ├── production_checklist.md # Production Release Launch Checklist
│   └── grafana_dashboard.json  # Pre-built Grafana Monitoring Dashboard
├── backend/
│   ├── main.py              # FastAPI Entry Point (lifespan, /health, /ready, /metrics)
│   ├── config.py            # Settings & PostgreSQL Pool Config (DB_POOL_SIZE, DB_MAX_OVERFLOW)
│   ├── cache.py             # `UnifiedCache` (Redis with `InMemoryTTLCache` fallback & metrics)
│   ├── queue.py             # `RedisJobQueue` (Redis queue with thread fallback)
│   ├── rate_limiter.py      # Thread-safe sliding window `RateLimiter` (`rate_limit_guard`)
│   ├── metrics.py           # Prometheus `MetricsRegistry` (request counters, cache hit ratio, DB query duration)
│   ├── logging_config.py    # Structured JSON Logger with Trace ID & Span ID tracing
│   └── database/
│       ├── database.py      # Engine with connection pooling & `pool_pre_ping=True`
│       ├── models.py        # ORM Database Models with explicit ownership (`user_id` FK)
│       └── crud.py          # Tenant-Isolated DB Access Methods
```

## Production Deployment Platform (Milestone 5.2)

1. **Docker Production Stack**:
   - `Dockerfile.backend`: Multi-stage Python image with dependencies, Gunicorn/Uvicorn workers, health check.
   - `Dockerfile.frontend`: Multi-stage Node build serving compiled bundle via Nginx.
   - `docker-compose.prod.yml`: Orchestrates PostgreSQL 15, Redis 7, FastAPI, Nginx, and Worker container.

2. **PostgreSQL Production Integration**:
   - Connection Pooling: Configured via `DB_POOL_SIZE` (default 10-20), `DB_MAX_OVERFLOW` (default 20-40), `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`.
   - Automatic Reconnection: `pool_pre_ping=True` in `backend/database/database.py`.
   - Dynamic Alembic: `alembic/env.py` dynamically loads `settings.DATABASE_URL`.

3. **Nginx Reverse Proxy**:
   - Configured for Gzip compression, static asset 1-year cache headers, SSL readiness, security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy`), request limits (`50M`), and WebSocket upgrade headers.

4. **CI/CD Pipeline (`.github/workflows/ci.yml`)**:
   - Automated workflow executing backend pytest suite, frontend linter & build, Docker build check, Alembic migration dry-run, and security vulnerability audit.

5. **Monitoring & Logging**:
   - Extended Prometheus metrics (`/metrics`) tracking cache hit ratio (`cache_hits_total`), DB query duration (`db_query_duration_seconds`), worker utilization (`worker_utilization_percent`).
   - Grafana dashboard definition in `docs/grafana_dashboard.json`.
   - Structured JSON logging with `trace_id`, `span_id`, and exception grouping fingerprints.

## Production Infrastructure (Milestone 5.1)

1. **Distributed Job Queue (`backend/queue.py`)**:
   - `RedisJobQueue`: Pushes jobs to Redis list (`seo_agent:jobs`) when `REDIS_URL` is set and `USE_REDIS_QUEUE=true`.
   - Thread Fallback: If Redis is unconfigured or unreachable, transparently falls back to isolated `threading.Thread` workers.
   - `JobService` preserves full backward compatibility with FastAPI frontend while guaranteeing async processing.

2. **Unified Caching Layer (`backend/cache.py`)**:
   - `UnifiedCache`: Tries Redis `get`/`set`/`delete` operations first. Falls back to thread-safe `InMemoryTTLCache` if Redis is offline.
   - Granular TTL Configs in `config.py`:
     - `CACHE_TTL_DEFAULT`: 600s
     - `CACHE_TTL_METRICS`: 1800s
     - `CACHE_TTL_WHOIS`: 86400s
     - `CACHE_TTL_SITEMAP`: 3600s
     - `CACHE_TTL_ROBOTS`: 3600s
     - `CACHE_TTL_KEYWORDS`: 600s
     - `CACHE_TTL_SERP`: 600s
     - `CACHE_TTL_AI`: 1800s

3. **Rate Limiting (`backend/rate_limiter.py`)**:
   - `RateLimiter`: Thread-safe sliding window rate limiter.
   - Guarded Endpoints: `/api/v1/audit`, `/api/v1/keywords`, `/api/v1/rank/check`, `/api/v1/ai/analyze/{id}`, `/api/v1/jobs/*`.
   - Exceeding `RATE_LIMIT_PER_MINUTE` returns HTTP `429 Too Many Requests`.

4. **Structured JSON Logging & Correlation IDs (`backend/logging_config.py`)**:
   - Middleware automatically extracts or generates `X-Request-ID` and `X-Correlation-ID`.
   - Log records emitted as structured JSON containing timestamp, level, logger name, message, request ID, correlation ID, user ID, method, path, status code, and duration (ms).
   - Automatically redacts sensitive fields (`password`, `access_token`, `authorization`, `jwt_secret_key`).

5. **Cloud Probes & Prometheus Metrics (`backend/metrics.py`, `backend/main.py`)**:
   - `/health`: Liveness probe.
   - `/ready`: Readiness probe verifying DB execution (`SELECT 1`) and Redis connectivity.
   - `/metrics`: Prometheus text exposition format tracking:
     - `request_count_total{method, endpoint, status_code}`
     - `request_duration_seconds{method, endpoint}`
     - `active_jobs_count`
     - `queue_length_count`
     - `crawl_duration_seconds`
     - `audit_duration_seconds`

---

## Security & Authorization Principles

1. **Authentication Dependency**:
   - `get_current_user` extracts Bearer JWT tokens from the `Authorization` header.
   - Missing or invalid tokens immediately yield `401 Unauthorized`.

2. **Ownership Guarding Dependencies**:
   - `verify_website_ownership(website_id, user_id, db)`: Checks resource existence (`404`) and owner matching (`403`).
   - `verify_audit_ownership(audit_id, user_id, db)`: Validates that audit belongs to authenticated user.
   - `verify_domain_ownership(domain, user_id, db)`: Rejects access if domain is already registered to another user (`403`).

3. **CRUD Tenant Isolation**:
   - All CRUD queries in `backend/database/crud.py` filter by `user_id`. No cross-tenant data leaks are possible.
