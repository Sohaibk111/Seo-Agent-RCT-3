import time
import random
import logging
from functools import wraps
from typing import Callable, Any, Tuple, Type, Optional
from pydantic import ValidationError

from backend.config import settings
from backend.exceptions import ValidationErrorException
from backend.metrics import metrics_registry

logger = logging.getLogger("seo_agent.retry")

# Custom retryable exception types for granular error handling
class NetworkTimeoutError(Exception):
    pass

class RedisUnavailableError(Exception):
    pass

class GeminiTimeoutError(Exception):
    pass

class SERPTimeoutError(Exception):
    pass

class WHOISTimeoutError(Exception):
    pass

# Exceptions that should NEVER be retried
DEFAULT_NON_RETRYABLE: Tuple[Type[BaseException], ...] = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    ValidationError,
    ValidationErrorException,
)

class RetryEngine:
    """Configurable exponential backoff retry engine with jitter."""

    def __init__(
        self,
        max_retries: Optional[int] = None,
        initial_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
        non_retryable_exceptions: Tuple[Type[BaseException], ...] = DEFAULT_NON_RETRYABLE,
    ):
        self.max_retries = max_retries if max_retries is not None else settings.MAX_JOB_RETRIES
        self.initial_delay = initial_delay if initial_delay is not None else settings.RETRY_BASE_DELAY
        self.max_delay = max_delay if max_delay is not None else settings.RETRY_MAX_DELAY
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self.non_retryable_exceptions = non_retryable_exceptions

    def compute_delay(self, attempt: int) -> float:
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay += random.uniform(0.0, 0.1 * delay)
        return delay

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except BaseException as e:
                last_exception = e
                # Check non-retryable exceptions first
                if isinstance(e, self.non_retryable_exceptions):
                    logger.warning(
                        f"Non-retryable exception encountered: {type(e).__name__}: {e}. Skipping retries."
                    )
                    raise e

                # Check if exception is retryable
                if not isinstance(e, self.retryable_exceptions):
                    raise e

                func_name = getattr(func, "__name__", str(func))
                if attempt < self.max_retries:
                    metrics_registry.inc_retry_attempts()
                    delay = self.compute_delay(attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} for {func_name} after {delay:.2f}s delay. "
                        f"Cause: {type(e).__name__}: {e}"
                    )
                    time.sleep(delay)
                else:
                    metrics_registry.inc_retry_failures()
                    logger.error(
                        f"All {self.max_retries} retries failed for {func_name}. Last exception: {type(e).__name__}: {e}"
                    )
                    raise e
        if last_exception:
            raise last_exception

def with_retry(
    max_retries: Optional[int] = None,
    initial_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[BaseException], ...] = DEFAULT_NON_RETRYABLE,
):
    """Decorator version of RetryEngine."""
    engine = RetryEngine(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
        non_retryable_exceptions=non_retryable_exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return engine.execute(func, *args, **kwargs)
        return wrapper
    return decorator
