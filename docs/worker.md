# Enterprise Worker Reliability Architecture (Milestone 6)

## 1. Executive Summary

Milestone 6 introduces Enterprise Worker Reliability to the SEO Agent SaaS platform. It upgrades background task processing with worker heartbeats, exponential backoff retries, dead-letter queues (DLQ), graceful signal handling, orphan job recovery, concurrency control, job cancellation, and extended Prometheus observability.

---

## 2. System Architecture & Component Interaction

```
[ FastAPI REST API / Job Producer ]
         │
         │ Enqueues job payload
         ▼
 ┌───────────────────────────────┐
 │   Redis Queue / Fallback      │ (seo_agent:jobs)
 └──────────────┬────────────────┘
                │
                │ Dequeues task payload
                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                    ReliableWorker Manager                    │
 │                                                             │
 │  ┌───────────────────────┐    ┌──────────────────────────┐  │
 │  │ WorkerHeartbeatManager│    │ ThreadPoolExecutor       │  │
 │  │ (seo_agent:worker:id) │    │ (WORKER_CONCURRENCY)     │  │
 │  └───────────────────────┘    └────────────┬─────────────┘  │
 └────────────────────────────────────────────┼────────────────┘
                                              │
                         ┌────────────────────┴────────────────────┐
                         │                                         │
                         ▼                                         ▼
            ┌──────────────────────────┐             ┌──────────────────────────┐
            │  Job Execution Thread 1  │             │  Job Execution Thread N  │
            └────────────┬─────────────┘             └────────────┬─────────────┘
                         │                                         │
                         │ Executes with                           │ Executes with
                         ▼                                         ▼
            ┌──────────────────────────┐             ┌──────────────────────────┐
            │       RetryEngine        │             │       RetryEngine        │
            │  (Exponential Backoff)   │             │  (Exponential Backoff)   │
            └────────────┬─────────────┘             └────────────┬─────────────┘
                         │                                         │
               ┌─────────┴─────────┐                     ┌─────────┴─────────┐
               │                   │                     │                   │
         [ Success ]          [ Max Retries         [ Success ]          [ Max Retries
               │               Exhausted ]               │               Exhausted ]
               ▼                   │                     ▼                   │
       (Mark Completed)            ▼             (Mark Completed)            ▼
                         ┌───────────────────┐                     ┌───────────────────┐
                         │ Dead Letter Queue │                     │ Dead Letter Queue │
                         │   (Redis DLQ)     │                     │   (Redis DLQ)     │
                         └───────────────────┘                     └───────────────────┘
```

---

## 3. Key Components & Implementation Details

### 3.1 Worker Heartbeat (`backend/worker_heartbeat.py`)
- **Persistence**: Saved in Redis under `seo_agent:worker:{worker_id}` with expiration TTL (`WORKER_HEARTBEAT_INTERVAL * 3`).
- **Telemetry Payload**:
  - `worker_id`: Unique identifier e.g. `worker-hostname-pid-uuid`.
  - `hostname` & `pid`: Host name and process ID.
  - `status`: Process state (`starting`, `idle`, `busy`, `stopping`, `stopped`).
  - `last_seen`: UTC ISO timestamp.
  - `running_jobs`: Active job count.
  - `cpu_usage` & `memory_usage`: Process CPU percentage and RSS memory (MB).
- **Inspection API**: `GET /api/v1/workers` lists all registered active worker heartbeats.

### 3.2 Exponential Backoff Retry Engine (`backend/retry.py`)
- **Decorator & Class**: `@with_retry(...)` and `RetryEngine`.
- **Delay Formula**:
  $$\text{Delay} = \min(\text{RETRY\_MAX\_DELAY}, \text{RETRY\_BASE\_DELAY} \times \text{backoff\_factor}^{\text{attempt}}) + \text{jitter}$$
- **Exception Filtering**:
  - **Retryable**: Network timeouts (`NetworkTimeoutError`, `RedisUnavailableError`, `GeminiTimeoutError`, `SERPTimeoutError`, `WHOISTimeoutError`, transient HTTP/DB connection errors).
  - **Non-Retryable**: Instantly bypasses retries for invalid user input and syntax/validation errors (`ValueError`, `ValidationErrorException`, `pydantic.ValidationError`, `TypeError`, `KeyError`).

