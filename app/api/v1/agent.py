"""
REST endpoint for the Pydantic AI logistics agent (Qwen 2.5 + Mem0).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.db.session import get_db
from app.agents.logistics import run_agent

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(require_api_key)],
)

DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


class AgentChatRequest(BaseModel):
    """Request body for agent chat."""

    user_id: str  # User identifier (e.g. str(user UUID) or email) for DB + Mem0
    message: str


class AgentChatResponse(BaseModel):
    """Response from agent chat."""

    reply: str


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    body: AgentChatRequest,
    db: DbSessionDep,
) -> AgentChatResponse:
    """
    Send a message to the logistics agent and get a reply.
    Uses Pydantic AI (Qwen 2.5 via Groq), tools (shipments, tracking), and Mem0 for context.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message is required",
        )
    reply = await run_agent(body.user_id, body.message.strip(), db)
    if reply is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not available. Set GROQ_API_KEY and ensure pydantic-ai is installed.",
        )
    return AgentChatResponse(reply=reply)
