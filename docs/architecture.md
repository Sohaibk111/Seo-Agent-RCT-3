# Architecture

```
seo-agent-saas/
  Dockerfile.backend    Multi-stage Python 3.11 FastAPI image builder with healthchecks
  Dockerfile.frontend   Multi-stage Node 20 build serving production static bundle via Nginx
  docker-compose.yml    Local development orchestration stack
  docker-compose.prod.yml Production orchestration stack (PostgreSQL, Redis, Backend, Worker, Nginx)
  .github/workflows/ci.yml GitHub Actions CI/CD workflow pipeline
  nginx/
    nginx.conf          Nginx main configuration (gzip, security headers, logging)
    conf.d/default.conf Virtual server routing (/api/* proxying, static caching, WebSockets)
  redis/
    redis.conf          Redis AOF & snapshot persistence configuration
  scripts/
    backup_db.sh        PostgreSQL compressed backup script
    restore_db.sh       PostgreSQL disaster recovery restoration script
    cron_backup.example Crontab schedule configuration template
  docs/
    architecture.md     Architecture specification
    deployment.md       Production deployment guide
    disaster_recovery.md Disaster recovery and restoration guide
    production_checklist.md Production launch release checklist
    grafana_dashboard.json Grafana monitoring dashboard definition
    prometheus_alerts.yml Prometheus alerting rules configuration
    worker.md           Worker reliability specification

  backend/
    main.py             FastAPI entrypoint (lifespan startup, CORS, routes, /health, /ready, /metrics)
    config.py           Pydantic settings loaded from .env (DB pool size, max overflow, Redis & worker settings)
    telemetry.py        OpenTelemetry distributed tracing manager (`OpenTelemetryManager`, `trace_span`)
    sentry.py           Sentry error monitoring integration with automatic data redaction (`SentryManager`)
    cache.py            Production `UnifiedCache` (Redis with thread-safe `InMemoryTTLCache` fallback & metrics)
    queue.py            Production `RedisJobQueue` with thread fallback worker
    retry.py            Exponential Backoff `RetryEngine` & `@with_retry` decorator
    dead_letter_queue.py Redis-backed Dead Letter Queue (`DeadLetterQueue`)
    worker_heartbeat.py Periodic worker heartbeat manager (`WorkerHeartbeatManager`)
    worker.py           Enterprise `ReliableWorker` framework (concurrency, recovery, shutdown)
    worker_runner.py    Standalone background worker entry point
    rate_limiter.py     Thread-safe sliding window rate limiter (`rate_limit_guard`)
    metrics.py          Prometheus metrics registry (`MetricsRegistry`) with 20+ enterprise gauges & counters
    logging_config.py   JSON structured logging with trace ID, span ID, worker ID, retry number & duration

    database/
      database.py       SQLAlchemy engine with pool size, max overflow & `pool_pre_ping=True`
      models.py         ORM database models with explicit user ownership (`user_id` FK)
      schemas.py        Pydantic input/output validation models
      crud.py           Tenant-isolated database access methods

    auth/
      security.py       JWT token encoding/decoding
      dependencies.py   `get_current_user` auth dependency (401 Unauthorized)

    api/
      dependencies.py   Resource ownership validation helpers (`verify_website_ownership`, etc.)
      auth_routes.py    Authentication endpoints (`/api/v1/auth/*`)
      routes.py         Thin protected API endpoints (`/api/v1/*`) including `/jobs/{id}/cancel`, `/workers`, `/dlq`

    services/
      ai_service.py     Gemini AI recommendations (TTL cached with Redis/in-memory)
      export_service.py Streaming CSV, Google Sheets payload & PDF/HTML report exporter
      job_service.py    Background task runners, cancellation checking, metrics & stale job cleanup

    tests/              Pytest suite (100% offline, mocked network/browser)
      conftest.py        In-memory database test fixtures
      test_deployment.py Docker, PostgreSQL pool, Redis queue, metrics & logging tests
      test_worker_reliability.py Enterprise Worker Reliability test suite (32 unit & integration tests)
```

## Key Architectural Highlights

1. **Production Deployment Platform (Milestone 5.2)**:
   - **Docker Containerization**: Standardized multi-stage container builds (`Dockerfile.backend`, `Dockerfile.frontend`) and compose orchestrations (`docker-compose.yml`, `docker-compose.prod.yml`).
   - **PostgreSQL Database Support**: Production engine with connection pooling (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`), pre-ping automatic reconnection, and dynamic Alembic migrations.
   - **Nginx Reverse Proxy**: Single point of ingress providing Gzip compression, static asset caching headers (1 year), proxy buffering, request size caps (50M), security headers, and WebSocket upgrades.
   - **CI/CD Pipeline**: Automated GitHub Actions workflow (`.github/workflows/ci.yml`) performing linting, pytest testing, frontend build, Docker build validation, Alembic check, and dependency security audit.
   - **Disaster Recovery & Monitoring**: Automated daily database backups (`backup_db.sh`), Redis AOF persistence (`redis.conf`), Prometheus metrics extension, trace/span ID logging, and Grafana dashboard (`grafana_dashboard.json`).
   - **Redis Queue Manager (`RedisJobQueue`)**: Offloads background job tasks to Redis queue (`seo_agent:jobs`) when `REDIS_URL` and `USE_REDIS_QUEUE=true` are configured, with automatic threadpool worker fallback.
   - **Unified Redis & In-Memory Caching (`UnifiedCache`)**: Caches WHOIS lookups, sitemap parsing, robots.txt, domain metrics, keyword expansions, SERP ranks, and AI recommendations using configurable TTL values defined in `config.py`.
   - **Sliding-Window Rate Limiting (`RateLimiter`)**: Protects expensive endpoints against abuse with `429 Too Many Requests` responses and structured error messages.
   - **Structured JSON Logging & Correlation IDs**: Every request records `request_id`, `correlation_id` (propagated via `X-Correlation-ID`), `user_id`, `duration_ms`, `status_code`, `method`, `path`.
   - **Cloud Probes & Prometheus Metrics**: Exposes `/health`, `/ready` (checking DB & Redis connectivity), and `/metrics` (Prometheus exposition format for `request_count`, `request_duration_seconds`, `active_jobs`, `queue_length`, `crawl_duration_seconds`, `audit_duration_seconds`).

2. **Multi-Tenant Ownership Isolation**:
   All DB records (`Website`, `AuditResult`, `Lead`, `Report`, `Job`) carry an explicit `user_id` FK. CRUD operations filter by `user_id` and reusable ownership guard functions (`verify_website_ownership`, `verify_audit_ownership`, `verify_domain_ownership`) prevent cross-tenant data access (returning `403 Forbidden` or `404 Not Found`).

3. **Background Execution & Stale Cleanup**:
   Long-running tasks execute asynchronously in background tasks or Redis queues. Job state is tracked (`pending` -> `running` -> `completed` / `failed` / `cancelled`). Long loops periodically query `JobService.is_cancelled` to immediately halt work upon cancellation. Stale or orphaned jobs stuck in running/pending state are cleaned up automatically on server startup.
