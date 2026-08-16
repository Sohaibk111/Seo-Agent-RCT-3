# Production Launch Checklist (Milestone 5.2)

Use this operational checklist before releasing the SEO Agent SaaS platform to production.

## 1. Security & Secrets Management
- [ ] `JWT_SECRET_KEY` is set to a cryptographically secure string of at least 32 characters.
- [ ] `POSTGRES_PASSWORD` is updated from default placeholders.
- [ ] `GEMINI_API_KEY` is configured and validated.
- [ ] `CORS_ORIGINS` is restricted to legitimate frontend production domain origins.
- [ ] Debug mode is disabled (`ENVIRONMENT=production`).
- [ ] Sensitive headers and tokens are redacted in structured JSON logs.

## 2. Infrastructure & Container Health
- [ ] `docker-compose.prod.yml` starts cleanly with zero exit code errors.
- [ ] Nginx reverse proxy serves static assets with long-term cache headers.
- [ ] Nginx security headers (`X-Frame-Options`, `Content-Security-Policy`, `X-Content-Type-Options`) are verified via `curl -I`.
- [ ] `/health` returns `200 OK`.
- [ ] `/ready` returns `200 OK` with `"database": "connected"` and `"redis": "connected"`.

## 3. Database & Persistence
- [ ] PostgreSQL connection pool size (`DB_POOL_SIZE=20`) and `pool_pre_ping=True` are configured.
- [ ] Alembic migrations run cleanly (`alembic upgrade head`).
- [ ] Automated daily database backup cron job (`scripts/backup_db.sh`) is scheduled and tested.
- [ ] Redis AOF persistence (`appendonly yes`) is enabled in `redis/redis.conf`.

## 4. Monitoring & Telemetry
- [ ] Prometheus metrics endpoint (`/metrics`) is exposed and operational.
- [ ] Grafana dashboard (`docs/grafana_dashboard.json`) is imported and rendering metrics.
- [ ] Queue depth, latency, worker utilization, and cache hit ratio alerts are active.

## 5. CI/CD & Testing
- [ ] GitHub Actions workflow (`.github/workflows/ci.yml`) passes all unit and integration tests.
- [ ] Docker image build check passes for backend and frontend.
