import logging
from typing import Dict, Any, Optional
from backend.config import settings
from backend.logging_config import sanitize_data

logger = logging.getLogger("seo_agent.sentry")

HAS_SENTRY = False
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False

class SentryManager:
    """Enterprise Sentry Error Monitoring integration with sensitive data scrubbing."""

    def __init__(self):
        self.dsn = settings.SENTRY_DSN
        self.environment = settings.ENVIRONMENT
        self.enabled = False
        self._init_sentry()

    def _before_send(self, event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Scrub sensitive information before sending events to Sentry."""
        try:
            # Sanitize request headers and body
            if "request" in event:
                req = event["request"]
                if "headers" in req:
                    req["headers"] = sanitize_data(req["headers"])
                if "data" in req:
                    req["data"] = sanitize_data(req["data"])
                if "query_string" in req:
                    req["query_string"] = sanitize_data(req["query_string"])

            # Sanitize extra and user data
            if "extra" in event:
                event["extra"] = sanitize_data(event["extra"])
            if "user" in event:
                event["user"] = sanitize_data(event["user"])

        except Exception as e:
            logger.warning(f"Error scrubbing Sentry event: {e}")

        return event

    def _init_sentry(self):
        if HAS_SENTRY and self.dsn:
            try:
                sentry_sdk.init(
                    dsn=self.dsn,
                    environment=self.environment,
                    traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
                    before_send=self._before_send,
                    integrations=[
                        FastApiIntegration(),
                        SqlalchemyIntegration(),
                    ],
                )
                self.enabled = True
                logger.info(f"Sentry error monitoring initialized for environment '{self.environment}'.")
            except Exception as e:
                logger.warning(f"Failed to initialize Sentry SDK: {e}")

    def capture_exception(
        self,
        exc: Exception,
        user_id: Optional[int] = None,
        job_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Capture an exception with context tags and extra metadata."""
        sanitized_context = sanitize_data(context or {})
        
        logger.error(
            f"Sentry capture: {type(exc).__name__}: {str(exc)}",
            exc_info=exc,
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "correlation_id": correlation_id,
                "path": path,
                "context": sanitized_context
            }
        )

        if self.enabled and HAS_SENTRY:
            try:
                with sentry_sdk.push_scope() as scope:
                    if user_id:
                        scope.set_user({"id": str(user_id)})
                    if job_id:
                        scope.set_tag("job_id", str(job_id))
                    if correlation_id:
                        scope.set_tag("correlation_id", correlation_id)
                    if path:
                        scope.set_tag("path", path)
                    scope.set_tag("environment", self.environment)
                    
                    for k, v in sanitized_context.items():
                        scope.set_extra(k, v)

                    sentry_sdk.capture_exception(exc)
            except Exception as e:
                logger.warning(f"Failed to transmit exception to Sentry: {e}")

    def capture_worker_failure(self, job_id: int, job_type: str, user_id: int, error_msg: str, stack_trace: str):
        self.capture_exception(
            RuntimeError(f"Worker failure in {job_type}: {error_msg}"),
            user_id=user_id,
            job_id=job_id,
            context={"job_type": job_type, "stack_trace": stack_trace}
        )

    def capture_queue_failure(self, queue_name: str, error_msg: str):
        self.capture_exception(
            RuntimeError(f"Queue failure in {queue_name}: {error_msg}"),
            context={"queue_name": queue_name}
        )

    def capture_db_failure(self, op: str, error_msg: str):
        self.capture_exception(
            RuntimeError(f"Database failure in {op}: {error_msg}"),
            context={"operation": op}
        )


# Global singleton instance
sentry_manager = SentryManager()
