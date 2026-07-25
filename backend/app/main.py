"""Chessania backend — FastAPI application entrypoint."""

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingest import (
    NoEligibleGames,
    PlayerNotFound,
    UpstreamError,
    UpstreamRateLimited,
    fetch_games,
    persist_games,
    upsert_player,
)

app = FastAPI(title="Chessania API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Returns 200 with a tiny JSON body.

    Verify with:  curl localhost:8000/health
    Edit the message, save, and re-curl — the --reload watcher restarts
    the server automatically, so the change shows without a manual restart.
    """
    return {"status": "ok"}


class IngestRequest(BaseModel):
    platform: Literal["chesscom", "lichess"]
    username: str


@app.post("/api/ingest")
def ingest(payload: IngestRequest, session: Session = Depends(get_session)) -> dict[str, int]:
    """Temporary Session 6 endpoint to manually verify fetch + persist +
    dedupe end to end. Session 10 folds this into the async analyze job;
    this route is deleted then — it exists only so the founder can curl
    the same account twice and watch `new` drop to 0.
    """
    try:
        games = fetch_games(payload.platform, payload.username)
    except PlayerNotFound:
        raise HTTPException(
            status_code=404, detail=f"No such {payload.platform} account: {payload.username}"
        )
    except NoEligibleGames:
        raise HTTPException(
            status_code=404,
            detail=f"{payload.username} has no eligible rapid/blitz games in range.",
        )
    except UpstreamRateLimited:
        raise HTTPException(
            status_code=429, detail="Rate limited upstream — try again in a minute."
        )
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    player = upsert_player(
        session, payload.platform, payload.username, games[0].player_rating if games else None
    )
    return persist_games(session, player, games)
