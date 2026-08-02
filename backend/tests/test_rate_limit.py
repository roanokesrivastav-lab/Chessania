"""Session 23 — rate limiting on POST /api/analyze.

Offline only: the limiter fires before the handler body, so an over-limit
request never touches the network or Stockfish.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, limiter
from app.jobs import JobStatus


# Module-level client is fine because the autouse fixture resets the in-memory limiter
# and restores the original rate-limit string after each test.
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter_and_rate():
    """Reset slowapi's in-memory storage and ensure any per-test rate-limit override
    is cleaned up, even if a test raises an exception."""
    original = settings.RATE_LIMIT_ANALYZE
    original_magic = settings.RATE_LIMIT_MAGIC_LINK
    limiter.reset()
    yield
    settings.RATE_LIMIT_ANALYZE = original
    settings.RATE_LIMIT_MAGIC_LINK = original_magic
    limiter.reset()


def _fake_job() -> tuple[JobStatus, bool]:
    return JobStatus(
        job_id="test-job-123",
        platform="chesscom",
        username="hikaru",
        state="queued",
        stage="fetching",
    ), True


def test_analyze_under_limit_succeeds():
    """A single request under the limit returns 200."""
    with patch("app.main.get_or_create_job", return_value=_fake_job()):
        response = client.post(
            "/api/analyze",
            json={"platform": "chesscom", "username": "hikaru"},
        )

    assert response.status_code == 200
    assert response.json() == {"job_id": "test-job-123"}


def test_analyze_over_limit_returns_429():
    """Once the limit is exceeded, further requests get the friendly 429."""
    # Use a tiny limit so the test doesn't need dozens of requests.
    settings.RATE_LIMIT_ANALYZE = "1/minute"
    limiter.reset()

    payload = {"platform": "chesscom", "username": "hikaru"}

    with patch("app.main.get_or_create_job", return_value=_fake_job()):
        # First request is allowed.
        response_1 = client.post("/api/analyze", json=payload)
        assert response_1.status_code == 200

        # Second request exceeds the 1/minute limit.
        response_2 = client.post("/api/analyze", json=payload)
        assert response_2.status_code == 429
        assert response_2.json() == {
            "detail": "You've queued a few already — reports keep, come back soon.",
        }


def test_analyze_429_detail_is_friendly():
    """The 429 body carries the custom friendly detail, not slowapi's default."""
    settings.RATE_LIMIT_ANALYZE = "0/minute"
    limiter.reset()

    response = client.post(
        "/api/analyze",
        json={"platform": "chesscom", "username": "hikaru"},
    )
    assert response.status_code == 429
    body = response.json()
    assert "detail" in body
    assert "reports keep" in body["detail"]


def test_magic_link_over_limit_returns_429():
    """The magic-link send endpoint is rate-limited (V2-S2 audit fix) so it
    can't be used to email-bomb a third party or burn the email quota."""
    settings.RATE_LIMIT_MAGIC_LINK = "1/minute"
    limiter.reset()

    payload = {"email": "someone@example.com"}
    # Patch the send so the test exercises ONLY the limiter, touching no DB/email.
    with patch("app.auth.send_magic_link", return_value=None):
        r1 = client.post("/api/auth/magic-link", json=payload)
        assert r1.status_code == 200
        # Second within the window is blocked (limiter fires before the handler body).
        r2 = client.post("/api/auth/magic-link", json=payload)
        assert r2.status_code == 429
