"""Chessania backend — FastAPI application entrypoint."""

import dataclasses
import re
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.features import load_features
from app.jobs import get_job, get_or_create_job, run_job
from app.models import Report as ReportModel

# In-memory rate limiter (correct for the single Railway instance v1; scaling
# horizontally would move this to shared storage — Part G #9).
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Chessania API", version="0.1.0")
app.state.limiter = limiter

# CORS is intentionally driven by the CORS_ORIGINS env/config. S24/S25 sets this
# to the Vercel domain; dev uses the default http://localhost:3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "You've queued a few already — reports keep, come back soon."},
    )

_USERNAME_PATTERNS = {
    "chesscom": r"[a-zA-Z0-9_-]{3,25}",
    "lichess": r"[a-zA-Z0-9_-]{2,30}",
}


def _platform_label(platform: str) -> str:
    return "Chess.com" if platform == "chesscom" else "Lichess"


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Returns 200 with a tiny JSON body.

    Verify with:  curl localhost:8000/health
    Edit the message, save, and re-curl — the --reload watcher restarts
    the server automatically, so the change shows without a manual restart.
    """
    return {"status": "ok"}


class AnalyzeRequest(BaseModel):
    platform: Literal["chesscom", "lichess"]
    username: str


def _analyze_rate_limit() -> str:
    """Callable limit so the rate can be overridden in tests without reloading the module."""
    return settings.RATE_LIMIT_ANALYZE


@app.post("/api/analyze")
@limiter.limit(_analyze_rate_limit)
def analyze(request: Request, payload: AnalyzeRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Kick off (or join) an analysis job for (platform, username) and
    return its job_id immediately. Progress is then polled via
    GET /api/jobs/{job_id} — this route never blocks on the fetch/analyze
    work itself."""
    platform_label = _platform_label(payload.platform)
    if not re.fullmatch(_USERNAME_PATTERNS[payload.platform], payload.username):
        raise HTTPException(
            status_code=400,
            detail=f"That doesn't look like a valid {platform_label} username.",
        )

    job, deduped = get_or_create_job(payload.platform, payload.username)
    if not deduped:
        background_tasks.add_task(run_job, job.job_id)

    return {"job_id": job.job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="That analysis expired or was never started — start a fresh one.",
        )
    return job.to_dict()


@app.get("/api/debug/features/{platform}/{username}")
def debug_features(
    platform: str, username: str, session: Session = Depends(get_session)
) -> dict:
    """Dev-only peek at Session 12's aggregated PlayerFeatures for an already-
    analyzed account — lets the founder eyeball the numbers a coaching report
    will eventually speak in, before there's a report endpoint to read them
    from. Formal prod gating (returning 404 whenever ENV != "dev") lands for
    real in Session 23; until then this plain check keeps the route from
    ever answering in production.

    Session via `Depends(get_session)` (S13) rather than calling
    SessionLocal() directly — same DB session plumbing every other route
    dependency uses, and what lets a test override it with
    `app.dependency_overrides[get_session]` instead of touching the real
    dev database."""
    if settings.ENV != "dev":
        raise HTTPException(status_code=404, detail="Not found.")
    # Debug endpoint is intentionally prod-gated: it only answers when ENV == "dev".
    if platform not in _USERNAME_PATTERNS:
        raise HTTPException(status_code=404, detail="Not found.")

    features = load_features(session, platform, username)

    if features is None:
        raise HTTPException(
            status_code=404,
            detail="No analyzed games for that account yet — run POST /api/analyze first.",
        )
    return dataclasses.asdict(features)


@app.get("/api/reports/{platform}/{username}")
def get_report(platform: str, username: str, session: Session = Depends(get_session)) -> dict:
    """Return the latest stored report for (platform, username). The report is
    generated by the coaching stage in run_job and persisted as JSON, so this
    route is fast and deterministic."""
    if platform not in _USERNAME_PATTERNS:
        raise HTTPException(status_code=404, detail="Not found.")

    from app.models import Player

    player = session.scalars(
        select(Player).where(Player.platform == platform, Player.username == username.lower())
    ).first()
    if player is None:
        raise HTTPException(
            status_code=404,
            detail="No report yet — run POST /api/analyze first.",
        )

    report = session.scalars(
        select(ReportModel).where(ReportModel.player_id == player.id).order_by(desc(ReportModel.created_at))
    ).first()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No report yet — run POST /api/analyze first.",
        )

    return report.report_json
