import re
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

# ISO 6346 container number: 4 letters (owner + equipment category) + 6 digits + 1 check digit
_CONTAINER_RE = re.compile(r"^[A-Z]{4}\d{7}$")


class UserBase(BaseModel):
    email: EmailStr
    phone: str | None = None


class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipmentCreate(BaseModel):
    container_number: str = Field(..., examples=["MSCU1234567"])
    bill_of_lading: str | None = Field(None, max_length=64)
    carrier: str | None = Field(None, max_length=64)
    user_id: uuid.UUID

    @field_validator("container_number")
    @classmethod
    def validate_container_number(cls, v: str) -> str:
        normalised = v.strip().upper()
        if not _CONTAINER_RE.match(normalised):
            raise ValueError(
                "container_number must be 4 letters followed by 7 digits (e.g. MSCU1234567)"
            )
        return normalised


class ShipmentRead(BaseModel):
    id: uuid.UUID
    container_number: str | None
    bill_of_lading: str | None
    carrier: str | None
    vessel: str | None
    origin: str | None
    destination: str | None
    status: str
    eta: datetime | None
    predicted_eta: datetime | None
    demurrage_risk: str | None
    free_days_remaining: int | None
    last_updated: datetime
    user_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line(self) -> str | None:
        """Shipping line — alias for carrier."""
        return self.carrier

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_left(self) -> int:
        """Days until ETA (0 if no ETA or already past)."""
        if self.eta is None:
            return 0
        eta = self.eta if self.eta.tzinfo else self.eta.replace(tzinfo=timezone.utc)
        delta = eta.date() - datetime.now(timezone.utc).date()
        return max(0, delta.days)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress(self) -> int:
        """Percentage of journey completed based on created_at → ETA window (0–100)."""
        if self.eta is None:
            return 0
        now = datetime.now(timezone.utc)
        eta = self.eta if self.eta.tzinfo else self.eta.replace(tzinfo=timezone.utc)
        start = self.created_at if self.created_at.tzinfo else self.created_at.replace(tzinfo=timezone.utc)
        total = (eta - start).total_seconds()
        if total <= 0:
            return 100
        elapsed = (now - start).total_seconds()
        return min(100, max(0, int(elapsed / total * 100)))


class ShipmentListResponse(BaseModel):
    items: list[ShipmentRead]
    total: int


class TrackShipmentResponse(BaseModel):
    status: str
    container_number: str


class NotificationRead(BaseModel):
    id: uuid.UUID
    shipment_id: uuid.UUID
    message: str
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)
