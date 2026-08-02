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


# ── V2-S7: game_urls filter ───────────────────────────────────────────


def test_positions_game_urls_filter_returns_only_matching_game(shared_session):
    """game_urls=one game's URL → only that game's positions returned."""
    player = Player(platform="chesscom", username="filterplayer", rating_snapshot=1200)
    shared_session.add(player)
    shared_session.commit()

    game1 = Game(
        player_id=player.id,
        platform_game_id="g1",
        game_url="https://www.chess.com/game/live/filter1",
        pgn='[Event "?"]\n1. e4 e5 *',
        time_class="blitz",
        player_color="white",
        result="loss",
        analyzed_at=datetime.now(timezone.utc),
    )
    game2 = Game(
        player_id=player.id,
        platform_game_id="g2",
        game_url="https://www.chess.com/game/live/filter2",
        pgn='[Event "?"]\n1. d4 d5 *',
        time_class="blitz",
        player_color="white",
        result="win",
        analyzed_at=datetime.now(timezone.utc),
    )
    shared_session.add_all([game1, game2])
    shared_session.commit()

    pos1 = TrainingPosition(
        player_id=player.id,
        source_game_id=game1.id,
        ply=1,
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        category="blunder",
        best_line_uci="e7e5",
        eval_before_cp=20,
        mined_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    pos2 = TrainingPosition(
        player_id=player.id,
        source_game_id=game2.id,
        ply=1,
        fen="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
        category="blunder",
        best_line_uci="d7d5",
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
        # Filter by game1's URL → only pos1 returned.
        resp = client.get(
            "/api/train/positions?platform=chesscom&username=filterplayer"
            "&game_urls=https%3A%2F%2Fwww.chess.com%2Fgame%2Flive%2Ffilter1"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["game_url"] == "https://www.chess.com/game/live/filter1"

        # Filter by game2's URL → only pos2 returned.
        resp2 = client.get(
            "/api/train/positions?platform=chesscom&username=filterplayer"
            "&game_urls=https%3A%2F%2Fwww.chess.com%2Fgame%2Flive%2Ffilter2"
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2) == 1
        assert data2[0]["game_url"] == "https://www.chess.com/game/live/filter2"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_curated_ref_attempt_inserts_with_string_ref_id(shared_session):
    """V2-S8: curated-ref attempt (ref_type="curated", ref_id="back-rank-1",
    trainer="mate") inserts and updates the mate streak — proving the Text
    column accepts a non-uuid id."""
    user = User(
        id=uuid.uuid4(),
        email="matecurated@example.com",
        display_name="Mate Tester",
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
                "ref_id": "back-rank-1",
                "ref_type": "curated",
                "trainer": "mate",
                "grade": "perfect",
                "seconds": 8,
            },
            headers={"Cookie": f"chessania_session={token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == 1
        assert data["best"] == 1

        # Verify the Attempt row was created with string ref_id.
        attempts = shared_session.query(Attempt).filter_by(user_id=user.id).all()
        assert len(attempts) == 1
        assert attempts[0].ref_type == "curated"
        assert attempts[0].ref_id == "back-rank-1"
        assert attempts[0].trainer == "mate"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_positions_game_urls_no_match_returns_empty(shared_session):
    """game_urls matching neither seeded game → empty list, not error."""
    player = Player(platform="chesscom", username="nomatchplayer", rating_snapshot=1200)
    shared_session.add(player)
    shared_session.commit()

    game = Game(
        player_id=player.id,
        platform_game_id="g1",
        game_url="https://www.chess.com/game/live/known",
        pgn='[Event "?"]\n1. e4 e5 *',
        time_class="blitz",
        player_color="white",
        result="loss",
        analyzed_at=datetime.now(timezone.utc),
    )
    shared_session.add(game)
    shared_session.commit()

    pos = TrainingPosition(
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
    shared_session.add(pos)
    shared_session.commit()

    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.get(
            "/api/train/positions?platform=chesscom&username=nomatchplayer"
            "&game_urls=https%3A%2F%2Fwww.chess.com%2Fgame%2Flive%2Funknown"
        )
        assert resp.status_code == 200
        assert resp.json() == []

        # No game_urls param → unfiltered returns the position.
        resp2 = client.get(
            "/api/train/positions?platform=chesscom&username=nomatchplayer"
        )
        assert resp2.status_code == 200
        assert len(resp2.json()) == 1
    finally:
        app.dependency_overrides.pop(get_session, None)


# ── V2-S12: Progress endpoint ─────────────────────────────────────────


def test_progress_guest_returns_401(shared_session):
    """Guest (no session) → 401."""
    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.get("/api/train/progress")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_progress_aggregates_per_trainer_with_streaks(shared_session):
    """Seed attempts across 2 trainers + streaks → correct per-trainer counts."""
    user = User(
        id=uuid.uuid4(),
        email="progress@example.com",
        display_name="Progress User",
    )
    shared_session.add(user)
    shared_session.commit()

    # Retry: 3 attempts (2 perfect, 1 pass).
    for grade in ("perfect", "perfect", "pass"):
        shared_session.add(Attempt(
            user_id=user.id, ref_type="position", ref_id=str(uuid.uuid4()),
            trainer="retry", grade=grade, seconds=5,
        ))
    # Preventer: 1 attempt (1 fail).
    shared_session.add(Attempt(
        user_id=user.id, ref_type="position", ref_id=str(uuid.uuid4()),
        trainer="preventer", grade="fail", seconds=8,
    ))
    # Streak for retry.
    shared_session.add(Streak(
        user_id=user.id, trainer="retry", current=5, best=9,
        last_active_date=date.today(),
    ))
    shared_session.commit()

    token = _serializer().dumps({"user_id": str(user.id)})

    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.get(
            "/api/train/progress",
            headers={"Cookie": f"chessania_session={token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Retry: 3 attempts, 2 perfect, 1 pass, 0 fail, streak 5/9.
        assert "retry" in data
        r = data["retry"]
        assert r["attempts"] == 3
        assert r["perfect"] == 2
        assert r["pass"] == 1
        assert r["fail"] == 0
        assert r["current_streak"] == 5
        assert r["best_streak"] == 9

        # Preventer: 1 attempt, 0/0/1, no streak row → zeros.
        assert "preventer" in data
        p = data["preventer"]
        assert p["attempts"] == 1
        assert p["perfect"] == 0
        assert p["pass"] == 0
        assert p["fail"] == 1
        assert p["current_streak"] == 0
        assert p["best_streak"] == 0
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_progress_does_not_leak_other_users_data(shared_session):
    """User A's progress query must not include User B's attempts."""
    user_a = User(
        id=uuid.uuid4(), email="a-progress@example.com", display_name="A"
    )
    user_b = User(
        id=uuid.uuid4(), email="b-progress@example.com", display_name="B"
    )
    shared_session.add_all([user_a, user_b])
    shared_session.commit()

    shared_session.add(Attempt(
        user_id=user_a.id, ref_type="position", ref_id=str(uuid.uuid4()),
        trainer="retry", grade="perfect", seconds=5,
    ))
    shared_session.add(Attempt(
        user_id=user_b.id, ref_type="position", ref_id=str(uuid.uuid4()),
        trainer="convert", grade="pass", seconds=10,
    ))
    shared_session.add(Attempt(
        user_id=user_b.id, ref_type="position", ref_id=str(uuid.uuid4()),
        trainer="convert", grade="fail", seconds=12,
    ))
    shared_session.commit()

    token = _serializer().dumps({"user_id": str(user_a.id)})

    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        resp = client.get(
            "/api/train/progress",
            headers={"Cookie": f"chessania_session={token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # A has only retry, not convert.
        assert "retry" in data
        assert "convert" not in data
        assert data["retry"]["attempts"] == 1
    finally:
        app.dependency_overrides.pop(get_session, None)


# ── V2-S13: Progress since filter ─────────────────────────────────────


def test_progress_since_filter_counts_only_newer_attempts(shared_session):
    """?since= filters to created_at > since; omitting since counts all."""
    user = User(
        id=uuid.uuid4(), email="since@example.com", display_name="Since User"
    )
    shared_session.add(user)
    shared_session.commit()

    # Older attempt (2 hours ago).
    older = Attempt(
        user_id=user.id, ref_type="position", ref_id=str(uuid.uuid4()),
        trainer="retry", grade="pass", seconds=5,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    # Newer attempt (30 minutes ago).
    newer = Attempt(
        user_id=user.id, ref_type="position", ref_id=str(uuid.uuid4()),
        trainer="retry", grade="perfect", seconds=8,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    shared_session.add_all([older, newer])
    shared_session.commit()

    token = _serializer().dumps({"user_id": str(user.id)})
    cookie = f"chessania_session={token}"

    def override():
        yield shared_session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    try:
        # Cutoff 1 hour ago → only the newer attempt counted.
        # Strip tzinfo so the +00:00 isn't URL-decoded to a space.
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
        resp = client.get(
            f"/api/train/progress?since={cutoff}",
            headers={"Cookie": cookie},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "retry" in data
        assert data["retry"]["attempts"] == 1
        assert data["retry"]["perfect"] == 1

        # No since → both attempts counted (all-time behavior intact).
        resp2 = client.get(
            "/api/train/progress",
            headers={"Cookie": cookie},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["retry"]["attempts"] == 2
    finally:
        app.dependency_overrides.pop(get_session, None)
