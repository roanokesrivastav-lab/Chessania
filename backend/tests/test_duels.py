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
