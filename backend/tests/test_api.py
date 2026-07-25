"""Session 3 round-trip test: insert a Player, read it back.

Uses a fresh in-memory SQLite database built straight from the models'
metadata (not the dev chessania.sqlite3 file, and not Alembic) — this is
the same offline, deterministic pattern Session 7 formalizes into
conftest.py for the whole suite (roadmap Rule 5: tests never require the
internet or Stockfish).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import enable_sqlite_foreign_keys
from app.models import Base, Game, Player


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


def test_deleting_a_player_cascades_to_their_games():
    """Regression test for a real bug caught in review: SQLite ignores
    ON DELETE CASCADE unless PRAGMA foreign_keys=ON is set per connection.
    Appendix 1 specifies cascade on games.player_id; without the fix in
    app/db.py this test fails with 1 orphaned row instead of 0."""
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        player = Player(platform="lichess", username="cascadetest")
        session.add(player)
        session.commit()
        player_id = player.id

        game = Game(
            player_id=player_id,
            platform_game_id="g1",
            game_url="https://lichess.org/g1",
            pgn="1. e4 e5",
            time_class="rapid",
            player_color="white",
            result="win",
        )
        session.add(game)
        session.commit()

    with Session(engine) as session:
        session.delete(session.get(Player, player_id))
        session.commit()

    with Session(engine) as session:
        assert session.query(Game).filter_by(player_id=player_id).count() == 0
