"""attempts and streaks

V2-S4: the first real trainer — retry your own mined blunder positions.
Additive migration — does not touch any existing table.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attempts",
        sa.Column("id", app.models.GUID(), nullable=False),
        sa.Column("user_id", app.models.GUID(), nullable=False),
        sa.Column("ref_type", sa.Text(), nullable=False),
        sa.Column("ref_id", app.models.GUID(), nullable=False),
        sa.Column("trainer", sa.Text(), nullable=False),
        sa.Column("grade", sa.Text(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint(
            "ref_type in ('position','curated','duel')",
            name="attempts_ref_type_check",
        ),
        sa.CheckConstraint(
            "grade in ('perfect','pass','fail')",
            name="attempts_grade_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "streaks",
        sa.Column("id", app.models.GUID(), nullable=False),
        sa.Column("user_id", app.models.GUID(), nullable=False),
        sa.Column("trainer", sa.Text(), nullable=False),
        sa.Column("current", sa.Integer(), nullable=False),
        sa.Column("best", sa.Integer(), nullable=False),
        sa.Column("last_active_date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "trainer", name="streaks_user_trainer_key"),
    )


def downgrade() -> None:
    op.drop_table("streaks")
    op.drop_table("attempts")
