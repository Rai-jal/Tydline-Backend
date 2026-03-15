"""
Abstraction point for carrier / AIS tracking clients.

At MVP, tracking_service calls HTTP endpoints directly.
Later, you can introduce concrete implementations here per carrier
and inject them into tracking_service to support multiple providers cleanly.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrackingResult:
    container_number: str
    status: str
    eta: datetime | None = None
    predicted_eta: datetime | None = None
    raw_payload: dict | None = None
