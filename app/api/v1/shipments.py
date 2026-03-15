import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.db.session import get_db
from app.models import orm
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentListResponse,
    ShipmentRead,
    TrackShipmentResponse,
)
from app.services.tracking import initial_track_shipment

router = APIRouter(
    prefix="/shipments",
    tags=["shipments"],
    dependencies=[Depends(require_api_key)],
)

DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/track",
    response_model=TrackShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def track_shipment(
    payload: ShipmentCreate,
    background_tasks: BackgroundTasks,
    db: DbSessionDep,
) -> TrackShipmentResponse:
    """
    Create a new shipment, persist to database, and kick off initial tracking.
    This matches the MVP example: store, start tracking, return confirmation.
    """
    shipment = orm.Shipment(
        container_number=payload.container_number,
        bill_of_lading=payload.bill_of_lading,
        carrier=payload.carrier,
        user_id=payload.user_id,
        status="tracking_started",
    )
    db.add(shipment)
    await db.commit()
    await db.refresh(shipment)

    # Fire-and-forget tracking initialization in the background
    background_tasks.add_task(initial_track_shipment, shipment.id)

    return TrackShipmentResponse(
        status="tracking_started",
        container_number=shipment.container_number,
    )


@router.get("/{shipment_id}", response_model=ShipmentRead)
async def get_shipment(
    shipment_id: uuid.UUID,
    db: DbSessionDep,
) -> ShipmentRead:
    """
    Retrieve a single shipment by ID.
    """
    result = await db.execute(
        select(orm.Shipment).where(orm.Shipment.id == shipment_id)
    )
    shipment = result.scalar_one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return ShipmentRead.model_validate(shipment)


@router.get("", response_model=ShipmentListResponse)
async def list_shipments(
    db: DbSessionDep,
    user_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ShipmentListResponse:
    """
    List shipments, optionally filtered by user_id with basic pagination.
    """
    stmt = select(orm.Shipment)
    count_stmt = select(func.count(orm.Shipment.id))

    if user_id is not None:
        stmt = stmt.where(orm.Shipment.user_id == user_id)
        count_stmt = count_stmt.where(orm.Shipment.user_id == user_id)

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(
        stmt.order_by(orm.Shipment.created_at.desc()).limit(limit).offset(offset)
    )
    shipments = result.scalars().all()

    return ShipmentListResponse(
        items=[ShipmentRead.model_validate(s) for s in shipments],
        total=total,
    )
