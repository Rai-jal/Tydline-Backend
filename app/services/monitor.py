"""
Shipment monitoring logic.

This service is responsible for:
- Fetching stored shipment state
- Comparing it with new tracking data
- Detecting meaningful events (e.g. status changes)
- Delegating notifications to the notification service
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import orm
from app.services.notification import send_shipment_status_change_notification


def _parse_eta(eta_raw: Any) -> datetime | None:
    """Parse ETA from tracking data (string or datetime) into datetime."""
    if eta_raw is None:
        return None
    if isinstance(eta_raw, datetime):
        return eta_raw
    if isinstance(eta_raw, str):
        try:
            return datetime.fromisoformat(eta_raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


async def apply_and_monitor_shipment_update(
    session: AsyncSession,
    shipment: orm.Shipment,
    tracking_data: dict[str, Any],
) -> None:
    """
    Compare existing shipment state with new tracking data, update the DB,
    and trigger notifications if meaningful changes are detected.
    """
    previous_status = shipment.status
    previous_eta = shipment.eta

    status = tracking_data.get("status") or previous_status
    eta_raw = tracking_data.get("eta")
    eta = _parse_eta(eta_raw) if eta_raw is not None else previous_eta

    status_changed = status != previous_status
    eta_changed = eta is not None and eta != previous_eta

    if status_changed:
        shipment.status = status

    if eta_changed:
        shipment.eta = eta

    if status_changed or eta_changed:
        await session.commit()
        await session.refresh(shipment)

    if status_changed:
        await send_shipment_status_change_notification(
            session=session,
            shipment=shipment,
            old_status=previous_status,
            new_status=status,
        )
