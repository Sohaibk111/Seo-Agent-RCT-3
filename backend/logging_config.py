import logging
import json
import time
import uuid
import re
from typing import Any, Dict, Optional
from fastapi import Request, Response
from starlette.datastructures import MutableHeaders

SENSITIVE_KEYS = {"password", "token", "authorization", "secret", "jwt", "access_token", "refresh_token", "api_key", "secret_key"}

def sanitize_data(data: Any) -> Any:
    """Recursively scrub sensitive fields from dict, list, or string values."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_str = str(k).lower()
            if any(s in k_str for s in ["password", "token", "auth", "secret", "jwt", "api_key", "key"]):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str):
        if any(s in data.lower() for s in ["bearer ", "jwt ", "eyj"]):
            return "[REDACTED TOKEN]"
    return data

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter including tracing, worker, and job context."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Context fields mandated for enterprise observability
        for field in [
            "trace_id", "span_id", "request_id", "correlation_id",
            "worker_id", "job_id", "user_id", "duration", "duration_ms",
            "method", "path", "status_code", "exception_group"
        ]:
            val = getattr(record, field, None)
            if val is not None:
                log_obj[field] = val

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            log_obj["exception_group"] = f"{exc_type}:{record.module}:{record.lineno}"

        # Sanitize sensitive fields in log output
        log_obj = sanitize_data(log_obj)

        return json.dumps(log_obj)

def setup_logger(name: str = "seo_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    return logger

logger = setup_logger()

class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_raw = dict(scope.get("headers", []))
        req_id_header = headers_raw.get(b"x-request-id", b"").decode("utf-8")
        corr_id_header = headers_raw.get(b"x-correlation-id", b"").decode("utf-8")
        trace_id_header = headers_raw.get(b"x-trace-id", b"").decode("utf-8")
        span_id_header = headers_raw.get(b"x-span-id", b"").decode("utf-8")

        request_id = req_id_header if req_id_header else str(uuid.uuid4())
        correlation_id = corr_id_header if corr_id_header else request_id
        trace_id = trace_id_header if trace_id_header else f"{uuid.uuid4().hex}"
        span_id = span_id_header if span_id_header else f"{uuid.uuid4().hex[:16]}"

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id
        scope["state"]["correlation_id"] = correlation_id
        scope["state"]["trace_id"] = trace_id
        scope["state"]["span_id"] = span_id

        start_time = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Correlation-ID"] = correlation_id
                headers["X-Trace-ID"] = trace_id
                headers["X-Span-ID"] = span_id
            await send(message)

        method = scope.get("method", "")
        path = scope.get("path", "")

        try:
            await self.app(scope, receive, send_wrapper)
            duration_sec = time.time() - start_time
            duration_ms = round(duration_sec * 1000, 2)
            user_id = scope.get("state", {}).get("user_id", None)

            from backend.metrics import metrics_registry
            metrics_registry.inc_request_count(method=method, endpoint=path, status_code=status_code)
            metrics_registry.observe_request_duration(duration_sec)

            logger.info(
                f"{method} {path} finished with status {status_code}",
                extra={
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "user_id": user_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration": round(duration_sec, 4),
                    "duration_ms": duration_ms
                }
            )
        except Exception as exc:
            duration_sec = time.time() - start_time
            duration_ms = round(duration_sec * 1000, 2)
            user_id = scope.get("state", {}).get("user_id", None)

            from backend.sentry import sentry_manager
            sentry_manager.capture_exception(
                exc,
                user_id=user_id,
                correlation_id=correlation_id,
                path=path,
                context={"trace_id": trace_id, "span_id": span_id}
            )

            logger.error(
                f"{method} {path} failed with exception: {str(exc)}",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "user_id": user_id,
                    "method": method,
                    "path": path,
                    "status_code": 500,
                    "duration": round(duration_sec, 4),
                    "duration_ms": duration_ms
                }
            )
            raise exc
