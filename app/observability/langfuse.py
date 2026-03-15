"""
Langfuse observability client for TydLine — compatible with Langfuse SDK v4.

v4 API changes from v2:
- No more langfuse.trace() / trace.generation() / trace.span()
- Use langfuse.start_observation(as_type=...) for root observations
- Use obs.start_observation(...) for child spans / generations
- Use obs.update(output=..., usage_details=...) then obs.end()

All Langfuse operations are wrapped in try/except so failures never break the app.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Suppress Langfuse's OTel "Context error: No active span" warnings — these are
# expected when using the imperative start_observation() API instead of context managers.
logging.getLogger("langfuse").setLevel(logging.ERROR)

_langfuse = None
_initialized = False


def get_langfuse():
    """Return the shared Langfuse client, or None if not configured."""
    global _langfuse, _initialized
    if _initialized:
        return _langfuse

    _initialized = True

    from app.core.config import settings

    public_key = settings.langfuse_public_key
    secret_key = settings.langfuse_secret_key
    host = settings.langfuse_host

    if not (public_key and secret_key):
        logger.info("Langfuse not configured — set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable tracing")
        return None

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("Langfuse observability initialized (host=%s)", host)
    except Exception as exc:
        logger.warning("Langfuse initialization failed: %s", exc)

    return _langfuse


def create_trace(
    name: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
):
    """
    Create a root Langfuse observation (trace). Returns a LangfuseObservationWrapper
    whose .start_observation() method can create child spans and generations.
    Returns None if Langfuse is not available.
    """
    lf = get_langfuse()
    if lf is None:
        return None
    try:
        combined_meta = {**(metadata or {})}
        if user_id:
            combined_meta["user_id"] = user_id
        if tags:
            combined_meta["tags"] = tags

        obs = lf.start_observation(
            name=name,
            as_type="agent",
            metadata=combined_meta,
        )
        # Use obs.trace_id directly — get_current_trace_id() only works inside
        # start_as_current_observation() context managers.
        _log_trace_id(getattr(obs, "trace_id", None) or "?", name)
        return obs
    except Exception as exc:
        logger.warning("Langfuse create_trace(%s) failed: %s", name, exc)
        return None


def flush() -> None:
    """
    Flush pending Langfuse events to the server.
    Call at application shutdown or end of background worker cycles.
    """
    lf = get_langfuse()
    if lf is None:
        return
    try:
        lf.flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed: %s", exc)


def _log_trace_id(trace_id: str, name: str) -> None:
    """Print trace ID in non-production environments so engineers can look it up."""
    from app.core.config import settings

    if settings.environment != "production":
        logger.debug("Langfuse Trace ID [%s]: %s", name, trace_id)


# ---------------------------------------------------------------------------
# FastAPI / Starlette middleware
# ---------------------------------------------------------------------------

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class LangfuseRequestMiddleware(BaseHTTPMiddleware):
        """
        Middleware that creates a Langfuse trace for every HTTP request.
        Captures method, path, status code, and errors.
        """

        async def dispatch(self, request: Request, call_next) -> Response:
            trace = create_trace(
                name="http_request",
                metadata={"method": request.method, "path": request.url.path},
                tags=["http"],
            )

            span = None
            if trace is not None:
                try:
                    span = trace.start_observation(
                        name=f"{request.method} {request.url.path}",
                        as_type="span",
                        input={
                            "method": request.method,
                            "path": request.url.path,
                            "query": str(request.url.query),
                        },
                    )
                except Exception:
                    pass

            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            except Exception as exc:
                if span is not None:
                    try:
                        span.update(
                            output={"error": str(exc)},
                            level="ERROR",
                            status_message=str(exc),
                        )
                        span.end()
                        span = None
                    except Exception:
                        pass
                raise
            finally:
                if span is not None:
                    try:
                        span.update(output={"status_code": status_code})
                        span.end()
                    except Exception:
                        pass

except ImportError:
    LangfuseRequestMiddleware = None  # type: ignore[assignment,misc]
