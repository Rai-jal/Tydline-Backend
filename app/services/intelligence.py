"""
Shipment intelligence layer.

Responsibilities:
- Build human-readable shipment timelines from tracking data
- Compute basic demurrage risk and free days remaining
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import orm


@dataclass
class DemurrageRisk:
    level: str  # LOW, MEDIUM, HIGH
    free_days_remaining: int | None
    days_since_discharge: int | None


def build_shipment_timeline(raw_tracking: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Construct a normalized timeline from ShipsGo tracking payload.

    The exact schema depends on ShipsGo; we look for a 'milestones' array
    where each element has at least an event description, time, and location.
    """
    data = raw_tracking or {}
    container = data.get("container") or data.get("data") or data
    milestones = container.get("milestones") or data.get("milestones") or []

    timeline: list[dict[str, Any]] = []
    for m in milestones:
        if not isinstance(m, dict):
            continue
        event = m.get("event") or m.get("status") or m.get("description")
        time = m.get("time") or m.get("event_time") or m.get("created_at")
        location = (
            m.get("location")
            or m.get("port")
            or m.get("port_name")
            or m.get("unlocode")
        )
        if not event or not time:
            continue
        timeline.append(
            {
                "event": event,
                "time": time,
                "location": location,
                "raw": m,
            }
        )

    # Sort by time if parsable; otherwise keep original order
    def _parse_dt(ts: str) -> datetime:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=UTC)

    timeline.sort(key=lambda e: _parse_dt(e["time"]))
    return timeline


def compute_demurrage_risk(
    timeline: list[dict[str, Any]],
    free_days: int,
) -> DemurrageRisk:
    """
    Very simple rule-based demurrage risk detector.
    """
    if free_days <= 0:
        return DemurrageRisk(level="UNKNOWN", free_days_remaining=None, days_since_discharge=None)

    discharged_time: datetime | None = None
    for event in reversed(timeline):
        name = (event.get("event") or "").lower()
        if "discharged" in name or "arrived" in name:
            ts = event.get("time")
            try:
                discharged_time = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                continue
            break

    if discharged_time is None:
        return DemurrageRisk(level="LOW", free_days_remaining=free_days, days_since_discharge=None)

    now = datetime.now(tz=UTC)
    days_since = max(0, (now - discharged_time).days)
    remaining = free_days - days_since

    if remaining <= 0:
        level = "HIGH"
    elif remaining <= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    return DemurrageRisk(
        level=level,
        free_days_remaining=remaining,
        days_since_discharge=days_since,
    )


async def persist_timeline_and_risk(
    session: AsyncSession,
    shipment: orm.Shipment,
    raw_tracking: dict[str, Any],
    free_days: int = 5,
) -> None:
    """
    Convenience helper to generate and store timeline + risk on a shipment.
    """
    timeline = build_shipment_timeline(raw_tracking)
    risk = compute_demurrage_risk(timeline, free_days)

    shipment.timeline_json = timeline or None
    shipment.demurrage_risk = risk.level
    shipment.free_days_remaining = risk.free_days_remaining

    await session.commit()
    await session.refresh(shipment)
