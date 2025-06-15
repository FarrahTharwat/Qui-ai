# app/utils/retry.py
import asyncio
import random
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def async_retry(max_retries=3, initial_delay=1, max_delay=30, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay

            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise

                    # Calculate next delay with jitter
                    next_delay = min(max_delay, delay * backoff_factor)
                    jitter = next_delay * 0.1 * random.random()
                    actual_delay = next_delay + jitter

                    logger.warning(f"Retry {retries}/{max_retries} after {actual_delay:.2f}s for {func.__name__}: {e}")
                    await asyncio.sleep(actual_delay)
                    delay = next_delay

        return wrapper

    return decorator