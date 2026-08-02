"""duels table

V2-S10: stores Lichess open-challenge share-links created from a FEN.
creator_user_id is nullable (guests can create duels). result is null
until game-result polling is built (out of scope for S10).

Uses batch_alter_table for SQLite compatibility.

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "duels",
        sa.Column("id", app.models.GUID(), primary_key=True),
        sa.Column("creator_user_id", app.models.GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fen", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("lichess_urls_json", sa.JSON(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("duels_creator_idx", "duels", ["creator_user_id"])


def downgrade() -> None:
    op.drop_index("duels_creator_idx", table_name="duels")
    op.drop_table("duels")
