"""V2-S2: offline auth tests — no network, no real tokens.

Uses an in-memory SQLite database with check_same_thread=False so it's
safe to share between the test thread and FastAPI's TestClient thread.
All tests are fully offline per Rule 6.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import respx
from fastapi import Request, Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth import (
    _hash_token,
    _upsert_user_by_lichess_id,
    create_session_cookie,
    read_session,
    send_magic_link,
    verify_magic_link,
)
from app.config import settings
from app.db import enable_sqlite_foreign_keys, get_session
from app.main import app
from app.models import Base, MagicLinkToken, User

# ── Fixtures ──────────────────────────────────────────────────────────

# A shared file-based SQLite database that can be used across threads
# (sqlite:///:memory: is per-connection, so the DB disappears in the other
# thread that TestClient uses). A temp file + check_same_thread=False
# gives us the same shared state across threads.

_SHARED_DB_PATH = "/tmp/chessania_test_auth.sqlite3"


@pytest.fixture()
def shared_session():
    """A session against a thread-safe file-based SQLite database. Tables
    are recreated from scratch before each test so state never leaks."""
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


# ── Token hashing ─────────────────────────────────────────────────────


def test_hash_token_is_deterministic():
    raw = "test-token-123"
    assert _hash_token(raw) == _hash_token(raw)


def test_hash_token_differs_for_different_inputs():
    assert _hash_token("abc") != _hash_token("xyz")


# ── Unit tests: store + verify (direct function calls) ────────────────


def test_send_magic_link_stores_hashed_token(shared_session):
    """send_magic_link stores a row with a SHA-256 hash, not the raw token."""
    send_magic_link(shared_session, "test@example.com")

    rows = shared_session.query(MagicLinkToken).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.token_hash != ""
    assert row.email == "test@example.com"
    assert row.used_at is None
    assert row.expires_at is not None


def test_verify_magic_link_succeeds_with_valid_token(shared_session):
    """End-to-end: send + verify, and the token is marked used."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    row = MagicLinkToken(
        token_hash=token_hash,
        email="test@example.com",
        expires_at=expires,
    )
    shared_session.add(row)
    shared_session.commit()

    user = verify_magic_link(shared_session, raw)
    assert user is not None
    assert user.email == "test@example.com"
    assert user.display_name == "test"

    shared_session.refresh(row)
    assert row.used_at is not None


def test_verify_magic_link_rejects_used_token(shared_session):
    """A second use of the same token is rejected."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    row = MagicLinkToken(
        token_hash=token_hash,
        email="test@example.com",
        expires_at=expires,
        used_at=datetime.now(timezone.utc),
    )
    shared_session.add(row)
    shared_session.commit()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        verify_magic_link(shared_session, raw)
    assert exc.value.status_code == 400
    assert "already been used" in exc.value.detail


def test_verify_magic_link_rejects_expired_token(shared_session):
    """An expired token is rejected even if unused."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires = datetime.now(timezone.utc) - timedelta(minutes=1)
    row = MagicLinkToken(
        token_hash=token_hash,
        email="test@example.com",
        expires_at=expires,
    )
    shared_session.add(row)
    shared_session.commit()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        verify_magic_link(shared_session, raw)
    assert exc.value.status_code == 400
    assert "expired" in exc.value.detail.lower()


