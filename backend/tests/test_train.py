"""V2-S4: offline tests for trainer routes — positions, attempts, streaks.

All tests offline, no engine, no network.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth import _serializer
from app.db import enable_sqlite_foreign_keys, get_session
from app.main import app, _upsert_streak
from app.models import (
    Attempt,
    Base,
    Game,
    Player,
    Streak,
    TrainingPosition,
    User,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def shared_session():
    """Thread-safe file-based SQLite for TestClient route tests."""
    import os
    db_path = "/tmp/chessania_test_train.sqlite3"
    if os.path.exists(db_path):
        os.remove(db_path)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


# ── Positions endpoint ────────────────────────────────────────────────


def test_positions_returns_empty_list_for_player_with_no_positions(shared_session):
    """Existing player with analyzed games but zero training_positions → [ ]."""
    player = Player(platform="chesscom", username="emptyplayer", rating_snapshot=1200)
    shared_session.add(player)
    shared_session.commit()

    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.get(
            "/api/train/positions?platform=chesscom&username=emptyplayer"
        )
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_positions_returns_seeded_rows(shared_session):
    """Seeded training_positions are returned with game_url, fen, and
    opponent_move_san/uci derived from the source PGN."""
    player = Player(platform="chesscom", username="seededplayer", rating_snapshot=1200)
    shared_session.add(player)
    shared_session.commit()

    # A real short PGN: 1. e4 e5 2. Nf3 Nc6
    game = Game(
        player_id=player.id,
        platform_game_id="g1",
        game_url="https://www.chess.com/game/live/g1",
        pgn='[Event "?"]\n[Site "?"]\n[Date "2025.01.01"]\n[Round "?"]\n[White "Player"]\n[Black "Opponent"]\n[Result "*"]\n\n1. e4 e5 2. Nf3 Nc6 *',
        time_class="blitz",
        player_color="white",
        result="loss",
        analyzed_at=datetime.now(timezone.utc),
    )
    shared_session.add(game)
    shared_session.commit()

    # ply=1 (White's e4): no prior move.
    pos1 = TrainingPosition(
        player_id=player.id,
        source_game_id=game.id,
        ply=1,
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        category="blunder",
        best_line_uci="e7e5",
        eval_before_cp=20,
        mined_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    # ply=3 (White's Nf3): prior move was Black's e5 (ply=2).
    pos2 = TrainingPosition(
        player_id=player.id,
        source_game_id=game.id,
        ply=3,
        fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        category="blunder",
        best_line_uci="d7d6",
        eval_before_cp=15,
        mined_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    shared_session.add_all([pos1, pos2])
    shared_session.commit()

    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.get(
            "/api/train/positions?platform=chesscom&username=seededplayer"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        # ply=1: no prior move.
        row1 = data[0]
        assert row1["ply"] == 1
        assert row1["opponent_move_san"] is None
        assert row1["opponent_move_uci"] is None

        # ply=3: opponent played e5.
        row2 = data[1]
        assert row2["ply"] == 3
        assert row2["opponent_move_san"] == "e5"
        assert row2["opponent_move_uci"] == "e7e5"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_positions_404s_for_unknown_player(shared_session):
    """Unknown username → 404."""
    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.get(
            "/api/train/positions?platform=chesscom&username=nobody"
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_session, None)


# ── Attempts endpoint ─────────────────────────────────────────────────


def test_attempts_401s_without_session(shared_session):
    """POST without a session cookie → 401."""
    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.post("/api/train/attempts", json={
            "ref_id": str(uuid.uuid4()),
            "trainer": "retry",
            "grade": "pass",
            "seconds": 5,
        })
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_attempts_inserts_with_valid_session(shared_session):
    """With a valid session cookie, the attempt is persisted and streak returned."""
    user = User(
        id=uuid.uuid4(),
        email="trainer@example.com",
        display_name="Trainer User",
    )
    shared_session.add(user)
    shared_session.commit()

    token = _serializer().dumps({"user_id": str(user.id)})

    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.post(
            "/api/train/attempts",
            json={
                "ref_id": str(uuid.uuid4()),
                "trainer": "retry",
                "grade": "perfect",
                "seconds": 12,
            },
            headers={"Cookie": f"chessania_session={token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == 1
        assert data["best"] == 1

        # Verify the Attempt row was created.
        attempts = shared_session.query(Attempt).filter_by(user_id=user.id).all()
        assert len(attempts) == 1
        assert attempts[0].grade == "perfect"
    finally:
        app.dependency_overrides.pop(get_session, None)


# ── Streak unit tests (pure function, 4 branches) ─────────────────────


def _make_user(session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="streaker@example.com",
        display_name="Streak User",
    )
    session.add(user)
    session.commit()
    return user


def test_streak_first_attempt_creates_current_1_best_1(shared_session):
    """First attempt ever → current=1, best=1, today."""
    user = _make_user(shared_session)
    streak = _upsert_streak(shared_session, user.id, "retry")
    shared_session.commit()
    assert streak.current == 1
    assert streak.best == 1
    assert streak.last_active_date.date() == date.today()


def test_streak_same_day_no_change(shared_session):
    """Same-day attempt → current/best unchanged."""
    user = _make_user(shared_session)
    s1 = _upsert_streak(shared_session, user.id, "retry")
    shared_session.commit()
    s2 = _upsert_streak(shared_session, user.id, "retry")
    shared_session.commit()
    assert s2.current == 1
    assert s2.best == 1


def test_streak_consecutive_day_bumps_current_and_best(shared_session):
    """Consecutive day → current += 1, best bumped if exceeded."""
    user = _make_user(shared_session)
    # Set last_active_date to yesterday.
    s1 = _upsert_streak(shared_session, user.id, "retry")
    yesterday = date.today() - timedelta(days=1)
    s1.last_active_date = yesterday
    shared_session.commit()

    s2 = _upsert_streak(shared_session, user.id, "retry")
    shared_session.commit()
    assert s2.current == 2
    assert s2.best == 2


def test_streak_gap_day_resets_current(shared_session):
    """A gap (≥2 days since last activity) resets current to 1, best stays."""
    user = _make_user(shared_session)
    s1 = _upsert_streak(shared_session, user.id, "retry")
    # Set last_active_date to 3 days ago.
    three_days_ago = date.today() - timedelta(days=3)
    s1.last_active_date = three_days_ago
    s1.current = 5
    s1.best = 7
    shared_session.commit()

    s2 = _upsert_streak(shared_session, user.id, "retry")
    shared_session.commit()
    assert s2.current == 1  # reset
    assert s2.best == 7     # preserved
