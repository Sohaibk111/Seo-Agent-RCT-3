# Production Deployment Guide (Milestone 5.2)

This guide walks through deploying the SEO Agent SaaS using Docker Compose, Nginx, PostgreSQL, Redis, and GitHub Actions CI/CD.

## Architecture Stack

- **Frontend**: React SPA served by Nginx (`Dockerfile.frontend`)
- **Backend API**: Python FastAPI with Gunicorn/Uvicorn (`Dockerfile.backend`)
- **Worker**: Asynchronous background queue worker (`seo_worker_prod`)
- **Database**: PostgreSQL 15 with connection pooling & pre-ping auto-reconnect
- **Cache & Queue**: Redis 7 with AOF persistence (`redis.conf`)
- **Reverse Proxy**: Nginx with SSL, Gzip, static asset caching & rate limiting

---

## 1. Quick Start with Docker Compose (Local Dev / Staging)

```bash
# Clone the repository
git clone https://github.com/your-org/seo-agent-saas.git
cd seo-agent-saas

# Copy environment template
cp .env.example .env

# Build and start all services (PostgreSQL, Redis, FastAPI, Worker, React/Nginx)
docker-compose up -d --build

# Verify running services
docker-compose ps
```

Visit `http://localhost:3000` for the frontend and `http://localhost:8000/docs` for the Swagger API reference.

---

## 2. Production Deployment Setup

### Step 1: Configure Environment Variables
Create a `production.env` file using `production.env.example` as a template:

```bash
cp production.env.example production.env
```

Ensure you set:
- `JWT_SECRET_KEY`: Minimum 32 random characters
- `POSTGRES_PASSWORD`: Strong password for PostgreSQL
- `GEMINI_API_KEY`: Valid Google Gemini API Key
- `CORS_ORIGINS`: Your actual domain origins (`https://yourdomain.com`)

### Step 2: Deploy Stack with Docker Compose Prod

```bash
# Deploy using the production stack file
docker-compose -f docker-compose.prod.yml --env-file production.env up -d --build

# Run database migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## 3. Enterprise Monitoring & Observability Setup (Milestone 5.3)

### OpenTelemetry Configuration
Configure OTLP trace export endpoint in `production.env`:
```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=seo-agent-service
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### Sentry Error Tracking Configuration
Configure Sentry DSN for exception capturing and performance sampling:
```env
SENTRY_DSN=https://your-key@sentry.io/your-project-id
SENTRY_TRACES_SAMPLE_RATE=1.0
```

### Prometheus & Grafana Configuration
1. **Scrape Config**: Point your Prometheus server scrape job to target `http://<backend_host>:8000/metrics` or `/api/v1/metrics`.
2. **Alert Rules**: Import `docs/prometheus_alerts.yml` into your Prometheus Alertmanager configuration directory.
3. **Grafana Dashboard**: Import `docs/grafana_dashboard.json` directly into Grafana UI (Dashboards -> Import).

---

## 4. Nginx Reverse Proxy & SSL Setup

Nginx is configured in `nginx/conf.d/default.conf` to serve static assets directly and proxy `/api/*` to FastAPI on port 8000.

For SSL/TLS setup (HTTPS):
1. Obtain an SSL certificate using Let's Encrypt / Certbot:
   ```bash
   certbot certonly --webroot -w /usr/share/nginx/html -d yourdomain.com
   ```
2. Mount your SSL certificates in `docker-compose.prod.yml` under Nginx volumes:
   ```yaml
   volumes:
     - /etc/letsencrypt:/etc/letsencrypt:ro
   ```
3. Enable `listen 443 ssl http2;` in `nginx/conf.d/default.conf`.

---

## 4. Monitoring & Probes

- **Liveness Probe**: `GET /health`
- **Readiness Probe**: `GET /ready` (verifies PostgreSQL DB query execution and Redis ping)
- **Prometheus Metrics**: `GET /metrics`

Import `docs/grafana_dashboard.json` into Grafana to monitor latencies, job durations, queue depth, cache hit ratios, and DB query performance.

---

## 5. Phase 3 Production Infrastructure Improvements

### Database Migration & Connection Validation
- **Alembic Automated Validator**: Migration linear history is validated via `scripts/validate_migrations.py`, enforcing a single migration head and valid revision sequence before deployments.
- **Connection Health Checks**: `check_db_connection()` utility in `backend.database.database` validates async engine connectivity and pool health during startup and container readiness checks.

### Real-Time SSE & Redis Pub/Sub Optimization
- **Event-Driven SSE Stream**: Job status updates (`/api/v1/jobs/{id}/stream`) utilize Redis Pub/Sub (`job:{id}:updates`) for zero-polling real-time updates with standard non-buffering headers (`X-Accel-Buffering: no`, `Cache-Control: no-cache`). Automatically falls back to efficient DB polling if Redis is inactive.
- **Custom JSON Cache Serializer**: `safe_json_dumps` handles `datetime`, `date`, `UUID`, `Decimal`, `set`, and Pydantic models for reliable Redis caching without serialization errors.

### Container Security & Worker Execution
- **Non-Root Container User**: Backend container runs under dedicated unprivileged `appuser` (UID 1000).
- **Production Queue Worker**: Background worker containers (`seo_worker` / `seo_worker_prod`) execute the full worker event loop via `python3 -m backend.worker`.

