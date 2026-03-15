"""
Shared FastAPI dependencies (auth, etc.).
"""

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    """
    If API_KEY is set in env, require X-API-Key header to match.
    If API_KEY is not set, skip validation (allow all).
    """
    if not settings.api_key:
        return
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
