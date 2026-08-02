"""V2-S10: offline duels tests — respx-mocked, no real network.

Uses the same file-based SQLite + TestClient overrides pattern as test_auth.py
(thread-safe shared DB). The Lichess /api/challenge/open call is always
respx-mocked — we never hit the real Lichess API in tests (Rule 6).
"""

import uuid

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db import enable_sqlite_foreign_keys, get_session
from app.main import app
from app.models import Base, Duel, User

_SHARED_DB_PATH = "/tmp/chessania_test_duels.sqlite3"


@pytest.fixture()
def shared_session():
    """Thread-safe file-based SQLite with fresh tables per test."""
    import os

    if os.path.exists(_SHARED_DB_PATH):
        os.remove(_SHARED_DB_PATH)

    engine = create_engine(
        f"sqlite:///{_SHARED_DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(shared_session):
    """TestClient with get_session overridden to our shared DB."""

    def override_get_session():
        yield shared_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


VALID_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

LICHESS_MOCK_RESPONSE = {
    "challenge": {
        "id": "mock1234",
        "url": "https://lichess.org/mock1234",
    },
    "urlWhite": "https://lichess.org/mock1234?color=white",
    "urlBlack": "https://lichess.org/mock1234?color=black",
}


# ── Valid FEN → stores a row + returns both URLs ────────────────────


@respx.mock
def test_create_duel_valid_fen_stores_row_and_returns_urls(client, shared_session):
    """A valid FEN posts to Lichess (mocked), stores a Duel row, and
    returns urlWhite + urlBlack."""
    respx.post("https://lichess.org/api/challenge/open").mock(
        return_value=httpx.Response(200, json=LICHESS_MOCK_RESPONSE)
    )

    resp = client.post(
        "/api/duels",
        json={"fen": VALID_FEN, "source": "paste", "mode": "realtime"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["urlWhite"] == "https://lichess.org/mock1234?color=white"
    assert data["urlBlack"] == "https://lichess.org/mock1234?color=black"
    assert data["challenge_id"] == "mock1234"
    assert data["id"]  # our duel uuid

    # Confirm the Duel row was persisted.
    duel = shared_session.query(Duel).filter_by(id=data["id"]).first()
    assert duel is not None
    assert duel.fen == VALID_FEN
    assert duel.source == "paste"
    assert duel.lichess_urls_json["urlWhite"].endswith("?color=white")
    assert duel.creator_user_id is None  # guest


# ── Invalid FEN → 400 and Lichess NOT called ────────────────────────


@respx.mock
def test_create_duel_invalid_fen_returns_400_no_lichess_call(client):
    """An invalid FEN returns 400 BEFORE the Lichess HTTP call is made."""
    route = respx.post("https://lichess.org/api/challenge/open")

    resp = client.post(
        "/api/duels",
        json={"fen": "not-a-fen", "source": "paste", "mode": "realtime"},
    )
    assert resp.status_code == 400
    assert "valid" in resp.json()["detail"].lower()

    # The Lichess route must NOT have been called.
    assert not route.called


@respx.mock
def test_create_duel_illegal_but_parseable_fen_returns_400(client):
    """A FEN that parses but is an ILLEGAL position (no kings) is rejected with
    a clean 400 before Lichess is called — not passed through to a 502."""
    route = respx.post("https://lichess.org/api/challenge/open")

    resp = client.post(
        "/api/duels",
        json={"fen": "8/8/8/8/8/8/8/8 w - - 0 1", "source": "paste", "mode": "realtime"},
    )
    assert resp.status_code == 400
    assert not route.called


# ── Guest → creator_user_id null ────────────────────────────────────


@respx.mock
def test_create_duel_guest_has_null_creator(client, shared_session):
    """Without a session cookie, the Duel's creator_user_id is null."""
    respx.post("https://lichess.org/api/challenge/open").mock(
        return_value=httpx.Response(200, json=LICHESS_MOCK_RESPONSE)
    )

    resp = client.post(
        "/api/duels",
        json={"fen": VALID_FEN, "source": "paste", "mode": "realtime"},
    )
    assert resp.status_code == 200
    data = resp.json()

    duel = shared_session.query(Duel).filter_by(id=data["id"]).first()
    assert duel.creator_user_id is None


# ── Signed-in → tagged to the user ──────────────────────────────────


@respx.mock
def test_create_duel_signed_in_tags_user(client, shared_session):
    """With a valid session cookie, the Duel's creator_user_id is set."""
    respx.post("https://lichess.org/api/challenge/open").mock(
        return_value=httpx.Response(200, json=LICHESS_MOCK_RESPONSE)
    )

    # Create a signed-in user and a session cookie.
    user = User(
        id=uuid.uuid4(),
        email="duelist@example.com",
        display_name="Duelist",
    )
    shared_session.add(user)
    shared_session.commit()

    from app.auth import _serializer

    token = _serializer().dumps({"user_id": str(user.id)})
    cookie = f"chessania_session={token}"

    resp = client.post(
        "/api/duels",
        json={"fen": VALID_FEN, "source": "paste", "mode": "realtime"},
        headers={"Cookie": cookie},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    duel = shared_session.query(Duel).filter_by(id=data["id"]).first()
    assert duel.creator_user_id == user.id


# ── Lichess 500 → 502 ───────────────────────────────────────────────


@respx.mock
def test_create_duel_lichess_failure_returns_502(client, shared_session):
    """A non-2xx from Lichess returns 502 to the frontend."""
    respx.post("https://lichess.org/api/challenge/open").mock(
        return_value=httpx.Response(500)
    )

    resp = client.post(
        "/api/duels",
        json={"fen": VALID_FEN, "source": "paste", "mode": "realtime"},
    )
    assert resp.status_code == 502

    # Confirm no Duel row was persisted (the error prevented store_duel).
    duels = shared_session.query(Duel).all()
    assert len(duels) == 0


# ── V2-S11: Duel history ─────────────────────────────────────────────


def test_list_duels_guest_returns_401(client):
    """Without a session cookie, GET /api/duels returns 401."""
    resp = client.get("/api/duels")
    assert resp.status_code == 401


def test_list_duels_returns_only_own_duels_newest_first(client, shared_session):
    """A signed-in user sees only their own duels, newest first."""
    # Two users.
    user_a = User(
        id=uuid.uuid4(), email="a@example.com", display_name="A"
    )
    user_b = User(
        id=uuid.uuid4(), email="b@example.com", display_name="B"
    )
    shared_session.add_all([user_a, user_b])
    shared_session.commit()

    # User A creates two duels (older + newer).
    from datetime import datetime, timedelta, timezone

    older = Duel(
        fen=VALID_FEN,
        source="paste",
        lichess_urls_json=LICHESS_MOCK_RESPONSE,
        creator_user_id=user_a.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    newer = Duel(
        fen=VALID_FEN,
        source="curated-endgame",
        lichess_urls_json=LICHESS_MOCK_RESPONSE,
        creator_user_id=user_a.id,
        created_at=datetime.now(timezone.utc),
    )
    # User B's duel — should NOT appear for A.
    other = Duel(
        fen=VALID_FEN,
        source="paste",
        lichess_urls_json=LICHESS_MOCK_RESPONSE,
        creator_user_id=user_b.id,
        created_at=datetime.now(timezone.utc),
    )
    shared_session.add_all([older, newer, other])
    shared_session.commit()

    # Sign in as user A.
    from app.auth import _serializer

    token = _serializer().dumps({"user_id": str(user_a.id)})
    cookie = f"chessania_session={token}"

    resp = client.get("/api/duels", headers={"Cookie": cookie})
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 2  # only A's duels, not B's
    assert data[0]["source"] == "curated-endgame"  # newest first
    assert data[1]["source"] == "paste"
    assert data[0]["urlWhite"] == LICHESS_MOCK_RESPONSE["urlWhite"]
    assert data[0]["urlBlack"] == LICHESS_MOCK_RESPONSE["urlBlack"]


def test_list_duels_empty_for_user_with_no_duels(client, shared_session):
    """A signed-in user with no duels gets an empty list, not an error."""
    user = User(
        id=uuid.uuid4(), email="no-duels@example.com", display_name="NoDuels"
    )
    shared_session.add(user)
    shared_session.commit()

    from app.auth import _serializer

    token = _serializer().dumps({"user_id": str(user.id)})
    cookie = f"chessania_session={token}"

    resp = client.get("/api/duels", headers={"Cookie": cookie})
    assert resp.status_code == 200
    assert resp.json() == []
