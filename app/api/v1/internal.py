"""
Internal endpoints — only callable by trusted systems (Cloud Scheduler, etc.).
Protected by X-API-Key header.

POST /api/v1/internal/run-tracker  — trigger a full tracker cycle
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends

from app.api.deps import require_api_key
from app.workers.tracker import run_tracker_cycle

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_api_key)])


@router.post("/run-tracker", status_code=202)
async def trigger_tracker(background_tasks: BackgroundTasks) -> dict:
    """
    Trigger a full shipment tracking refresh cycle.
    Runs in the background so the scheduler gets a fast 202 response.
    """
    background_tasks.add_task(run_tracker_cycle)
    return {"status": "accepted"}
