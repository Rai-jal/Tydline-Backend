"""add index on users phone

Revision ID: a3b7c9d1e2f4
Revises: 7e1509a91c5d
Create Date: 2026-03-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3b7c9d1e2f4'
down_revision: Union[str, Sequence[str], None] = '7e1509a91c5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index on users.phone for WhatsApp lookup."""
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=False)


def downgrade() -> None:
    """Remove index on users.phone."""
    op.drop_index(op.f('ix_users_phone'), table_name='users')
