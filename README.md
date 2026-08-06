# SEO Agent

An AI-assisted SEO platform backend: site crawling, technical SEO audits,
free keyword research, domain metrics, and contact/lead extraction --
built on FastAPI, SQLAlchemy, Alembic, and Playwright.

## Status

Working today: Multi-tenant JWT-authenticated user accounts & strict tenant isolation, site crawling, full technical SEO audits (title/meta/h1/canonical/viewport/alt-text/structured-data/sitemap.xml/robots.txt/broken-link checking), free keyword research with search-intent classification and clustering, domain metrics, contact/lead/company extraction, rule-based & Gemini AI recommendations, free rank tracking, CSV/Excel/PDF report export, SMTP outreach email, Redis-backed distributed job queue with thread fallback, Redis & in-memory TTL caching, rate limiting, structured JSON logging with correlation IDs, Prometheus metrics, Kubernetes probes (`/health`, `/ready`, `/metrics`), and a full REST API.

## Enterprise Monitoring & Observability (Milestone 5.3 - Part 2)

- **OpenTelemetry Distributed Tracing**: Integrated `OpenTelemetryManager` (`backend/telemetry.py`) tracing HTTP requests, DB queries, Redis operations, background jobs, queue execution, Gemini AI calls, crawling, and technical audit execution with automatic `trace_id` and `span_id` context propagation.
- **Sentry Error Monitoring**: Production Sentry error capture (`backend/sentry.py`) handling API errors, worker crashes, queue failures, and database errors with tags for `user_id`, `job_id`, `correlation_id`, request path, and environment. Automatic recursive redaction guarantees JWT tokens, passwords, API keys, and secrets are never transmitted.
- **Prometheus Metrics Expansion**: Extended `MetricsRegistry` (`backend/metrics.py`) with 20+ enterprise metrics including `seo_requests_total`, `seo_request_duration_seconds`, `active_users`, `worker_queue_size`, `queue_processing_time`, `crawl_duration`, `audit_duration`, `keyword_duration`, `rank_duration`, `ai_duration`, `redis_latency`, `database_latency`, `cache_hit_ratio`, `cache_miss_ratio`, `failed_jobs`, `successful_jobs`, `worker_restarts`, `worker_memory_usage`, and `worker_cpu_usage`.
- **Grafana Production Dashboard**: Updated `docs/grafana_dashboard.json` with dedicated visual panels for API latency, error rates, 429 rate limiting, queue size, worker activity, database latency, Redis latency, cache hit ratios, CPU/memory usage, and task execution durations.
- **Enhanced Readiness Probe**: Upgraded `/ready` and `/api/v1/ready` endpoints in `backend/main.py` performing multi-component verification across Database, Redis, Worker Heartbeat, Queue, Disk Space, Memory, and Configuration, returning `degraded` state (HTTP 200) for non-critical warnings or HTTP 503 for critical failures.
- **Prometheus Alert Rules**: Provisioned `docs/prometheus_alerts.yml` covering Worker offline, Redis unavailable, Database unavailable, Queue backlog, High latency, Memory >90%, CPU >90%, High API error rate, Excessive job retries, and Dead Letter Queue growth.

## Enterprise Worker Reliability (Milestone 6)

- **Worker Heartbeat**: Workers periodically update heartbeats in Redis (`seo_agent:worker:{worker_id}`) with TTL, reporting `status` ("starting", "idle", "busy", "stopping", "stopped"), `running_jobs`, `cpu_usage`, and `memory_usage`. View active worker heartbeats via `GET /api/v1/workers`.
- **Exponential Backoff Retry Engine**: Decorators and `RetryEngine` with exponential backoff (`initial_delay * backoff_factor^attempt`), capped at `max_delay`, and random jitter. Bypasses retries for non-retryable validation/syntax errors.
- **Dead Letter Queue (DLQ)**: Redis-backed queue (`dead_letter_queue`) storing failed job details (`job_id`, `job_type`, `user_id`, `failure_reason`, `stack_trace`, `retry_count`, `timestamp`). Inspect via `GET /api/v1/dlq`.
- **Graceful Shutdown**: Intercepts `SIGTERM` and `SIGINT` signals, halting queue ingestion (`accepting_jobs = False`), waiting for active worker threads to finish, flushing logs, closing Redis and DB connection pools cleanly, and setting heartbeat status to "stopped".
- **Job Recovery**: On worker startup, scans for orphan jobs stuck in `running` or `pending` state from crashed workers and re-enqueues or moves them to DLQ to prevent dangling states.
- **Worker Concurrency & Safety**: Configurable concurrency via `WORKER_CONCURRENCY`, thread safety against race conditions, and utilization metrics (`worker_utilization_percent`).
- **Job Cancellation**: Endpoint `POST /api/v1/jobs/{id}/cancel` allows job owners to cancel queued or running jobs immediately.
- **Worker Metrics & Observability**: Extended Prometheus metrics including `worker_active`, `worker_jobs_running`, `worker_jobs_completed`, `worker_jobs_failed`, `worker_restarts`, `dead_letter_jobs`, `retry_attempts`, `retry_failures`, and `worker_uptime_seconds`. Structured JSON logs include `worker_id`, `job_id`, `trace_id`, `user_id`, `retry_number`, and `duration`.

