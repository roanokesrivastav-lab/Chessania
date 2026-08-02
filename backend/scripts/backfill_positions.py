"""Backfill training positions for every existing analyzed player.

Usage (from the backend/ directory, venv activated):
    python scripts/backfill_positions.py

The script is idempotent — running it twice produces zero new rows the
second time. Safe to run while the app is running (additive only, no deletes).

Mirrors scripts/backfill_openings.py exactly: same sys.path.insert bootstrap,
same session-opening style, same chunked iteration pattern.
"""

from __future__ import annotations

import os
import sys

# Make app/ importable regardless of the caller's cwd (mirrors backfill_openings.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Player
from app.positions import mine_positions


def main() -> None:
    session = SessionLocal()
    try:
        players = session.scalars(select(Player)).all()

        if not players:
            print("No players found.")
            return

        grand_total: dict[str, int] = {"blunder": 0, "unconverted": 0, "danger": 0}
        players_with_new = 0

        for player in players:
            counts = mine_positions(session, player)
            session.commit()
            total_new = sum(counts.values())
            if total_new > 0:
                players_with_new += 1
                print(
                    f"  {player.platform}/{player.username}: "
                    f"blunder={counts['blunder']} unconverted={counts['unconverted']} "
                    f"danger={counts['danger']}"
                )
            for cat in grand_total:
                grand_total[cat] += counts[cat]

        grand = sum(grand_total.values())
        print(
            f"\nBackfill complete: {grand} new positions across "
            f"{players_with_new}/{len(players)} players.\n"
            f"  blunder={grand_total['blunder']} "
            f"unconverted={grand_total['unconverted']} "
            f"danger={grand_total['danger']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
