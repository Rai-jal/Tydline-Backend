"""add vessel, origin, destination to shipments

Revision ID: l1a2b3c4d5e6
Revises: k0f1a2b3c4d5
Create Date: 2026-03-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l1a2b3c4d5e6"
down_revision: Union[str, None] = "k0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shipments", sa.Column("vessel", sa.String(128), nullable=True))
    op.add_column("shipments", sa.Column("origin", sa.String(128), nullable=True))
    op.add_column("shipments", sa.Column("destination", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("shipments", "destination")
    op.drop_column("shipments", "origin")
    op.drop_column("shipments", "vessel")
