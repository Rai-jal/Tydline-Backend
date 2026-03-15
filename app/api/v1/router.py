"""
API v1 router — aggregates all v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import agent, shipments

router = APIRouter(prefix="/api/v1")
router.include_router(shipments.router)
router.include_router(agent.router)
