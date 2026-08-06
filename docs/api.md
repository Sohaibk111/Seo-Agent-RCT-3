# API Reference

Base URL: `http://127.0.0.1:8000`
All protected endpoints below are mounted under `/api/v1` (configurable via `API_PREFIX` in `.env`).
Interactive docs: `GET /docs` (Swagger UI) and `GET /redoc`.

| Method | Path                     | Description                                              |
|--------|--------------------------|------------------------------------------------------------|
| GET    | `/health`, `/api/v1/health` | Kubernetes liveness probe check                       |
| GET    | `/ready`, `/api/v1/ready`  | Kubernetes readiness probe (checks DB & Redis status)  |
| GET    | `/metrics`, `/api/v1/metrics` | Prometheus metrics exposition format                  |
| GET    | `/api/v1/websites`       | List tracked user websites                                 |
| POST   | `/api/v1/audit`          | Run technical SEO audit on a URL (Rate Limited)            |
| GET    | `/api/v1/audit/{id}`     | List saved audit results for a website                     |
| GET    | `/api/v1/scraper/robots` | Fetch and parse robots.txt (Redis/TTL Cached)              |
| GET    | `/api/v1/scraper/sitemap`| Fetch and parse sitemap.xml (Redis/TTL Cached)             |
| GET    | `/api/v1/metrics/whois`  | Lookup domain WHOIS registration (Redis/TTL Cached)       |
| POST   | `/api/v1/keywords`       | Expand seed keyword into ideas (Rate Limited, Redis Cached)|
| POST   | `/api/v1/metrics/domain` | Domain metrics (Rate Limited, Redis Cached)                |
| POST   | `/api/v1/jobs/crawl`     | Enqueue async background site crawl job (Redis Queue)      |
| POST   | `/api/v1/jobs/audit`     | Enqueue async background technical audit job (Redis Queue) |
| POST   | `/api/v1/jobs/keywords`  | Enqueue async background keyword research job (Redis Queue)|
| POST   | `/api/v1/jobs/rank`      | Enqueue async background SERP rank check job (Redis Queue) |
| GET    | `/api/v1/jobs`           | List user's background jobs with filtering & pagination    |
| GET    | `/api/v1/jobs/{id}`      | Get background job execution status & result               |
| DELETE | `/api/v1/jobs/{id}`      | Delete background job                                      |

See `/docs` for full request/response schemas (generated from the Pydantic
models in `backend/database/schemas.py`).
