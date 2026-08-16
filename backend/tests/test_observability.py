import pytest
import os
import json
import logging
import yaml
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.metrics import metrics_registry
from backend.logging_config import sanitize_data, JSONFormatter
from backend.telemetry import telemetry_manager, TraceSpanContext
from backend.sentry import sentry_manager

client = TestClient(app)

def test_prometheus_metrics_exposed():
    """Verify all requested Prometheus metrics are correctly exported."""
    metrics_registry.inc_request_count("GET", "/api/v1/websites", 200)
    metrics_registry.observe_request_duration(0.125)
    metrics_registry.set_active_users(5)
    metrics_registry.set_queue_length(3)
    metrics_registry.observe_crawl_duration(1.5)
    metrics_registry.observe_audit_duration(2.0)
    metrics_registry.observe_keyword_duration(0.8)
    metrics_registry.observe_rank_duration(0.5)
    metrics_registry.observe_ai_duration(1.2)
    metrics_registry.set_redis_latency(0.002)
    metrics_registry.set_database_latency(0.005)
    metrics_registry.inc_cache_hit()
    metrics_registry.inc_cache_miss()
    metrics_registry.inc_worker_jobs_completed()
    metrics_registry.inc_worker_jobs_failed()
    metrics_registry.inc_worker_restarts()
    metrics_registry.set_worker_memory_usage(128.5)
    metrics_registry.set_worker_cpu_usage(15.2)

    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text

    expected_metrics = [
        "seo_requests_total",
        "seo_request_duration_seconds",
        "active_users",
        "worker_queue_size",
        "queue_processing_time",
        "crawl_duration",
        "audit_duration",
        "keyword_duration",
        "rank_duration",
        "ai_duration",
        "redis_latency",
        "database_latency",
        "cache_hit_ratio",
        "cache_miss_ratio",
        "failed_jobs",
        "successful_jobs",
        "worker_restarts",
        "worker_memory_usage",
        "worker_cpu_usage"
    ]

    for metric in expected_metrics:
        assert metric in text, f"Metric '{metric}' missing from Prometheus output"

def test_health_and_readiness_endpoints():
    """Verify /health and /ready endpoints behave as expected."""
    # Test Liveness
    resp_liveness = client.get("/health")
    assert resp_liveness.status_code == 200
    assert resp_liveness.json()["status"] == "ok"

    # Test Readiness
    resp_ready = client.get("/ready")
    assert resp_ready.status_code in (200, 503)
    data = resp_ready.json()
    assert "status" in data
    assert "components" in data
    assert "database" in data["components"]

def test_telemetry_trace_generation():
    """Verify trace_id and span_id generation and context manager execution."""
    with TraceSpanContext("test_operation", attributes={"test.attr": "value"}) as span:
        assert span.trace_id is not None
        assert len(span.trace_id) > 0
        assert span.span_id is not None
        assert len(span.span_id) > 0

    # Test telemetry helper methods
    with telemetry_manager.trace_http_request("GET", "/test"):
        pass
    with telemetry_manager.trace_db_query("SELECT 1"):
        pass
    with telemetry_manager.trace_redis_op("GET", "key"):
        pass

def test_logging_sanitization_and_formatting():
    """Verify sensitive data is redacted and JSON logger includes tracing context."""
    raw_data = {
        "user_id": 1,
        "password": "MySecretPassword123!",
        "jwt_token": "Bearer eyJhbGciOiJIUzI1NiJ9...",
        "api_key": "secret_api_key_val",
        "nested": {
            "authorization": "Bearer secret_header"
        }
    }

    sanitized = sanitize_data(raw_data)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["nested"]["authorization"] == "[REDACTED]"
    assert sanitized["user_id"] == 1

    # Test JSON Formatter
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test log message",
        args=(),
        exc_info=None
    )
    record.trace_id = "test-trace-123"
    record.span_id = "test-span-456"
    record.user_id = 42

    formatted_str = formatter.format(record)
    log_json = json.loads(formatted_str)
    assert log_json["trace_id"] == "test-trace-123"
    assert log_json["span_id"] == "test-span-456"
    assert log_json["user_id"] == 42
    assert log_json["message"] == "Test log message"

def test_sentry_capture_methods():
    """Verify Sentry exception capture wrappers format context cleanly."""
    with patch("backend.sentry.logger.error") as mock_logger:
        sentry_manager.capture_exception(
            ValueError("Test exception"),
            user_id=10,
            job_id=99,
            correlation_id="corr-123",
            path="/api/v1/test"
        )
        assert mock_logger.called

    with patch.object(sentry_manager, "capture_exception") as mock_capture:
        sentry_manager.capture_worker_failure(
            job_id=5, job_type="audit", user_id=1, error_msg="Job crashed", stack_trace="Traceback..."
        )
        mock_capture.assert_called_once()

    with patch.object(sentry_manager, "capture_exception") as mock_capture:
        sentry_manager.capture_queue_failure("redis_queue", "Queue full")
        mock_capture.assert_called_once()

    with patch.object(sentry_manager, "capture_exception") as mock_capture:
        sentry_manager.capture_db_failure("SELECT", "DB connection reset")
        mock_capture.assert_called_once()

def test_prometheus_alert_rules_file():
    """Verify prometheus_alerts.yml is valid YAML and contains required alert rules."""
    alert_file_path = os.path.join(os.path.dirname(__file__), "../../docs/prometheus_alerts.yml")
    assert os.path.exists(alert_file_path), "prometheus_alerts.yml missing"

    with open(alert_file_path, "r") as f:
        content = yaml.safe_load(f)

    assert "groups" in content
    rules = content["groups"][0]["rules"]
    alert_names = [rule["alert"] for rule in rules]

    required_alerts = [
        "WorkerOffline",
        "RedisUnavailable",
        "DatabaseUnavailable",
        "QueueBacklog",
        "HighRequestLatency",
        "HighMemoryUsage",
        "HighCPUUsage",
        "HighAPIErrorRate",
        "TooManyJobRetries",
        "DeadLetterQueueGrowth"
    ]

    for alert in required_alerts:
        assert alert in alert_names, f"Alert rule '{alert}' missing from prometheus_alerts.yml"
