"""training_positions

V2-S3: the accumulating position bank — mined from existing MoveEval data.
Additive migration — does not touch any existing table.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "training_positions",
        sa.Column("id", app.models.GUID(), nullable=False),
        sa.Column("player_id", app.models.GUID(), nullable=False),
        sa.Column("source_game_id", app.models.GUID(), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("fen", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("best_line_uci", sa.Text(), nullable=False),
        sa.Column("eval_before_cp", sa.Integer(), nullable=False),
        sa.Column("mined_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint(
            "category in ('blunder','unconverted','danger')",
            name="training_positions_category_check",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id", "source_game_id", "ply", "category",
            name="training_positions_dedupe_key",
        ),
    )
    op.create_index(
        "training_positions_player_idx", "training_positions", ["player_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("training_positions_player_idx", table_name="training_positions")
    op.drop_table("training_positions")