def test_verify_magic_link_rejects_unknown_token(shared_session):
    """A made-up token that was never stored returns 400."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        verify_magic_link(shared_session, "nonexistent-token")
    assert exc.value.status_code == 400


# ── User upsert idempotency ───────────────────────────────────────────


def test_upsert_user_by_email_is_idempotent(shared_session):
    """Calling verify with the same email twice returns the same User row."""
    # First sign-in.
    raw = secrets.token_urlsafe(32)
    row = MagicLinkToken(
        token_hash=_hash_token(raw),
        email="repeat@example.com",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    shared_session.add(row)
    shared_session.commit()
    user1 = verify_magic_link(shared_session, raw)
    user1_id = user1.id

    # Second sign-in with a new token, same email.
    raw2 = secrets.token_urlsafe(32)
    row2 = MagicLinkToken(
        token_hash=_hash_token(raw2),
        email="repeat@example.com",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    shared_session.add(row2)
    shared_session.commit()
    user2 = verify_magic_link(shared_session, raw2)

    assert user2.id == user1_id
    assert (
        shared_session.query(User).filter_by(email="repeat@example.com").count() == 1
    )


# ── Session cookie round-trip ─────────────────────────────────────────


def test_session_cookie_round_trip():
    """Create a cookie, read it back — the same user_id emerges."""
    user_id = str(uuid.uuid4())
    response = Response()
    create_session_cookie(response, user_id=user_id)

    cookie_header = response.headers.get("set-cookie", "")
    assert "chessania_session=" in cookie_header

    cookie_value = cookie_header.split("chessania_session=")[1].split(";")[0]
    scope = {
        "type": "http",
        "headers": [
            (b"cookie", f"chessania_session={cookie_value}".encode())
        ],
    }
    request = Request(scope)
    recovered = read_session(request)
    assert recovered == user_id


def test_session_cookie_tampered_is_rejected():
    """A tampered cookie value returns None from read_session."""
    scope = {
        "type": "http",
        "headers": [(b"cookie", b"chessania_session=not.a.valid.token")],
    }
    request = Request(scope)
    assert read_session(request) is None


def test_session_cookie_missing_returns_none():
    """No cookie at all returns None."""
    scope = {"type": "http", "headers": []}
    request = Request(scope)
    assert read_session(request) is None


# ── API: /me (guest) ──────────────────────────────────────────────────


def test_auth_me_returns_none_for_guest():
    """Without a cookie, /me returns user=null."""
    client = TestClient(app)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["user"] is None


# ── API: logout ───────────────────────────────────────────────────────


def test_logout_clears_cookie():
    """POST /api/auth/logout clears the session cookie."""
    client = TestClient(app)
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    set_cookie = resp.headers.get("set-cookie", "")
    assert "chessania_session=" in set_cookie


# ── API: Lichess OAuth start ──────────────────────────────────────────


def test_lichess_start_returns_url_and_sets_verifier_cookie():
    """GET /api/auth/lichess/start returns a Lichess authorize URL."""
    client = TestClient(app)
    resp = client.get("/api/auth/lichess/start")
    assert resp.status_code == 200
    assert "url" in resp.json()
    assert resp.json()["url"].startswith("https://lichess.org/oauth")
    assert "chessania_lichess_oauth=" in resp.headers.get("set-cookie", "")


# ── Lichess OAuth: upsert idempotency ─────────────────────────────────


def test_upsert_user_by_lichess_id_is_idempotent(shared_session):
    """Two OAuth sign-ins with the same Lichess account return the same User."""
    user1 = _upsert_user_by_lichess_id(shared_session, "lichess_user_1", "Test Player")
    user2 = _upsert_user_by_lichess_id(
        shared_session, "lichess_user_1", "Test Player Updated"
    )
    assert user2.id == user1.id
    assert user2.display_name == "Test Player Updated"
    assert (
        shared_session.query(User).filter_by(lichess_id="lichess_user_1").count() == 1
    )


# ── Magic-link: no user-enumeration leak ──────────────────────────────


def test_send_magic_link_creates_token_even_for_unknown_email(shared_session):
    """A token is created regardless of whether the email has an account."""
    send_magic_link(shared_session, "completely-new@example.com")
    rows = (
        shared_session.query(MagicLinkToken)
        .filter_by(email="completely-new@example.com")
        .all()
    )
    assert len(rows) == 1


# ── User model: CheckConstraint ───────────────────────────────────────


def test_user_must_have_at_least_one_identity(shared_session):
    """The CheckConstraint prevents a User with neither email nor lichess_id."""
    user = User(display_name="Bad User")
    shared_session.add(user)
    with pytest.raises(Exception):
        shared_session.commit()
    shared_session.rollback()

    user2 = User(email="good@example.com", display_name="Good User")
    shared_session.add(user2)
    shared_session.commit()


# ── API: magic-link flow (using TestClient with DB override) ──────────


def test_request_magic_link_returns_200_for_unknown_email(shared_session):
    """No user-enumeration: a fresh email still returns 200."""
    # Override get_session with our thread-safe session.
    def override_get_session():
        yield shared_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    try:
        resp = client.post(
            "/api/auth/magic-link", json={"email": "nobody@example.com"}
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_verify_magic_link_endpoint_sets_cookie(shared_session):
    """GET /api/auth/magic-link/verify?token=... redirects with a Set-Cookie."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    row = MagicLinkToken(
        token_hash=token_hash,
        email="verify-test@example.com",
        expires_at=expires,
    )
    shared_session.add(row)
    shared_session.commit()

    def override_get_session():
        yield shared_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    try:
        resp = client.get(
            f"/api/auth/magic-link/verify?token={raw}",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "chessania_session=" in resp.headers.get("set-cookie", "")
        assert "/train" in resp.headers["location"]
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_verify_magic_link_endpoint_rejects_used_token(shared_session):
    """Second use of the same token redirects with error."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    row = MagicLinkToken(
        token_hash=token_hash,
        email="used-test@example.com",
        expires_at=expires,
        used_at=datetime.now(timezone.utc),
    )
    shared_session.add(row)
    shared_session.commit()

    def override_get_session():
        yield shared_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    try:
        resp = client.get(
            f"/api/auth/magic-link/verify?token={raw}",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=invalid_link" in resp.headers["location"]
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_auth_me_returns_user_when_signed_in(shared_session):
    """With a valid session cookie, /me returns the signed-in user."""
    user = User(
        id=uuid.uuid4(),
        email="signedin@example.com",
        display_name="Signed In User",
    )
    shared_session.add(user)
    shared_session.commit()

    from app.auth import _serializer

    token = _serializer().dumps({"user_id": str(user.id)})
    cookie_value = f"chessania_session={token}"

    def override_get_session():
        yield shared_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    try:
        resp = client.get("/api/auth/me", headers={"Cookie": cookie_value})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] is not None
        assert data["user"]["display_name"] == "Signed In User"
        assert data["user"]["email"] == "signedin@example.com"
    finally:
        app.dependency_overrides.pop(get_session, None)
