"""Unit tests for input validation schemas."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.shipment import ShipmentCreate


class TestContainerNumberValidation:
    def test_valid_container_number(self):
        s = ShipmentCreate(container_number="MSCU1234567", user_id=uuid.uuid4())
        assert s.container_number == "MSCU1234567"

    def test_lowercase_is_normalised(self):
        s = ShipmentCreate(container_number="mscu1234567", user_id=uuid.uuid4())
        assert s.container_number == "MSCU1234567"

    def test_whitespace_stripped(self):
        s = ShipmentCreate(container_number="  MSCU1234567  ", user_id=uuid.uuid4())
        assert s.container_number == "MSCU1234567"

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError):
            ShipmentCreate(container_number="INVALID", user_id=uuid.uuid4())

    def test_too_short_raises(self):
        with pytest.raises(ValidationError):
            ShipmentCreate(container_number="MSCU123", user_id=uuid.uuid4())

    def test_digits_only_raises(self):
        with pytest.raises(ValidationError):
            ShipmentCreate(container_number="12345678901", user_id=uuid.uuid4())
