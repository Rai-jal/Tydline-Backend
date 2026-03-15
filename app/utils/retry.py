"""
Retry helper with exponential backoff for external API calls.
"""

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retries(
    func: Callable[[], Awaitable[T]],
    retries: int = 3,
    base_delay: float = 1.0,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T | None:
    """
    Execute an async call with exponential backoff on failure.
    delay = base_delay * (2 ** (attempt - 1)).
    Returns None if all retries fail.
    """
    attempt = 0
    last_exc: Exception | None = None
    while attempt <= retries:
        try:
            return await func()
        except (httpx.HTTPError, OSError) as exc:
            last_exc = exc
            attempt += 1
            if attempt > retries:
                logger.warning("retries exhausted after %s attempts: %s", retries, exc)
                return None
            delay = base_delay * (2 ** (attempt - 1))
            if on_retry:
                on_retry(attempt, exc)
            await asyncio.sleep(delay)
    return None
