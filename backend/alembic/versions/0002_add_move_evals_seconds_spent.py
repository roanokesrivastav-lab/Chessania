"""add move_evals.seconds_spent

Reserves per-move clock time as a first-class, nullable column so future v2
time-management coaching (roadmap Part G #11) never needs a painful mid-pipeline
schema retrofit. Populated from S9 onward out of the PGN's [%clk] data; no v1
feature/rule reads it. A separate migration (not an edit to the committed 0001)
because migrations are append-only history.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("move_evals", sa.Column("seconds_spent", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("move_evals", "seconds_spent")
