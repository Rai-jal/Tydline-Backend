"""
Pydantic AI logistics agent: Qwen 2.5 via Groq + tools (shipments, tracking) + Mem0 memory.

Use from API or WhatsApp webhook: run the agent with user message and deps (session, user_id),
then store the turn in Mem0 for future context.

Every agent run is traced in Langfuse when configured.
"""

import contextvars
import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import orm
from app.services.tracking import fetch_container_tracking_data

logger = logging.getLogger(__name__)

# Holds the active Langfuse trace for the current agent run so tools can attach spans
_current_trace: contextvars.ContextVar = contextvars.ContextVar("langfuse_trace", default=None)

# Lazy agent creation so we don't require groq/pydantic-ai at import if not used
_agent = None


@dataclass
class AgentDeps:
    """Dependencies for the logistics agent: DB session and current user."""

    session: AsyncSession
    user_id: str  # User identifier (e.g. str(user.id) or email) for DB and Mem0


def _build_agent():
    if not settings.groq_api_key:
        return None
    try:
        from pydantic_ai import Agent, RunContext
        from pydantic_ai.models.groq import GroqModel
        from pydantic_ai.providers.groq import GroqProvider

        model = GroqModel(
            settings.groq_model_agent,
            provider=GroqProvider(api_key=settings.groq_api_key),
        )
        agent = Agent(
            model,
            deps_type=AgentDeps,
            instructions=(
                "You are Tydline's logistics assistant. You help importers track containers and avoid demurrage. "
                "Use the tools to look up the user's shipments and container status when needed. "
                "Be concise and actionable. If you don't have data, say so and suggest they add a container or try again later."
            ),
        )

        @agent.system_prompt
        async def system_prompt(ctx: RunContext[AgentDeps]) -> str:
            base = (
                "You are Tydline's logistics assistant. Help the user with container tracking and demurrage risk. "
                "Use list_my_shipments to see their shipments and get_shipment_status for live status of a container."
            )
            from app.agents.memory import agent_memory

            memories = agent_memory.search(ctx.deps.user_id, "shipments containers tracking", limit=5)
            if memories:
                base += "\n\nRelevant context from past conversations:\n" + "\n".join(f"- {m}" for m in memories)
            return base

        @agent.tool
        async def list_my_shipments(ctx: RunContext[AgentDeps]) -> str:
            """List the current user's shipments (container number, status, ETA). Use this when the user asks about their containers or shipments."""
            trace = _current_trace.get()
            span = None
            if trace is not None:
                try:
                    span = trace.start_observation(name="list_my_shipments", as_type="tool", input={"user_id": ctx.deps.user_id})
                except Exception:
                    pass
            try:
                uid = ctx.deps.user_id
                try:
                    user_uuid = UUID(uid)
                except ValueError:
                    result_str = "Could not identify user. Please try again."
                    _end_span(span, result_str)
                    return result_str
                result = await ctx.deps.session.execute(
                    select(orm.Shipment)
                    .where(orm.Shipment.user_id == user_uuid)
                    .order_by(orm.Shipment.created_at.desc())
                )
                shipments = result.scalars().all()
                if not shipments:
                    result_str = "No shipments found for this user."
                    _end_span(span, result_str)
                    return result_str
                lines = []
                for s in shipments:
                    eta = s.eta.isoformat() if s.eta else "—"
                    risk = f", risk: {s.demurrage_risk}" if s.demurrage_risk else ""
                    lines.append(f"- {s.container_number}: {s.status}, ETA {eta}{risk}")
                result_str = "\n".join(lines)
                _end_span(span, result_str)
                return result_str
            except Exception as e:
                logger.exception("list_my_shipments failed")
                err = f"Error loading shipments: {e!s}"
                _end_span(span, err, error=True)
                return err

        @agent.tool
        async def get_shipment_status(ctx: RunContext[AgentDeps], container_number: str) -> str:
            """Get live tracking status for a container from ShipsGo. Use when the user asks about a specific container number."""
            trace = _current_trace.get()
            span = None
            if trace is not None:
                try:
                    span = trace.start_observation(
                        name="shipsgo_container_lookup",
                        as_type="tool",
                        input={"container_number": container_number},
                        metadata={"tool": "get_shipment_status"},
                    )
                except Exception:
                    pass
            if not container_number or not container_number.strip():
                result_str = "Please provide a container number."
                _end_span(span, result_str)
                return result_str
            try:
                data = await fetch_container_tracking_data(container_number.strip())
                if not data:
                    result_str = f"No tracking data found for container {container_number}."
                    _end_span(span, result_str)
                    return result_str
                status = data.get("status") or "unknown"
                location = data.get("location") or "—"
                eta = data.get("eta")
                eta_str = eta.isoformat() if hasattr(eta, "isoformat") else str(eta) if eta else "—"
                vessel = data.get("vessel") or "—"
                result_str = f"Container {data.get('container_number', container_number)}: status={status}, location={location}, ETA={eta_str}, vessel={vessel}"
                _end_span(span, result_str)
                return result_str
            except Exception as e:
                logger.exception("get_shipment_status failed")
                err = f"Error fetching status: {e!s}"
                _end_span(span, err, error=True)
                return err

        return agent
    except ImportError as e:
        logger.warning("Pydantic AI / Groq not available: %s", e)
        return None


