"""add shipsgo_shipment_id to shipments

Revision ID: n3c4d5e6f7a8
Revises: m2b3c4d5e6f7
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n3c4d5e6f7a8"
down_revision: Union[str, None] = "m2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("shipsgo_shipment_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_shipments_shipsgo_shipment_id",
        "shipments",
        ["shipsgo_shipment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_shipments_shipsgo_shipment_id", table_name="shipments")
    op.drop_column("shipments", "shipsgo_shipment_id")
