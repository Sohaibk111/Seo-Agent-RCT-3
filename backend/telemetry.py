import os
import uuid
import time
import logging
import functools
from typing import Dict, Any, Optional, Callable
from backend.config import settings

logger = logging.getLogger("seo_agent.telemetry")

# Try importing opentelemetry modules if present
HAS_OTEL = False
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False

class TraceSpanContext:
    """Span context supporting both OpenTelemetry SDK and lightweight fallback tracing."""

    def __init__(self, span_name: str, attributes: Optional[Dict[str, Any]] = None):
        self.span_name = span_name
        self.attributes = attributes or {}
        self.trace_id = f"{uuid.uuid4().hex}"
        self.span_id = f"{uuid.uuid4().hex[:16]}"
        self.start_time = 0.0
        self.end_time = 0.0
        self._otel_span = None

    def __enter__(self):
        self.start_time = time.time()
        if HAS_OTEL and settings.OTEL_ENABLED:
            try:
                tracer = otel_trace.get_tracer(settings.OTEL_SERVICE_NAME)
                self._otel_span = tracer.start_span(self.span_name)
                for k, v in self.attributes.items():
                    if v is not None:
                        self._otel_span.set_attribute(k, str(v))
                ctx = self._otel_span.get_span_context()
                if ctx and ctx.trace_id:
                    self.trace_id = format(ctx.trace_id, "032x")
                    self.span_id = format(ctx.span_id, "016x")
            except Exception as e:
                logger.debug(f"OpenTelemetry span start warning: {e}")

        logger.debug(f"[Trace {self.trace_id[:8]}..] Started span: {self.span_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        
        if exc_type:
            self.attributes["error"] = True
            self.attributes["error.type"] = exc_type.__name__
            self.attributes["error.message"] = str(exc_val)
            if self._otel_span:
                try:
                    self._otel_span.record_exception(exc_val)
                    self._otel_span.set_status(otel_trace.Status(otel_trace.StatusCode.ERROR, str(exc_val)))
                except Exception:
                    pass

        if self._otel_span:
            try:
                self._otel_span.end()
            except Exception:
                pass

        logger.debug(
            f"[Trace {self.trace_id[:8]}..] Ended span: {self.span_name} in {duration_ms}ms"
        )
        return False

class OpenTelemetryManager:
    """Unified OpenTelemetry Distributed Tracing Manager."""

    def __init__(self):
        self.service_name = settings.OTEL_SERVICE_NAME
        self.enabled = settings.OTEL_ENABLED
        self._tracer = None
        self._init_otel()

    def _init_otel(self):
        if HAS_OTEL and self.enabled:
            try:
                provider = TracerProvider(resource=Resource.create({"service.name": self.service_name}))
                if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
                    try:
                        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
                        provider.add_span_processor(BatchSpanProcessor(exporter))
                    except Exception:
                        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
                else:
                    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

                otel_trace.set_tracer_provider(provider)
                self._tracer = otel_trace.get_tracer(self.service_name)
                logger.info(f"OpenTelemetry tracing initialized for service '{self.service_name}'.")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenTelemetry SDK: {e}. Falling back to lightweight tracing.")

    def trace_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for tracing arbitrary spans (HTTP, DB, Redis, Jobs, AI, Crawl, Audit)."""
        return TraceSpanContext(span_name=name, attributes=attributes)

    def trace_decorator(self, name: Optional[str] = None, attributes_extractor: Optional[Callable] = None):
        """Decorator to trace function executions."""
        def decorator(func: Callable):
            span_name = name or f"{func.__module__}.{func.__name__}"
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                attrs = {}
                if attributes_extractor:
                    try:
                        attrs = attributes_extractor(*args, **kwargs)
                    except Exception:
                        pass
                with self.trace_span(span_name, attributes=attrs):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    # Specific Tracing Helper Methods
    def trace_http_request(self, method: str, path: str, user_id: Optional[int] = None):
        return self.trace_span(f"HTTP {method} {path}", attributes={"http.method": method, "http.path": path, "user_id": user_id})

    def trace_db_query(self, query_name: str, table: Optional[str] = None):
        return self.trace_span(f"DB {query_name}", attributes={"db.system": "postgresql", "db.table": table})

    def trace_redis_op(self, command: str, key: Optional[str] = None):
        return self.trace_span(f"Redis {command}", attributes={"db.system": "redis", "redis.key": key})

    def trace_background_job(self, job_id: int, job_type: str, user_id: int):
        return self.trace_span(f"Job #{job_id} ({job_type})", attributes={"job.id": job_id, "job.type": job_type, "user_id": user_id})

    def trace_ai_request(self, model: str = "gemini-2.5-flash", action: str = "recommendation"):
        return self.trace_span(f"AI {action}", attributes={"ai.model": model, "ai.action": action})

    def trace_crawl_execution(self, url: str):
        return self.trace_span("Crawl Execution", attributes={"crawl.url": url})

    def trace_audit_execution(self, website_id: int):
        return self.trace_span("Audit Execution", attributes={"audit.website_id": website_id})


# Global singleton instance
telemetry_manager = OpenTelemetryManager()
trace_span = telemetry_manager.trace_span
