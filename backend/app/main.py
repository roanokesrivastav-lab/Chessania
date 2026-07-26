"""Chessania backend — FastAPI application entrypoint."""

import re
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.jobs import get_job, get_or_create_job, run_job

app = FastAPI(title="Chessania API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.post("/api/analyze")
def analyze(payload: AnalyzeRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
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
