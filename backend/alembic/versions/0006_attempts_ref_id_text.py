"""attempts ref_id → Text (polymorphic ref)

V2-S8: change ref_id from GUID to Text so curated mate positions can use
string IDs alongside UUIDs for position-row references.

Uses batch_alter_table for SQLite compatibility (SQLite doesn't support
ALTER COLUMN … TYPE in the normal path).

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("attempts") as batch_op:
        batch_op.alter_column(
            "ref_id",
            existing_type=app.models.GUID(),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("attempts") as batch_op:
        batch_op.alter_column(
            "ref_id",
            existing_type=sa.Text(),
            type_=app.models.GUID(),
            existing_nullable=False,
        )
