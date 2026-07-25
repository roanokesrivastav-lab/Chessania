"""Session 3 round-trip test: insert a Player, read it back.

Uses a fresh in-memory SQLite database built straight from the models'
metadata (not the dev chessania.sqlite3 file, and not Alembic) — this is
the same offline, deterministic pattern Session 7 formalizes into
conftest.py for the whole suite (roadmap Rule 5: tests never require the
internet or Stockfish).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Player


def test_player_round_trip():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        player = Player(platform="chesscom", username="magnuscarlsen", rating_snapshot=2839)
        session.add(player)
        session.commit()
        player_id = player.id

    with Session(engine) as session:
        fetched = session.get(Player, player_id)
        assert fetched is not None
        assert fetched.platform == "chesscom"
        assert fetched.username == "magnuscarlsen"
        assert fetched.rating_snapshot == 2839
        assert fetched.created_at is not None