## Production Deployment Platform (Milestone 5.2)

- **Docker Production Stack**: Multi-stage `Dockerfile.backend` and `Dockerfile.frontend` paired with `docker-compose.yml` (development) and `docker-compose.prod.yml` (production).
- **PostgreSQL Production Support**: PostgreSQL 15 integration with connection pooling (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`), pre-ping automatic reconnection, and dynamic Alembic migrations.
- **Nginx Reverse Proxy**: Custom Nginx reverse proxy configuration (`nginx/nginx.conf`, `nginx/conf.d/default.conf`) with SSL readiness, Gzip compression, static asset caching headers, proxy buffering, security headers, request size limits, and WebSocket upgrade support.
- **CI/CD Pipeline**: GitHub Actions workflow (`.github/workflows/ci.yml`) for automatic linting, pytest testing, frontend build validation, Docker container build check, Alembic migration validation, and security audit.
- **Backup & Recovery**: Automated database backup script (`scripts/backup_db.sh`), restore script (`scripts/restore_db.sh`), crontab schedules (`scripts/cron_backup.example`), and Redis AOF persistence (`redis/redis.conf`).
- **Monitoring & Grafana**: Prometheus metrics extension (cache hit ratio, DB query duration, worker utilization) and pre-configured Grafana dashboard (`docs/grafana_dashboard.json`).
- **Structured Logging Improvements**: Request logging with trace IDs, span IDs, exception fingerprinting, and daily rotation.

## Production Infrastructure (Milestone 5.1 & 5.2)

- **Redis-Backed Queue (`RedisJobQueue`)**: Offloads background job tasks (crawls, audits, keyword research, rank checks) to Redis queue (`seo_agent:jobs`) when `REDIS_URL` and `USE_REDIS_QUEUE=true` are configured, with automatic threadpool worker fallback when Redis is offline.
- **Unified Redis Caching (`UnifiedCache`)**: Caches WHOIS lookups (`CACHE_TTL_WHOIS`), sitemaps (`CACHE_TTL_SITEMAP`), robots.txt (`CACHE_TTL_ROBOTS`), domain metrics (`CACHE_TTL_METRICS`), keyword expansions (`CACHE_TTL_KEYWORDS`), SERP ranks (`CACHE_TTL_SERP`), and AI recommendations (`CACHE_TTL_AI`) with configurable TTL values in `config.py`.
- **Sliding-Window Rate Limiting (`RateLimiter`)**: Rate limits expensive endpoints (`/api/v1/audit`, `/api/v1/keywords`, `/api/v1/rank/check`, `/api/v1/ai/analyze/{id}`, `/api/v1/jobs/*`) returning `429 Too Many Requests`.
- **Structured JSON Logging & Correlation IDs**: Intercepts requests with `X-Request-ID` and `X-Correlation-ID` headers, logging request duration (`duration_ms`), user ID, method, path, and status code.
- **Cloud Infrastructure Endpoints**: Provides `/health` (liveness probe), `/ready` (readiness probe checking DB & Redis connectivity), and `/metrics` (Prometheus exposition format tracking request counts, request duration summary, active jobs, queue length, crawl duration, and audit duration).

## Multi-Tenant Authorization & Security Model

The platform enforces complete resource ownership and tenant isolation across all endpoints:

- **Authentication**: JWT / Bearer tokens passed via `Authorization: Bearer <token>` header.
- **Resource Ownership**: Every `Website`, `AuditResult`, `Lead`, `Report`, `RankCheck`, and `Job` belongs strictly to the authenticated `user_id`.
- **Authorization Guarding**:
  - `401 Unauthorized`: Returned when requests lack valid bearer authentication credentials.
  - `403 Forbidden`: Returned when an authenticated user attempts to view, modify, audit, export, analyze, or delete a resource owned by another user.
  - `404 Not Found`: Returned when a requested resource ID does not exist.
- **Reusable Verification Helpers**: All routes delegate ownership validation to reusable service checkers (`verify_website_ownership`, `verify_audit_ownership`, `verify_domain_ownership`, `verify_job_ownership`).

## Background Job Infrastructure

Async background operations (crawls, audits, keyword research, rank tracking) run via a tenant-isolated task runner:
- **Endpoints**: `POST /api/v1/jobs/crawl`, `POST /api/v1/jobs/audit`, `POST /api/v1/jobs/keywords`, `POST /api/v1/jobs/rank`, `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `DELETE /api/v1/jobs/{id}`.
- **Job States**: `pending` -> `running` -> `completed` / `failed` / `cancelled`.
- **Progress Tracking**: Real-time progress integer (0-100) and timestamps (`created_at`, `started_at`, `finished_at`, `updated_at`).
- **Isolation**: Users can only trigger, view, list, or delete jobs owned by their user account.

Interface-with-graceful-fallback (need your own credentials to go live):
Google Sheets export, Ahrefs/Moz/SEMrush metrics, OpenAI/Anthropic AI
analysis. Each raises a clear, typed error telling you which `.env`
variable to set rather than silently no-op'ing.

Not yet built: multi-tenant user roles/permissions beyond basic auth,
competitor-comparison UI, Celery/Redis-backed distributed job queue
(the current scheduler is in-process APScheduler, fine for a single
instance). `backend/parser/`, `backend/providers/`, `backend/gbob/`,
`backend/settings/` remain empty placeholder packages.

## Requirements

- Python 3.12
- Windows, macOS, or Linux

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install the Playwright browser binary (one-time)
python -m playwright install chromium

# 4. Configure environment
cp .env.example .env      # Windows: copy .env.example .env
# edit .env if you want to change the DB path, CORS origins, etc.

# 5. Apply database migrations
alembic upgrade head

# 6. Run the server
python -m uvicorn backend.main:app --reload
```

Windows users can instead run `scripts\run_backend.ps1`, which does all
of the above in one step.

Visit `http://127.0.0.1:8000/docs` for interactive API docs.

## Running tests

```bash
pytest
```

All 86 tests run offline (Playwright/HTTP calls are mocked), so they pass
in any environment with no live internet access, including CI.

## Configuration

All configuration lives in `.env` (see `.env.example` for every option),
loaded via `backend/config.py`. Nothing in the codebase reads
`os.environ` directly -- import `settings` from `backend.config` instead.

### Metrics providers: free today, paid later

`METRICS_PROVIDER` in `.env` controls which domain-metrics backend the
`/api/v1/metrics/domain` endpoint uses:

- `free` (default) -- WHOIS-based domain age/registrar lookup, no API key.
- `ahrefs` / `moz` / `semrush` -- paid providers. Stub classes already
  exist in `backend/metrics/` with the auth/config plumbing done; each
  raises a clear `NotImplementedError` at the one line where you need to
  add the actual API call once you have credentials. Add the relevant
  key(s) to `.env` and flip `METRICS_PROVIDER`, and nothing else in the
  app needs to change.

### Free-source keyword & search modules

`backend/keyword/keyword_expander.py` and `backend/scraper/google_search.py`
intentionally use free, unauthenticated sources (Google/DuckDuckGo
autocomplete, DuckDuckGo HTML search) instead of scraping Google's SERPs
directly, which violates Google's Terms of Service and gets IPs blocked.
When you're ready for real search-volume/SERP data, swap these for the
Google Custom Search JSON API, SerpApi, or similar -- see the docstring
in each file for the exact integration point.

## Project layout

See [`docs/architecture.md`](docs/architecture.md) for the full module
breakdown and design principles.

## API reference

See [`docs/api.md`](docs/api.md), or the live Swagger UI at `/docs`.

## Authentication & Security

All resource-intensive and data-modifying endpoints (clients, crawling, audits, keyword expansion, domain metrics, AI analysis, rank tracking, exports, outreach) require JWT bearer authentication.

- **JWT Secret Hardening**: When `APP_ENV=production`, the application refuses to start if `JWT_SECRET_KEY` is still set to the default development secret value.
- **SSRF Protection**: All crawl, Playwright, sitemap, broken-link check, and domain lookup requests are validated against SSRF attacks. Targets such as `localhost`, loopback, private IPv4/IPv6 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local addresses (`169.254.0.0/16`), cloud metadata IPs (`169.254.169.254`, `100.100.100.100`), and non-HTTP schemes (`file://`, `ftp://`) are strictly blocked with validation errors.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "a-strong-password"}'

curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -d "username=you@example.com&password=a-strong-password"
# -> {"access_token": "...", "token_type": "bearer"}

curl http://127.0.0.1:8000/api/v1/export/1/csv \
  -H "Authorization: Bearer <token>"
```

Set a real `JWT_SECRET_KEY` in `.env` before deploying -- the default in
`.env.example` is a placeholder.

## Background jobs

Set `SCHEDULER_ENABLED=true` in `.env` to run a daily in-process
re-audit of every tracked website (APScheduler, no external queue/broker
required). Off by default.

## Database migrations

Schema changes go through Alembic:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The initial schema migration lives in `migrations/versions/`.
