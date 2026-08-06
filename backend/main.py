from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException

from backend.config import settings
from backend.database.database import engine, Base
from backend.api.auth_routes import router as auth_router
from backend.api.org_routes import router as org_router
from backend.api.project_routes import router as project_router
from backend.api.website_routes import router as website_router
from backend.api.audit_routes import router as audit_router
from backend.api.routes import router as api_router
from backend.exceptions import SEOAgentException
from backend.logging_config import logger, RequestLoggingMiddleware
from backend.compression import setup_compression_middleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup phase: Validate configuration and ensure database schema readiness
    settings.validate_startup()
    Base.metadata.create_all(bind=engine)
    try:
        from backend.http_client import get_http_client, close_http_client
        get_http_client()  # Warm up reusable HTTP connection pool
    except Exception as http_err:
        logger.warning(f"Failed to initialize HTTP client pool: {http_err}")

    try:
        from backend.database.database import SessionLocal
        from backend.services.job_service import JobService
        from backend.worker import worker_instance
        db = SessionLocal()
        stale_count = JobService.cleanup_stale_jobs(db, max_age_seconds=300)
        if stale_count > 0:
            logger.info(f"Cleaned up {stale_count} stale jobs on application startup.")
        db.close()

        # Initialize worker background components and perform job recovery
        worker_instance.start(run_loop=False)
    except Exception as e:
        logger.warning(f"Failed to run startup stale job cleanup or worker startup: {e}")

    logger.info("Application startup complete: database schema verified.")
    yield
    # Shutdown phase
    try:
        from backend.http_client import close_http_client
        await close_http_client()
    except Exception as http_err:
        logger.warning(f"Error closing HTTP client pool: {http_err}")

    try:
        from backend.browser_pool import close_browser_pool
        await close_browser_pool()
    except Exception as browser_err:
        logger.warning(f"Error closing BrowserPool: {browser_err}")

    try:
        from backend.worker import worker_instance
        worker_instance.shutdown()
    except Exception as e:
        logger.warning(f"Error shutting down worker: {e}")
    logger.info("Application shutdown complete.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
setup_compression_middleware(app)


# Custom exception handlers for structured, consistent error responses
@app.exception_handler(SEOAgentException)
async def seo_agent_exception_handler(request: Request, exc: SEOAgentException):
    req_id = getattr(request.state, "request_id", None)
    user_id = getattr(request.state, "user_id", None)
    logger.warning(
        f"SEOAgentException: {exc.message}",
        extra={"request_id": req_id, "user_id": user_id, "status_code": exc.status_code}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "detail": exc.message,
            "status_code": exc.status_code,
            "details": exc.details
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", None)
    user_id = getattr(request.state, "user_id", None)
    detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    logger.warning(
        f"HTTPException: {detail_msg}",
        extra={"request_id": req_id, "user_id": user_id, "status_code": exc.status_code}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": detail_msg,
            "detail": detail_msg,
            "status_code": exc.status_code,
            "details": {}
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", None)
    user_id = getattr(request.state, "user_id", None)
    errors = exc.errors()
    cleaned_details = []
    for err in errors:
        cleaned_details.append({
            "loc": [str(item) for item in err.get("loc", [])],
            "msg": err.get("msg", ""),
            "type": err.get("type", "")
        })
    logger.warning(
        "Request validation failed",
        extra={"request_id": req_id, "user_id": user_id, "status_code": 422}
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Request validation failed",
            "detail": "Request validation failed",
            "status_code": 422,
            "details": {"errors": cleaned_details}
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", None)
    user_id = getattr(request.state, "user_id", None)
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={"request_id": req_id, "user_id": user_id, "status_code": 500}
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "An internal server error occurred",
            "detail": "An internal server error occurred",
            "status_code": 500,
            "details": {}
        }
    )

from datetime import datetime
import time
import shutil
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from backend.database.database import SessionLocal
from backend.cache import ttl_cache
from backend.metrics import metrics_registry

@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    """Kubernetes liveness probe endpoint."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/ready")
@app.get("/api/v1/ready")
async def readiness_check():
    """Kubernetes readiness probe checking database, redis, worker heartbeat, queue, disk space, memory, & configuration."""
    components = {}
    is_critical_down = False
    is_degraded = False

    # 1. Database (Async)
    try:
        start_db = time.time()
        from backend.database.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_duration = time.time() - start_db
        metrics_registry.set_database_latency(db_duration)
        components["database"] = {"status": "ok", "latency_ms": round(db_duration * 1000, 2)}
    except Exception as e:
        logger.error(f"Readiness check database error: {e}")
        components["database"] = {"status": "error", "message": str(e)}
        is_critical_down = True

    # 2. Redis
    try:
        if ttl_cache.is_redis_active() and ttl_cache.redis_client:
            start_redis = time.time()
            ttl_cache.redis_client.ping()
            redis_duration = time.time() - start_redis
            metrics_registry.set_redis_latency(redis_duration)
            components["redis"] = {"status": "ok", "latency_ms": round(redis_duration * 1000, 2)}
        else:
            components["redis"] = {"status": "fallback_in_memory", "message": "Using thread-safe TTL cache fallback"}
            is_degraded = True
    except Exception as e:
        components["redis"] = {"status": "error", "message": str(e)}
        is_degraded = True

    # 3. Worker Heartbeat
    try:
        from backend.worker_heartbeat import worker_heartbeat_manager
        active_workers = worker_heartbeat_manager.get_active_workers()
        if active_workers:
            components["worker_heartbeat"] = {"status": "ok", "active_count": len(active_workers)}
            metrics_registry.set_worker_active(1)
        else:
            components["worker_heartbeat"] = {"status": "no_active_workers", "active_count": 0}
            is_degraded = True
            metrics_registry.set_worker_active(0)
    except Exception as e:
        components["worker_heartbeat"] = {"status": "error", "message": str(e)}
        is_degraded = True

    # 4. Queue
    try:
        from backend.queue import background_job_queue
        q_len = background_job_queue.get_queue_length()
        metrics_registry.set_queue_length(q_len)
        components["queue"] = {"status": "ok", "pending_jobs": q_len}
    except Exception as e:
        components["queue"] = {"status": "error", "message": str(e)}
        is_degraded = True

    # 5. Disk Space
    try:
        total, used, free = shutil.disk_usage("/")
        free_gb = round(free / (1024**3), 2)
        used_percent = round((used / total) * 100, 1)
        components["disk_space"] = {"status": "ok", "free_gb": free_gb, "used_percent": used_percent}
        if used_percent > 90:
            components["disk_space"]["status"] = "warning"
            is_degraded = True
    except Exception as e:
        components["disk_space"] = {"status": "unknown", "message": str(e)}

    # 6. Memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        metrics_registry.set_worker_memory_usage(mem.used / (1024 * 1024))
        metrics_registry.set_worker_cpu_usage(psutil.cpu_percent(interval=None))
        components["memory"] = {"status": "ok", "used_percent": mem_percent}
        if mem_percent > 90:
            components["memory"]["status"] = "warning"
            is_degraded = True
    except ImportError:
        components["memory"] = {"status": "ok", "used_percent": "N/A (psutil module not loaded)"}
    except Exception as e:
        components["memory"] = {"status": "unknown", "message": str(e)}

    # 7. Configuration
    try:
        warnings = settings.validate_startup()
        components["configuration"] = {"status": "ok", "warnings": warnings}
    except Exception as e:
        components["configuration"] = {"status": "error", "message": str(e)}
        is_degraded = True

    if is_critical_down:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "components": components, "timestamp": datetime.utcnow().isoformat() + "Z"}
        )

    overall_status = "degraded" if is_degraded else "ready"
    return {
        "status": overall_status,
        "database": components.get("database", "connected"),
        "redis": components.get("redis", "connected"),
        "components": components,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/metrics")
@app.get("/api/v1/metrics")
def prometheus_metrics():
    """Prometheus exposition metrics endpoint for Cloud Monitoring."""
    return Response(content=metrics_registry.generate_prometheus_text(), media_type="text/plain; version=0.0.4")

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(org_router, prefix=settings.API_V1_STR)
app.include_router(project_router, prefix=settings.API_V1_STR)
app.include_router(website_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(api_router, prefix=settings.API_V1_STR)


