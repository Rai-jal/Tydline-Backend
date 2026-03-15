"""
AI-powered alert generation using Groq.

Converts shipment/risk context into human-readable logistics alerts.
Every call is traced in Langfuse when configured.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def draft_logistics_alert(context: dict[str, Any]) -> str | None:
    """
    Use Groq to turn shipment + risk context into a short, clear alert.
    Returns None if Groq is not configured or the request fails.
    """
    if not settings.groq_api_key:
        return None

    container = context.get("container_number", "")
    status = context.get("status", "")
    location = context.get("location") or "unknown"
    eta = context.get("eta")
    free_days = context.get("free_days_remaining")
    risk = context.get("risk_level", "")

    prompt = f"""You are a logistics assistant helping an importer avoid demurrage fees.

Container: {container}
Status: {status}
Location: {location}
ETA: {eta}
Free days remaining: {free_days}
Risk level: {risk}

Write a short, clear alert (2-4 sentences) explaining the situation and what the importer should do next. Be direct and actionable."""

    messages = [{"role": "user", "content": prompt}]

    # --- Langfuse: open trace + generation ---
    from app.observability.langfuse import create_trace

    trace = create_trace(
        name="draft_logistics_alert",
        metadata={"container_number": container, "risk_level": risk},
        tags=["llm", "alert"],
    )
    generation = None
    if trace is not None:
        try:
            generation = trace.start_observation(
                name="groq_logistics_alert",
                as_type="generation",
                model=settings.groq_model,
                input=messages,
            )
        except Exception:
            pass

    # --- Groq call ---
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.groq_model,
                    "messages": messages,
                    "max_tokens": 256,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning("groq draft_logistics_alert failed: %s", e)
        if generation is not None:
            try:
                generation.update(output=None, level="ERROR", status_message=str(e))
                generation.end()
            except Exception:
                pass
        return None

    # --- Parse response ---
    try:
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        if generation is not None:
            try:
                generation.update(
                    output=content,
                    usage_details={
                        "input": usage.get("prompt_tokens") or 0,
                        "output": usage.get("completion_tokens") or 0,
                        "total": usage.get("total_tokens") or 0,
                    },
                )
                generation.end()
            except Exception:
                pass
        return content.strip() if content else None
    except (KeyError, IndexError, TypeError):
        if generation is not None:
            try:
                generation.update(output=None, level="ERROR", status_message="unexpected response shape")
                generation.end()
            except Exception:
                pass
        return None
