"""Session 13 offline tests for GET /api/debug/features/{platform}/{username}
— exercising the S13 refactor that moved this route from calling
SessionLocal() directly to `Depends(get_session)` (app/main.py), which is
what makes overriding the DB with an in-memory, pre-seeded session possible
here instead of touching the real dev database.
"""

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.db import enable_sqlite_foreign_keys, get_session
from app.main import app
from app.models import Base, Game, MoveEval, Player

client = TestClient(app)


@pytest.fixture()
def seeded_session():
    """An in-memory DB with one player who has one fully-analyzed game —
    enough for load_features to return a populated PlayerFeatures.

    StaticPool (a single shared connection, not one-per-thread) is required
    here specifically: FastAPI runs a sync `def` path operation in a
    worker thread, a different thread than the one that builds this
    fixture, and plain ":memory:" SQLite's default SingletonThreadPool
    would hand that other thread a brand new, empty database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        player = Player(platform="chesscom", username="debugtester")
        session.add(player)
        session.commit()

        game = Game(
            player_id=player.id,
            platform_game_id="g1",
            game_url="https://example.com/g1",
            pgn="1. e4 e5",
            time_class="blitz",
            player_color="white",
            result="win",
            analyzed_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add(game)
        session.commit()

        session.add(
            MoveEval(
                game_id=game.id,
                ply=1,
                move_san="e4",
                fen_before="startpos",
                eval_cp_before=0,
                eval_cp_after=10,
                cp_loss=0,
                best_move_san="e4",
                classification="ok",
                phase="opening",
            )
        )
        session.commit()

        yield session


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_session, None)


def test_debug_features_returns_populated_shape_for_analyzed_player(seeded_session):
    app.dependency_overrides[get_session] = lambda: seeded_session

    resp = client.get("/api/debug/features/chesscom/debugtester")

    assert resp.status_code == 200
    body = resp.json()
    assert body["games_analyzed"] == 1
    assert "blunders_per_game" in body
    assert "detectors" in body


def test_debug_features_404_for_player_with_no_analyzed_games(seeded_session):
    app.dependency_overrides[get_session] = lambda: seeded_session

    resp = client.get("/api/debug/features/chesscom/nobodyhome")

    assert resp.status_code == 404


def test_debug_features_404_in_prod(seeded_session, monkeypatch):
    app.dependency_overrides[get_session] = lambda: seeded_session
    monkeypatch.setattr(main.settings, "ENV", "prod")

    resp = client.get("/api/debug/features/chesscom/debugtester")

    assert resp.status_code == 404
