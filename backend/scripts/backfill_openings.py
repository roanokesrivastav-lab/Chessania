"""Backfill missing opening_eco / opening_name values for existing games.

Usage (from the backend/ directory, venv activated):
    python scripts/backfill_openings.py

The script is idempotent: it only updates rows where opening_eco or
opening_name is NULL, and it skips games that already have data. It is
safe to run multiple times and safe to run while the app is running.
"""

from __future__ import annotations

import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Game
from app.opening_book import classify_opening


CHUNK_SIZE = 500


def main() -> None:
    session = SessionLocal()
    try:
        total = session.scalar(
            select(func.count(Game.id)).where(
                Game.opening_eco.is_(None) | Game.opening_name.is_(None)
            )
        )

        if total == 0:
            print("No games need backfilling.")
            return

        print(f"Found {total} games with missing opening data.")
        updated = 0

        while True:
            # Fetch in small chunks to keep memory pressure low.
            games = session.execute(
                select(Game)
                .where(Game.opening_eco.is_(None) | Game.opening_name.is_(None))
                .limit(CHUNK_SIZE)
            ).scalars().all()

            if not games:
                break

            for game in games:
                eco, name = classify_opening(game.pgn)
                if eco or name:
                    # Only fill what's missing; preserve any existing value.
                    if game.opening_eco is None:
                        game.opening_eco = eco
                    if game.opening_name is None:
                        game.opening_name = name
                    updated += 1

            session.commit()

            # Progress indicator for large DBs.
            print(f"  ... backfilled {updated} games so far", end="\r")

        print(f"\nBackfilled {updated} games.")
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
