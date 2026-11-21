"""Exponential back-off retry decorator (used for the REST API and database calls)."""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from functools import wraps

from .logging_setup import get_logger

log = get_logger(__name__)


def retry(
    attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts:
                        log.error("giving up after %d attempts: %s", attempt, exc)
                        raise
                    delay = min(max_delay, base_delay * 2 ** (attempt - 1)) * (0.5 + random.random() / 2)
                    log.warning("attempt %d/%d failed (%s); retrying in %.1fs", attempt, attempts, exc, delay)
                    sleep(delay)

        return wrapper

    return decorator