def _strip_thinking(text: str) -> str:
    """
    Remove Qwen3 thinking blocks from agent output.
    Handles both complete <think>...</think> and incomplete blocks (token cutoff).
    """
    # Remove complete blocks first
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Remove any remaining incomplete block (no closing tag)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
    return text.strip()


def _end_span(span, output: str, error: bool = False) -> None:
    """Safely update and end a Langfuse span (v4 API: update then end)."""
    if span is None:
        return
    try:
        if error:
            span.update(output=output, level="ERROR", status_message=output)
        else:
            span.update(output=output)
        span.end()
    except Exception:
        pass


def get_logistics_agent():
    """Return the shared logistics agent, or None if Groq is not configured."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


async def run_agent(user_id: str, message: str, session: AsyncSession) -> str | None:
    """
    Run the logistics agent for one user message and return the reply.
    Persists the turn to Mem0 when Mem0 is configured.
    Returns None if the agent is not available (e.g. no Groq key).
    """
    agent = get_logistics_agent()
    if not agent:
        return None
    from app.agents.memory import agent_memory
    from app.observability.langfuse import create_trace

    # Create a Langfuse trace for the full agent turn and expose it via context var
    trace = create_trace(
        name="whatsapp_container_query",
        user_id=user_id,
        metadata={"model": settings.groq_model_agent},
        tags=["agent", "qwen"],
    )
    generation = None
    if trace is not None:
        try:
            generation = trace.start_observation(
                name="qwen_shipping_agent",
                as_type="generation",
                model=settings.groq_model_agent,
                input=message,
            )
        except Exception:
            pass

    token = _current_trace.set(trace)
    deps = AgentDeps(session=session, user_id=user_id)
    try:
        result = await agent.run(message, deps=deps)
        output = result.output if hasattr(result, "output") else str(result)
        output = _strip_thinking(output)
        if generation is not None:
            try:
                generation.update(output=output)
                generation.end()
            except Exception:
                pass
        # Store in Mem0 for future context
        await agent_memory.add(
            user_id,
            [{"role": "user", "content": message}, {"role": "assistant", "content": output}],
            metadata={"source": "tydline_agent"},
        )
        return output
    except Exception as e:
        logger.exception("Agent run failed: %s", e)
        if generation is not None:
            try:
                generation.update(output=None, level="ERROR", status_message=str(e))
                generation.end()
            except Exception:
                pass
        return None
    finally:
        _current_trace.reset(token)
