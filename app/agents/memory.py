"""
Mem0 integration for the logistics agent: store and retrieve conversation/shipment context.

When MEM0_API_KEY is set, uses Mem0 cloud. Otherwise uses a no-op in-memory stub
so the app runs without Mem0 (e.g. local dev). For production conversational flows,
set MEM0_API_KEY (get one at https://mem0.ai).
"""

import asyncio
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_mem0_client: Any = None


def _get_client():
    global _mem0_client
    if _mem0_client is not None:
        return _mem0_client
    if not settings.mem0_api_key:
        return None
    try:
        from mem0 import MemoryClient

        _mem0_client = MemoryClient(api_key=settings.mem0_api_key)
        return _mem0_client
    except Exception as e:
        logger.warning("Mem0 MemoryClient init failed: %s", e)
        return None


async def add_memory(
    user_id: str,
    messages: list[dict[str, str]],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Store a conversation turn for the user. No-op if Mem0 is not configured."""
    client = _get_client()
    if not client:
        return
    try:
        await asyncio.to_thread(
            client.add,
            messages,
            user_id=user_id,
            metadata=metadata or {},
            version="v2",
        )
    except Exception as e:
        logger.warning("Mem0 add_memory failed: %s", e)


def search_memory(user_id: str, query: str, limit: int = 5) -> list[str]:
    """
    Search memories for the user. Returns list of memory strings.
    Returns [] if Mem0 is not configured or search fails.
    """
    client = _get_client()
    if not client:
        return []
    try:
        # Mem0 cloud API: filters with AND/user_id (v2); fallback filter= for older SDKs
        try:
            results = client.search(
                query,
                filters={"AND": [{"user_id": user_id}]},
                limit=limit,
            )
        except TypeError:
            results = client.search(
                query,
                filter={"user_id": user_id},
                limit=limit,
            )
        # Mem0 v2 search may return {"results": [...]} or list of dicts with "memory" or "message"
        if isinstance(results, dict) and "results" in results:
            items = results["results"]
        elif isinstance(results, list):
            items = results
        else:
            return []
        out: list[str] = []
        for item in items:
            if isinstance(item, dict):
                text = item.get("memory") or item.get("message") or item.get("content")
                if isinstance(text, str):
                    out.append(text)
            elif isinstance(item, str):
                out.append(item)
        return out[:limit]
    except Exception as e:
        logger.warning("Mem0 search_memory failed: %s", e)
        return []


class AgentMemory:
    """Thin wrapper used by the agent: add after each turn, search before reply."""

    async def add(self, user_id: str, messages: list[dict[str, str]], metadata: dict[str, Any] | None = None) -> None:
        await add_memory(user_id, messages, metadata)

    def search(self, user_id: str, query: str, limit: int = 5) -> list[str]:
        return search_memory(user_id, query, limit)


agent_memory = AgentMemory()