### 3.3 Dead Letter Queue (DLQ) (`backend/dead_letter_queue.py`)
- **Storage**: Redis list `dead_letter_queue` with thread-safe in-memory fallback.
- **Payload Contents**:
  - `job_id`, `job_type`, `user_id`
  - `failure_reason`: Descriptive error message
  - `stack_trace`: Complete Python traceback
  - `retry_count`: Number of retries executed before DLQ push
  - `timestamp`: UTC timestamp
- **Inspection API**: `GET /api/v1/dlq` returns dead-lettered job records.

### 3.4 Graceful Shutdown & Signal Handling (`backend/worker.py`)
- **Signals**: Intercepts `SIGTERM` and `SIGINT`.
- **Sequence**:
  1. Sets `accepting_jobs = False` and status="stopping".
  2. Stops pulling new tasks from Redis queue.
  3. Waits for active threads in `ThreadPoolExecutor` to finish currently running jobs.
  4. Flushes all logger stream handlers.
  5. Gracefully closes Redis connection pool and SQLAlchemy database engine.
  6. Sets heartbeat status="stopped" and exits process cleanly with return code 0.

### 3.5 Job Recovery (`backend/worker.py`)
- **Startup Scanner**: `recover_interrupted_jobs()` runs during worker initialization.
- **Orphan Resolution**: Queries DB for jobs stuck in `running` or `pending` state exceeding `JOB_TIMEOUT_SECONDS` (300s). Pushes stack trace to DLQ and updates status to `failed`.

### 3.6 Job Cancellation Endpoint
- **API**: `POST /api/v1/jobs/{id}/cancel`
- **Security**: Enforces user ownership (`verify_job_ownership`).
- **Behavior**: Sets `status = "cancelled"`. Running workers poll `JobService.is_cancelled(db, job_id)` before execution and prior to retry loops, terminating cancelled tasks immediately.

---

## 4. Configuration Reference

Added environment variables in `backend/config.py`:

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `WORKER_CONCURRENCY` | `4` | Maximum parallel worker execution threads |
| `MAX_JOB_RETRIES` | `3` | Maximum retry attempts for failed jobs |
| `RETRY_BASE_DELAY` | `1.0` | Initial delay (seconds) for exponential backoff |
| `RETRY_MAX_DELAY` | `60.0` | Maximum cap (seconds) for backoff delay |
| `WORKER_HEARTBEAT_INTERVAL` | `10` | Frequency (seconds) for worker heartbeat updates |
| `JOB_RECOVERY_ENABLED` | `true` | Enables startup scan for orphan/interrupted jobs |
| `ENABLE_DEAD_LETTER_QUEUE` | `true` | Enables push to DLQ on permanent job failures |

---

## 5. Observability & Prometheus Metrics

Prometheus exposition endpoint `/api/v1/metrics` now includes:

```prometheus
# HELP worker_active Whether worker is currently active (1/0).
# TYPE worker_active gauge
worker_active 1

# HELP worker_jobs_running Number of worker jobs currently executing.
# TYPE worker_jobs_running gauge
worker_jobs_running 0

# HELP worker_jobs_completed Total background jobs completed.
# TYPE worker_jobs_completed counter
worker_jobs_completed 42

# HELP worker_jobs_failed Total background jobs failed permanently.
# TYPE worker_jobs_failed counter
worker_jobs_failed 1

# HELP worker_restarts Total worker process restarts.
# TYPE worker_restarts counter
worker_restarts 0

# HELP dead_letter_jobs Total dead letter queue jobs.
# TYPE dead_letter_jobs gauge
dead_letter_jobs 1

# HELP retry_attempts Total job execution retry attempts.
# TYPE retry_attempts counter
retry_attempts 3

# HELP retry_failures Total job execution failures after all retries.
# TYPE retry_failures counter
retry_failures 1

# HELP worker_uptime_seconds Worker uptime in seconds.
# TYPE worker_uptime_seconds gauge
worker_uptime_seconds 3600.50
```

---

## 6. Verification & Test Suite

The test suite in `backend/tests/test_worker_reliability.py` provides 32 comprehensive tests covering:
- Worker heartbeat payload, Redis TTL, and system metrics collection
- Retry engine backoff calculation, max retries, and skipping non-retryable exceptions
- DLQ push, list, clear, and payload structure
- Job cancellation authorization, state transition, and execution halting
- Job recovery for orphan running jobs
- Graceful shutdown signal interception
- Worker concurrency bounds
- Prometheus exposition format verification
