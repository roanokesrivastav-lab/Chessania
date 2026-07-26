"""The in-memory job registry and its two HTTP routes, fully offline.

No real network call and no real Stockfish process ever run here: the
endpoint tests monkeypatch app.jobs.run_job to a no-op so the
BackgroundTask FastAPI schedules never actually fetches or analyzes
anything (Rule 5: the suite is offline and deterministic).
"""

import pytest
from fastapi.testclient import TestClient

from app import jobs, main
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_registry():
    """The registry is module-global — clear it before and after every test
    so state never leaks between tests (jobs.py's own docstring warns this
    dies on restart; leaking across tests would be the same bug in miniature)."""
    jobs._registry.clear()
    yield
    jobs._registry.clear()


# ---------------------------------------------------------------------------
# Registry unit tests
# ---------------------------------------------------------------------------


def test_get_or_create_job_creates_a_queued_job():
    job, deduped = jobs.get_or_create_job("chesscom", "alice")
    assert deduped is False
    assert job.job_id
    assert job.state == "queued"
    assert job.stage == "fetching"
    assert jobs.get_job(job.job_id) is job


def test_second_call_for_same_live_job_is_deduped():
    job1, deduped1 = jobs.get_or_create_job("chesscom", "alice")
    assert deduped1 is False

    job2, deduped2 = jobs.get_or_create_job("chesscom", "Alice")  # case-insensitive
    assert deduped2 is True
    assert job2.job_id == job1.job_id

    # Once the job is no longer live, a fresh request starts a new job.
    job1.state = "done"
    job3, deduped3 = jobs.get_or_create_job("chesscom", "alice")
    assert deduped3 is False
    assert job3.job_id != job1.job_id


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


def test_analyze_rejects_invalid_username(monkeypatch):
    monkeypatch.setattr(main, "run_job", lambda job_id: None)
    resp = client.post("/api/analyze", json={"platform": "chesscom", "username": "x"})
    assert resp.status_code == 400


def test_analyze_returns_job_id_for_valid_username(monkeypatch):
    monkeypatch.setattr(main, "run_job", lambda job_id: None)
    resp = client.post("/api/analyze", json={"platform": "chesscom", "username": "validuser"})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_job_status_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(main, "run_job", lambda job_id: None)
    resp = client.post("/api/analyze", json={"platform": "lichess", "username": "someone"})
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/api/jobs/{job_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert "state" in body
    assert "stage" in body
    assert "current_game" in body
    assert "total_games" in body


def test_job_status_404_for_unknown_id():
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404
